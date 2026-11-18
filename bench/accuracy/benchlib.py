"""Helpers shared by the accuracy benches (bench/accuracy, models, psm, preprocess, languages, engines, ocr-online).

- run Tesseract CLI with explicit model dir / OEM / PSM, in parallel (OMP_THREAD_LIMIT=1 per process)
- score with tools/metrics.py (the lab's shared CER/WER; not re-implemented here)
- write results/meta.json with engine version, model commit hashes, OS, CPU, git sha, command lines
"""
import csv
import datetime as _dt
import json
import os
import platform
import subprocess
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CORPUS = REPO / "corpus"
sys.path.insert(0, str(REPO / "tools"))
import metrics  # noqa: E402  (tools/metrics.py)

TESS = {"5.5.4": os.environ.get("TESS554", "/opt/tess554/bin/tesseract"), "5.3.4": "/usr/bin/tesseract"}
TESSDATA_ROOT = Path(os.environ.get("TESSDATA_ROOT", "/opt/tessdata"))
MODELS = {"fast": TESSDATA_ROOT / "tessdata_fast", "standard": TESSDATA_ROOT / "tessdata",
          "best": TESSDATA_ROOT / "tessdata_best",
          "apt": Path("/usr/share/tesseract-ocr/5/tessdata")}  # Ubuntu 24.04 tesseract-ocr-eng package
WORKERS = int(os.environ.get("BENCH_WORKERS", "4"))


def manifest(**filt):
    m = json.loads((CORPUS / "manifest.json").read_text(encoding="utf-8"))["images"]
    out = []
    for e in m:
        ok = True
        for k, v in filt.items():
            if callable(v):
                ok = ok and v(e.get(k))
            elif isinstance(v, (list, tuple, set)):
                ok = ok and e.get(k) in v
            else:
                ok = ok and e.get(k) == v
        if ok:
            out.append(e)
    return out


def gt(entry):
    return (CORPUS / entry["gt"]).read_text(encoding="utf-8")


def tess_cmd(image, version="5.5.4", model="standard", lang="eng", oem=1, psm=3, extra=()):
    return [TESS[version], str(image), "stdout", "--tessdata-dir", str(MODELS.get(model, model)), "-l", lang,
            "--oem", str(oem), "--psm", str(psm), *extra]


def run(cmd, timeout=600):
    env = dict(os.environ, OMP_THREAD_LIMIT="1")
    p = subprocess.run(cmd, capture_output=True, env=env, timeout=timeout)
    return p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace"), p.returncode


def unordered_word_recall(truth, hyp):
    """Supplementary, order-independent metric: share of ground-truth words (multiset) found in the output.
    Used only for layouts with no single reading order (screenshots, receipts, labels). Not a replacement
    for CER/WER."""
    t = Counter(metrics.normalize(truth).split(" "))
    h = Counter(metrics.normalize(hyp).split(" "))
    total = sum(t.values())
    return sum((t & h).values()) / max(total, 1)


def score(truth, hyp):
    return {"cer": metrics.cer(truth, hyp), "wer": metrics.wer(truth, hyp),
            "word_recall_unordered": unordered_word_recall(truth, hyp),
            "gt_chars": len(metrics.normalize(truth)), "out_chars": len(metrics.normalize(hyp))}


def _job(args):
    key, cmd, truth, raw_path = args
    out, err, rc = run(cmd)
    if raw_path:
        Path(raw_path).parent.mkdir(parents=True, exist_ok=True)
        Path(raw_path).write_text(out, encoding="utf-8")
    s = score(truth, out)
    s.update(rc=rc, stderr=err.strip().replace("\n", " | ")[:300])
    return key, s


def run_jobs(jobs, workers=WORKERS):
    """jobs: list of (key, cmd, truth, raw_path or None). Returns {key: score dict}."""
    res = {}
    with ProcessPoolExecutor(workers) as ex:
        for i, (k, s) in enumerate(ex.map(_job, jobs, chunksize=1)):
            res[k] = s
            if (i + 1) % 25 == 0:
                print(f"  {i + 1}/{len(jobs)}", flush=True)
    return res


def score_jobs(items, workers=WORKERS):
    """items: list of (key, truth, hyp). Parallel scoring for outputs produced elsewhere."""
    with ProcessPoolExecutor(workers) as ex:
        return dict(zip([k for k, _, _ in items], ex.map(_score_one, [(t, h) for _, t, h in items], chunksize=4)))


def _score_one(a):
    return score(*a)


def write_csv(path, rows, fields=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = fields or list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: (round(v, 5) if isinstance(v, float) else v) for k, v in r.items()})


def _git(dir_, *args):
    try:
        return subprocess.run(["git", "-C", str(dir_), *args], capture_output=True, text=True).stdout.strip()
    except Exception:
        return None


def cpu_model():
    try:
        for line in open("/proc/cpuinfo"):
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor()


def model_commit(p):
    c = _git(p, "log", "-1", "--format=%H")
    if not c and (Path(p) / "COMMIT").exists():  # Actions: models fetched at a pinned commit by build-tesseract.sh
        c = (Path(p) / "COMMIT").read_text().strip()
    return c or None


def meta(commands, extra=None):
    versions = {}
    for v, b in TESS.items():
        if Path(b).exists():
            versions[v] = run([b, "--version"])[0].splitlines()[:2] or run([b, "--version"])[1].splitlines()[:2]
    m = {
        "date_utc": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "machine": (f"GitHub Actions runner ({os.environ.get('ImageOS', '?')}, image {os.environ.get('ImageVersion', '?')}, "
                    f"run {os.environ.get('GITHUB_RUN_ID', '?')})" if os.environ.get("GITHUB_ACTIONS")
                    else "development container (accuracy only; timings from this machine are not published)"),
        "os": platform.platform(), "cpu": cpu_model(), "cores": os.cpu_count(),
        "python": platform.python_version(),
        "tesseract_binaries": {v: {"path": TESS[v], "version": versions.get(v)} for v in TESS},
        "models": {k: {"path": str(p), "commit": model_commit(p)} for k, p in MODELS.items() if k != "apt"},
        "repo_git_sha": _git(REPO, "rev-parse", "HEAD"),
        "corpus_manifest": "corpus/manifest.json",
        "env": {"OMP_THREAD_LIMIT": "1"},
        "metrics": "tools/metrics.py (CER/WER after NFC + whitespace collapse; case and punctuation kept)",
        "commands": commands,
    }
    if extra:
        m.update(extra)
    return m


def write_meta(path, commands, extra=None):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(meta(commands, extra), indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else float("nan")


def micro_cer(rows):
    """Character-weighted CER over a group: sum(cer*gt_chars)/sum(gt_chars)."""
    n = sum(r["gt_chars"] for r in rows)
    return sum(r["cer"] * r["gt_chars"] for r in rows) / max(n, 1)
