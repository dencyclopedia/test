#!/usr/bin/env python3
"""Chart data for tesseractocr.org/api/ from bench/api (run 44309687300).

Writes tools/images/figures/data/api-host-matrix.jsonl: results/host_matrix.jsonl with the nested
burst8/closed8 summaries flattened (burst_*, closed_*) and a "label" field, so charts.py can read it.
Values are copied, never typed.

usage: python3 tools/images/figures/api_figures.py
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
RES = os.path.join(REPO, "bench", "api", "results")
DATA = os.path.join(HERE, "data")


def main():
    os.makedirs(DATA, exist_ok=True)
    with open(os.path.join(DATA, "api-host-matrix.jsonl"), "w", encoding="utf-8") as f:
        for line in open(os.path.join(RES, "host_matrix.jsonl"), encoding="utf-8"):
            r = json.loads(line)
            row = {k: v for k, v in r.items() if not isinstance(v, (dict, list))}
            for pre, key in (("burst", "burst8"), ("closed", "closed8")):
                for k, v in r[key].items():
                    if not isinstance(v, (dict, list)):
                        row[f"{pre}_{k}"] = v
                row[f"{pre}_status_counts"] = " ".join(f"{n}x{c}" for c, n in r[key]["status_counts"].items())
            row["label"] = f"{r['image']} pool {r['pool']} OMP {r['omp_thread_limit']}"
            f.write(json.dumps(row) + "\n")
    print("ok")


if __name__ == "__main__":
    main()
