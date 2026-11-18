#!/usr/bin/env python3
"""Before/after table for the RTL fix: browser CER of the tool before (../results/comparison.csv, run of
2026-11-18 07:13 UTC) and after the fix (comparison.csv in this folder), plus native Tesseract 5.5.4.
Usage: python3 bench/ocr-online/results-2026-11-18-rtl-fix/compare.py  -> before_after.csv"""
import csv
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
old = {r["id"]: r for r in csv.DictReader(open(HERE.parent / "results" / "comparison.csv", encoding="utf-8"))}
new = list(csv.DictReader(open(HERE / "comparison.csv", encoding="utf-8")))
runs = {r["id"]: r for r in json.loads((HERE / "browser_runs.json").read_text(encoding="utf-8"))["runs"]}
cols = ["label", "id", "lang", "browser_cer_before", "browser_cer_after", "browser_word_recall_before",
        "browser_word_recall_after", "native_standard_cer", "native_best_cer", "confidence_badge_after",
        "wall_s_dev_container_after"]
with open(HERE / "before_after.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=cols)
    w.writeheader()
    for r in new:
        o, run = old[r["id"]], runs[r["id"]]
        w.writerow({"label": r["label"], "id": r["id"], "lang": r["lang"],
                    "browser_cer_before": o["browser_cer"], "browser_cer_after": r["browser_cer"],
                    "browser_word_recall_before": o["browser_word_recall_unordered"],
                    "browser_word_recall_after": r["browser_word_recall_unordered"],
                    "native_standard_cer": r["native_standard_cer"], "native_best_cer": r["native_best_cer"],
                    "confidence_badge_after": run["confidence_badge"].replace("Confidence: ", "").replace("%", ""),
                    "wall_s_dev_container_after": round(run["wall_ms_dev_container"] / 1000, 1)})
        print(f'{r["label"]:20} before {float(o["browser_cer"]):.4f} after {float(r["browser_cer"]):.4f}')
