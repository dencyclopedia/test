"""CER/WER of one model on the held-out line images (tesseract CLI, --psm 7, tools/metrics.py).
usage: python3 eval_heldout.py GTDIR TESSDATA_DIR LANG LABEL   -> one JSON line on stdout"""
import glob, json, os, re, subprocess, sys
from multiprocessing import Pool
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tools"))
import metrics  # noqa: E402

GT, TD, LANG, LABEL = sys.argv[1:5]


def ocr(png):
    p = subprocess.run(["tesseract", png, "-", "--tessdata-dir", TD, "-l", LANG, "--psm", "7"],
                       capture_output=True, text=True, env=dict(os.environ, OMP_THREAD_LIMIT="1"))
    return p.stdout


if __name__ == "__main__":
    pngs = sorted(glob.glob(os.path.join(GT, "*.png")))
    with Pool(os.cpu_count()) as pool:
        hyps = pool.map(ocr, pngs)
    gts = [open(p[:-4] + ".gt.txt", encoding="utf-8").read() for p in pngs]
    errs = sum(metrics._lev(metrics.normalize(g), metrics.normalize(h)) for g, h in zip(gts, hyps))
    chars = sum(len(metrics.normalize(g)) for g in gts)
    werrs = sum(metrics._lev(metrics.normalize(g).split(" "), metrics.normalize(h).split(" ")) for g, h in zip(gts, hyps))
    words = sum(len(metrics.normalize(g).split(" ")) for g in gts)
    m = re.match(r".*_([0-9.]+)_(\d+)_(\d+)$", LANG)
    rec = {"label": LABEL, "model": LANG, "lines": len(pngs),
           "cer": round(errs / chars, 5), "wer": round(werrs / words, 5),
           "checkpoint_bcer_train": float(m.group(1)) if m else None,
           "learning_iteration": int(m.group(2)) if m else None,
           "training_iteration": int(m.group(3)) if m else None,
           "worst": sorted(({"gt": g.strip(), "ocr": h.strip()} for g, h in zip(gts, hyps)
                            if metrics.normalize(g) != metrics.normalize(h)),
                           key=lambda x: -metrics._lev(x["gt"], x["ocr"]))[:5]}
    print(json.dumps(rec, ensure_ascii=False), flush=True)
