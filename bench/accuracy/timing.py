#!/usr/bin/env python3
"""Timing: seconds per page for Tesseract 5.5.4 by DPI and by model (fast / standard / best). Run on GitHub Actions only.

Method (LAB.md): OMP_THREAD_LIMIT=1, 1 warm-up run then N timed runs (default 5) per image; we report median, min, max
of the wall-clock time of the whole CLI call (process start + model load + recognition), measured with
time.perf_counter around subprocess.run.
  timing-dpi.csv    : clean pages, DejaVu Serif, 3 passages x DPI 150/200/300/400/600, tessdata standard eng
  timing-models.csv : clean pages at 300 DPI, 3 passages x {DejaVu Serif, Carlito, DejaVu Sans Mono}, fast/standard/best
Usage: python3 bench/accuracy/timing.py <outdir> [runs]
"""
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import benchlib as B  # noqa: E402


def time_cmd(cmd, runs):
    env = dict(os.environ, OMP_THREAD_LIMIT="1")
    subprocess.run(cmd, capture_output=True, env=env, check=True)  # warm-up
    ts = []
    for _ in range(runs):
        t = time.perf_counter()
        subprocess.run(cmd, capture_output=True, env=env, check=True)
        ts.append(time.perf_counter() - t)
    return ts


def main():
    out = Path(sys.argv[1])
    runs = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    rows = []
    for e in B.manifest(set="clean", size_pt=12, font="DejaVu Serif"):
        ts = time_cmd(B.tess_cmd(B.CORPUS / e["image"]), runs)
        rows.append(dict(id=e["id"], dpi=e["dpi"], width=e["width"], height=e["height"], model="standard", runs=runs,
                         median_s=statistics.median(ts), min_s=min(ts), max_s=max(ts)))
        print(rows[-1], flush=True)
    B.write_csv(out / "timing-dpi.csv", rows)
    rows = []
    for e in B.manifest(set="clean", dpi=300, size_pt=12, font=("DejaVu Serif", "Carlito", "DejaVu Sans Mono")):
        for m in ("fast", "standard", "best"):
            ts = time_cmd(B.tess_cmd(B.CORPUS / e["image"], model=m), runs)
            rows.append(dict(id=e["id"], dpi=300, model=m, runs=runs, median_s=statistics.median(ts), min_s=min(ts),
                             max_s=max(ts)))
            print(rows[-1], flush=True)
    B.write_csv(out / "timing-models.csv", rows)
    B.write_meta(out / "meta.json", {"timing": " ".join(B.tess_cmd("<image>", model="<model>"))},
                 {"runs_per_image": runs, "warmup_runs": 1, "timer": "time.perf_counter around the full CLI call",
                  "cpu_lscpu": subprocess.run(["lscpu"], capture_output=True, text=True).stdout})


if __name__ == "__main__":
    main()
