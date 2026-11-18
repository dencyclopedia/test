#!/usr/bin/env python3
"""Per-image timing for one engine (GitHub Actions only; dev-container numbers are not published).

Usage: <python of the engine's venv> bench/engines/timing.py <tesseract|easyocr|paddleocr> <out.csv> [runs]
Images: 3 clean 300-DPI pages, 2 clean receipts, 2 screenshots (light/dark, 1x); English.
Method: model/pipeline created once (its load time is reported separately as load_s); then for each image 1 warm-up
call and N timed calls (default 5) of the recognition function; median/min/max of time.perf_counter.
Tesseract is timed as the CLI (process start + model load included in every call), OMP_THREAD_LIMIT=1.
Thread count for EasyOCR/PaddleOCR follows the environment (THREADS=1 sets OMP/MKL/torch threads to 1).
"""
import csv
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CORPUS = HERE.parents[1] / "corpus"
IMAGES = ["clean/austen_dejavu-serif_300", "clean/doyle_carlito_300", "clean/austen_dejavu-mono_300",
          "receipt/receipt01_dejavu-mono", "receipt/receipt05_carlito", "screenshot/settings_light_1x",
          "screenshot/dashboard_dark_1x"]
THREADS = os.environ.get("THREADS", "default")
if THREADS == "1":
    for v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
        os.environ[v] = "1"


def path(i):
    for ext in (".png", ".jpg"):
        if (CORPUS / (i + ext)).exists():
            return str(CORPUS / (i + ext))
    raise FileNotFoundError(i)


def make(engine):
    if engine == "tesseract":
        tess = os.environ.get("TESS554", "/opt/tess554/bin/tesseract")
        env = dict(os.environ, OMP_THREAD_LIMIT="1")
        cmd = [tess, "{}", "stdout", "--tessdata-dir", "/opt/tessdata/tessdata", "-l", "eng", "--oem", "1", "--psm", "3"]
        return lambda p: subprocess.run([c.replace("{}", p) for c in cmd], capture_output=True, env=env, check=True), 0.0
    t = time.perf_counter()
    if engine == "easyocr":
        import easyocr
        import torch
        if THREADS == "1":
            torch.set_num_threads(1)
        r = easyocr.Reader(["en"], gpu=False, verbose=False)
        f = lambda p: r.readtext(p)  # noqa: E731
    else:
        from paddleocr import PaddleOCR
        kw = dict(lang="en", use_doc_orientation_classify=False, use_doc_unwarping=False,
                  use_textline_orientation=False, enable_mkldnn=False)
        if THREADS == "1":
            kw["cpu_threads"] = 1
        o = PaddleOCR(**kw)
        f = lambda p: list(o.predict(p))  # noqa: E731
    return f, time.perf_counter() - t


def main():
    engine, out = sys.argv[1], Path(sys.argv[2])
    runs = int(sys.argv[3]) if len(sys.argv) > 3 else 5
    f, load = make(engine)
    rows = []
    for i in IMAGES:
        p = path(i)
        f(p)
        ts = []
        for _ in range(runs):
            t = time.perf_counter()
            f(p)
            ts.append(time.perf_counter() - t)
        rows.append(dict(engine=engine, threads=THREADS, id=i, runs=runs, median_s=round(statistics.median(ts), 4),
                         min_s=round(min(ts), 4), max_s=round(max(ts), 4), load_s=round(load, 3)))
        print(rows[-1], flush=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    new = not out.exists()
    with open(out, "a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        if new:
            w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main()
