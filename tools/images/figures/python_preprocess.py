#!/usr/bin/env python3
"""Raw figures for tesseractocr.org/python/ from bench/preprocess (SYNTHETIC corpus images).

Writes two composites into tools/images/raw/python/ (branded copies: tools/images/brand.py jobs/python.json):

  preprocessing-before-after.png  three damaged images, each as loaded (raw) and after one preprocessing
                                  step, with the CER and the first line pytesseract returned
  word-confidence-boxes.png       image_to_data word boxes on a faded receipt; words under conf 60 get a
                                  thick outline and their confidence, words the bench scored wrong a cross

The preprocessed pixels are re-made with bench/preprocess/run.py's own PIPELINES (deterministic). OCR text,
CER, boxes and confidences are NOT re-run: they are read from bench/preprocess/results (per_image.csv,
raw/<pipeline>/<id>.txt, raw/tsv/<id>.tsv, confidence_words.csv).

usage: python3 tools/images/figures/python_preprocess.py
"""
import csv
import importlib.util
import os
import sys

import cv2
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
BENCH = os.path.join(REPO, "bench", "preprocess")
RES = os.path.join(BENCH, "results")
OUT = os.path.join(HERE, "..", "raw", "python")
MONO = os.path.join(HERE, "..", "fonts", "JetBrainsMono-500.ttf")
MONO_B = os.path.join(HERE, "..", "fonts", "JetBrainsMono-600.ttf")
sys.path.insert(0, os.path.join(REPO, "bench", "accuracy"))
_spec = importlib.util.spec_from_file_location("pre_run", os.path.join(BENCH, "run.py"))
R = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(R)

PAPER, INK, MUTED, LINE = (245, 244, 239), (14, 17, 22), (91, 99, 114), (214, 212, 204)
BAD, GOOD, AMBER = (200, 55, 43), (77, 106, 0), (176, 112, 0)
W = 1640

ROWS = [  # (image id, after-pipeline, crop box in source pixels, title)
    ("receipt/receipt03_freemono_faded", "sauvola", (0, 0, 945, 470), "Faded thermal receipt"),
    ("degraded/austen_dejavu-serif_contrast2", "sauvola", (270, 270, 1390, 640), "Low-contrast page (ink 150 / paper 190)"),
    ("degraded/carroll_inter_noise30", "adaptive", (270, 270, 1390, 640), "Noisy page (Gaussian noise sigma 30)"),
]
LABEL = {"raw": "RAW (as loaded)", "sauvola": "SAUVOLA", "adaptive": "ADAPTIVE THRESHOLD"}


def cer_table():
    t = {}
    for r in csv.DictReader(open(os.path.join(RES, "per_image.csv"), encoding="utf-8")):
        t[(r["pipeline"], r["id"])] = float(r["cer"])
    return t


def first_line(pipe, id_):
    txt = open(os.path.join(RES, "raw", pipe, id_ + ".txt"), encoding="utf-8").read()
    for l in txt.splitlines():
        if l.strip():
            return l.strip()
    return "(empty output)"


def clip(d, s, font, maxw):
    if d.textlength(s, font=font) <= maxw:
        return s
    while s and d.textlength(s + "…", font=font) > maxw:
        s = s[:-1]
    return s + "…"


