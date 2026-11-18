"""Run every binding harness on the same 10 images; collect per-call overhead, pages/s, peak RSS, output identity.

usage: python3 run_bindings.py IMGDIR RESULTS_DIR --passes 5 [--only name,name]
Each harness follows one protocol:  <cmd> TESSDATA LANG PSM PASSES TINY IMG1..IMG10  -> JSON
  {binding, info, init_s, tiny_s[20], pass_s[PASSES][10], texts[10]}
Peak RSS = "Maximum resident set size" from GNU time -v for the harness process (for cli/pytesseract this is the
largest single process, i.e. one tesseract run). OMP_THREAD_LIMIT=1 for everything.
"""
import argparse, glob, json, os, re, statistics, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools"))
import metrics  # noqa: E402

FAST = os.environ.get("FAST", "/opt/tessdata/tessdata_fast")
TJS_MODEL = os.environ.get("TJS_MODEL_DIR", "")  # dir holding tesseract.js's CDN eng.traineddata (gunzipped)
PY = os.environ.get("PYBIN", sys.executable)
PYTESSEROCR_SRC = os.environ.get("PY_TESSEROCR_SRC", "")  # python of a venv where tesserocr is built against 5.5.4


def harnesses():
    h = {
        "tesseract-cli": ([PY, f"{HERE}/python/harness.py", "cli"], FAST),
        "pytesseract": ([PY, f"{HERE}/python/harness.py", "pytesseract"], FAST),
        "tesserocr-wheel": ([PY, f"{HERE}/python/harness.py", "tesserocr"], FAST),
        "cpp-tessbaseapi": ([os.environ.get("CPP_BIN", f"{HERE}/cpp/harness")], FAST),
        "gosseract": ([os.environ.get("GO_BIN", f"{HERE}/go/harness")], FAST),
        "tess4j": (["java", "-Djna.library.path=/opt/tess554/lib", "-cp",
                    f"{HERE}/java/target/classes:{HERE}/java/target/lib/*", "bench.Harness"], FAST),
        "dotnet-tesseract": ([os.environ.get("DOTNET_BIN", f"{HERE}/dotnet/bin/Release/net8.0/harness")], FAST),
        "tesseractjs-localmodel": (["node", f"{HERE}/node/harness.js"], FAST),
        "tesseractjs-cdnmodel": (["node", f"{HERE}/node/harness.js"], "default"),
    }
    if PYTESSEROCR_SRC:
        h["tesserocr-source-5.5.4"] = ([PYTESSEROCR_SRC, f"{HERE}/python/harness.py", "tesserocr"], FAST)
    if TJS_MODEL:
        h["tesseract-cli-tjsmodel"] = ([PY, f"{HERE}/python/harness.py", "cli"], TJS_MODEL)
    return h


def run(name, cmd, td, psm, passes, tiny, imgs, raw):
    full = ["/usr/bin/time", "-v"] + cmd + [td, "eng", psm, str(passes), tiny] + imgs
    env = dict(os.environ, OMP_THREAD_LIMIT="1")
    p = subprocess.run(full, capture_output=True, text=True, env=env)
    open(os.path.join(raw, f"{name}-psm{psm}.stderr.txt"), "w").write(p.stderr[-20000:])
    m = re.search(r"Maximum resident set size \(kbytes\): (\d+)", p.stderr)
    out = p.stdout.strip().splitlines()
    js = None
    for line in reversed(out):
        if line.startswith("{"):
            try:
                js = json.loads(line); break
            except ValueError:
                pass
    return p.returncode, js, (int(m.group(1)) if m else None), p.stderr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("imgdir"); ap.add_argument("res")
    ap.add_argument("--passes", type=int, default=5); ap.add_argument("--only", default="")
    a = ap.parse_args()
    raw = os.path.join(a.res, "raw"); os.makedirs(raw, exist_ok=True)
    imgs = sorted(glob.glob(os.path.join(a.imgdir, "img-*.png")))
    tiny = os.path.join(a.imgdir, "tiny.png")
    gts = [open(i[:-4] + ".gt.txt").read() for i in imgs]
    rows, texts = [], {}
    jobs = [(psm, name) for psm in ("default", "3") for name in harnesses()]
    jobs.append(("3var", "gosseract"))  # gosseract: PSM via SetVariable (SetPageSegMode before first Text() is lost)
    for psm, name in jobs:
            cmd, td = harnesses()[name]
            if a.only and name not in a.only.split(","):
                continue
            rc, js, rss, err = run(name, cmd, td, psm, a.passes, tiny, imgs, raw)
            row = {"binding": name, "psm": psm, "model_dir": td, "exit_code": rc, "peak_rss_mb": round(rss / 1024, 1) if rss else None}
            if js:
                totals = [sum(r) for r in js["pass_s"]]
                row.update({
                    "info": js["info"],
                    "init_s": round(js["init_s"], 4) if js.get("init_s") is not None else None,
                    "per_call_tiny_median_ms": round(1000 * statistics.median(js["tiny_s"]), 2),
                    "per_call_tiny_min_ms": round(1000 * min(js["tiny_s"]), 2),
                    "per_call_tiny_max_ms": round(1000 * max(js["tiny_s"]), 2),
                    "pass_10img_median_s": round(statistics.median(totals), 3),
                    "pass_10img_min_s": round(min(totals), 3), "pass_10img_max_s": round(max(totals), 3),
                    "images_per_s": round(len(imgs) / statistics.median(totals), 3),
                    "cer_mean": round(statistics.mean(metrics.cer(g, t) for g, t in zip(gts, js["texts"])), 5),
                })
                texts[(name, psm)] = js["texts"]
                json.dump(js, open(os.path.join(raw, f"{name}-psm{psm}.json"), "w"), indent=1)
            else:
                row["error_tail"] = err[-1500:]
            print(json.dumps(row)[:400], flush=True)
            rows.append(row)
    # identity vs the CLI with the same model and psm
    for row in rows:
        k = (row["binding"], row["psm"])
        ref = ("tesseract-cli-tjsmodel" if row["binding"] == "tesseractjs-cdnmodel" else "tesseract-cli",
               "3" if row["psm"] == "3var" else row["psm"])
        if k in texts and ref in texts and k != ref:
            a_, b_ = texts[k], texts[ref]
            row["identical_bytes_vs_cli"] = sum(x == y for x, y in zip(a_, b_))
            row["identical_normalized_vs_cli"] = sum(metrics.normalize(x) == metrics.normalize(y) for x, y in zip(a_, b_))
            row["cer_vs_cli_mean"] = round(statistics.mean(metrics.cer(y, x) for x, y in zip(a_, b_)), 5)
            row["identity_reference"] = ref[0]
    json.dump(rows, open(os.path.join(a.res, "bindings.json"), "w"), indent=2)


if __name__ == "__main__":
    main()
