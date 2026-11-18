#!/usr/bin/env python3
"""Word-confidence study: are Tesseract's word confidences useful for flagging wrong words?

Engine: pytesseract.image_to_data -> Tesseract 5.5.4, tessdata (standard) eng, --oem 1 --psm 3, no preprocessing.
Images: corpus clean (90), degraded (80) and receipt (16) sets.

Alignment method (documented in README.md):
  1. Ground truth and OCR are normalised as in tools/metrics.py (NFC, whitespace collapsed) and split on spaces.
  2. OCR words are taken in image_to_data order (block, paragraph, line, word), skipping conf == -1 rows and empty text.
  3. difflib.SequenceMatcher(autojunk=False) aligns the two word sequences; an OCR word is CORRECT when it lies in a
     matching block (identical to the aligned ground-truth word, case and punctuation included), otherwise INCORRECT.
Outputs: results/confidence_words.csv (every word), results/confidence_hist.csv (5-point bins),
         results/confidence_thresholds.csv (keep words with conf >= t: precision, recall of correct words, share of
         wrong words removed), results/raw/tsv/<id>.tsv
Usage: python3 bench/preprocess/confidence.py
"""
import difflib
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pytesseract

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "accuracy"))
import benchlib as B  # noqa: E402

RES = HERE / "results"
CONFIG = f"--tessdata-dir {B.MODELS['standard']} --oem 1 --psm 3"
pytesseract.pytesseract.tesseract_cmd = B.TESS["5.5.4"]


def work(e):
    os.environ["OMP_THREAD_LIMIT"] = "1"
    tsv = pytesseract.image_to_data(str(B.CORPUS / e["image"]), config=CONFIG)
    p = RES / "raw" / "tsv" / (e["id"] + ".tsv")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(tsv, encoding="utf-8")
    lines = tsv.splitlines()
    head = lines[0].split("\t")
    words = []
    for l in lines[1:]:
        f = dict(zip(head, l.split("\t")))
        t = B.metrics.normalize(f.get("text", ""))
        if not t or float(f["conf"]) < 0:
            continue
        for part in t.split(" "):
            words.append((part, float(f["conf"])))
    truth = B.metrics.normalize(B.gt(e)).split(" ")
    sm = difflib.SequenceMatcher(None, truth, [w for w, _ in words], autojunk=False)
    ok = set()
    for blk in sm.get_matching_blocks():
        ok.update(range(blk.b, blk.b + blk.size))
    return [dict(id=e["id"], set=e["set"], level=e.get("level", ""), word=w, conf=c, correct=int(i in ok))
            for i, (w, c) in enumerate(words)]


def main():
    imgs = B.manifest(set=("clean", "degraded", "receipt"))
    rows = []
    with ProcessPoolExecutor(B.WORKERS) as ex:
        for r in ex.map(work, imgs, chunksize=1):
            rows.extend(r)
    B.write_csv(RES / "confidence_words.csv", rows)
    hist = []
    for lo in range(0, 100, 5):
        sel = [r for r in rows if lo <= r["conf"] < lo + 5 or (lo == 95 and r["conf"] == 100)]
        hist.append(dict(bin=f"{lo}-{lo + 5}", correct=sum(r["correct"] for r in sel),
                         incorrect=sum(1 - r["correct"] for r in sel)))
    B.write_csv(RES / "confidence_hist.csv", hist)
    nc = sum(r["correct"] for r in rows)
    ni = len(rows) - nc
    th = []
    for t in range(0, 100, 5):
        kept = [r for r in rows if r["conf"] >= t]
        kc = sum(r["correct"] for r in kept)
        ki = len(kept) - kc
        th.append(dict(threshold=t, kept_words=len(kept), precision_of_kept=kc / max(len(kept), 1),
                       correct_words_kept=kc / max(nc, 1), wrong_words_removed=(ni - ki) / max(ni, 1),
                       balanced_accuracy=(kc / max(nc, 1) + (ni - ki) / max(ni, 1)) / 2))
    B.write_csv(RES / "confidence_thresholds.csv", th)
    best = max(th, key=lambda r: r["balanced_accuracy"])
    print("words", len(rows), "correct", nc, "incorrect", ni, "best balanced-accuracy threshold", best)
    B.write_meta(RES / "meta_confidence.json", {"pytesseract_config": CONFIG},
                 {"images": len(imgs), "words": len(rows), "correct": nc, "incorrect": ni,
                  "threshold_max_balanced_accuracy": best})


if __name__ == "__main__":
    main()