def before_after():
    cers = cer_table()
    pad, gap, colgap = 40, 46, 40
    pw = (W - 2 * pad - colgap) // 2
    f, fb, ft = ImageFont.truetype(MONO, 19), ImageFont.truetype(MONO_B, 17), ImageFont.truetype(MONO_B, 22)
    cells = []
    h = pad
    for id_, pipe, box, title in ROWS:
        a = cv2.imread(os.path.join(REPO, "corpus", id_ + ".png"), cv2.IMREAD_COLOR)
        row = []
        for p in ("raw", pipe):
            im = R.PIPELINES[p](a)
            im = cv2.cvtColor(im, cv2.COLOR_GRAY2RGB) if im.ndim == 2 else cv2.cvtColor(im, cv2.COLOR_BGR2RGB)
            pim = Image.fromarray(im).crop(box)
            pim = pim.resize((pw, round(pim.height * pw / pim.width)), Image.LANCZOS)
            row.append((p, pim, cers[(p, id_)], first_line(p, id_)))
        ph = max(c[1].height for c in row)
        cells.append((title, row, ph))
        h += 34 + 30 + ph + 12 + 30 + gap
    h += pad - gap
    can = Image.new("RGB", (W, h), PAPER)
    d = ImageDraw.Draw(can)
    y = pad
    report = []
    for i, (title, row, ph) in enumerate(cells):
        if i:
            d.line([pad, y - gap // 2, W - pad, y - gap // 2], fill=LINE)
        d.text((pad, y), title, font=ft, fill=INK)
        y += 34
        for k, (p, pim, cer, line) in enumerate(row):
            x = pad + k * (pw + colgap)
            worse = k == 1 and cer > row[0][2]
            d.text((x, y), LABEL[p], font=fb, fill=MUTED)
            tag = f"CER {cer * 100:.2f}%"
            d.text((x + pw - d.textlength(tag, font=fb), y), tag, font=fb,
                   fill=(BAD if worse else GOOD) if k == 1 else INK)
            can.paste(pim, (x, y + 30))
            d.rectangle([x - 1, y + 29, x + pw, y + 30 + pim.height], outline=LINE)
            d.text((x, y + 30 + ph + 12), clip(d, "out: " + line, f, pw), font=f, fill=INK)
            report.append((title, p, round(cer * 100, 2), line[:60]))
        y += 30 + ph + 12 + 30 + gap
    return can, report


def word_boxes(id_="receipt/receipt04_jetbrains-mono_faded", top=0, crop_h=1180):
    words = []
    for r in csv.reader(open(os.path.join(RES, "raw", "tsv", id_ + ".tsv"), encoding="utf-8"), delimiter="\t",
                        quoting=csv.QUOTE_NONE):
        if r[0] == "level" or len(r) < 12 or not r[11].strip() or float(r[10]) < 0:
            continue
        words.append((r[11], int(r[6]), int(r[7]), int(r[8]), int(r[9]), float(r[10])))
    scored = [r for r in csv.DictReader(open(os.path.join(RES, "confidence_words.csv"), encoding="utf-8")) if r["id"] == id_]
    assert len(scored) == len(words), (len(scored), len(words))
    for (t, *_), s in zip(words, scored):
        assert t == s["word"], (t, s["word"])
    src = Image.open(os.path.join(REPO, "corpus", id_ + ".png")).convert("RGB")
    sc = 1.6
    pad, legend_h = 40, 92
    im = src.crop((0, top, src.width, crop_h)).resize((round(src.width * sc), round((crop_h - top) * sc)), Image.LANCZOS)
    can = Image.new("RGB", (W, im.height + 2 * pad + legend_h), PAPER)
    ox = (W - im.width) // 2
    can.paste(im, (ox, pad))
    d = ImageDraw.Draw(can)
    fl, fs = ImageFont.truetype(MONO_B, 18), ImageFont.truetype(MONO, 17)
    stats = {"low": 0, "wrong": 0, "both": 0}
    for (t, l, tp, w, hh, c), s in zip(words, scored):
        if tp < top or tp + hh > crop_h:
            continue
        tp -= top
        x0, y0, x1, y1 = ox + l * sc - 3, pad + tp * sc - 3, ox + (l + w) * sc + 3, pad + (tp + hh) * sc + 3
        low, wrong = c < 60, s["correct"] == "0"
        stats["low"] += low
        stats["wrong"] += wrong
        stats["both"] += low and wrong
        d.rectangle([x0, y0, x1, y1], outline=AMBER if low else GOOD, width=5 if low else 2)
        if low:
            lab = f"{c:.0f}"
            tw = d.textlength(lab, font=fl)
            d.rectangle([x1 - tw - 8, y0 - 24, x1, y0], fill=AMBER)
            d.text((x1 - tw - 4, y0 - 23), lab, font=fl, fill=(255, 255, 255))
        if wrong:
            d.line([x0, y0, x1, y1], fill=BAD, width=3)
            d.line([x0, y1, x1, y0], fill=BAD, width=3)
    y = pad + im.height + 22
    d.rectangle([pad, y, pad + 40, y + 22], outline=GOOD, width=2)
    d.text((pad + 52, y), "word box, conf >= 60", font=fs, fill=INK)
    x2 = pad + 420
    d.rectangle([x2, y, x2 + 40, y + 22], outline=AMBER, width=5)
    d.text((x2 + 52, y), "conf < 60 (value shown)", font=fs, fill=INK)
    x3 = pad + 880
    d.rectangle([x3, y, x3 + 40, y + 22], outline=LINE, width=1)
    d.line([x3, y, x3 + 40, y + 22], fill=BAD, width=3)
    d.line([x3, y + 22, x3 + 40, y], fill=BAD, width=3)
    d.text((x3 + 52, y), "word read wrong (vs ground truth)", font=fs, fill=INK)
    d.text((pad, y + 40), f"pytesseract.image_to_data, Tesseract 5.5.4, eng (standard), --oem 1 --psm 3 · {id_}",
           font=fs, fill=MUTED)
    return can, stats


def main():
    os.makedirs(OUT, exist_ok=True)
    a, rep = before_after()
    a.save(os.path.join(OUT, "preprocessing-before-after.png"), optimize=True)
    print("preprocessing-before-after.png", a.size)
    for r in rep:
        print("  ", r)
    b, st = word_boxes()
    b.save(os.path.join(OUT, "word-confidence-boxes.png"), optimize=True)
    print("word-confidence-boxes.png", b.size, st)


if __name__ == "__main__":
    main()
