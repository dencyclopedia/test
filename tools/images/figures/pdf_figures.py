#!/usr/bin/env python3
"""Raw figure + chart data for tesseractocr.org/pdf/ from bench/pdf (SYNTHETIC 20-page scan).

Writes:
  tools/images/raw/pdf/text-layer-alignment.png   two text-layer overlays from the bench run, side by side:
      left  = pdf2image + pytesseract with config="--dpi 300" (crop of page 1, unscaled overlay pixels x2)
      right = the same code without --dpi (whole page 1, downscaled)
      Overlays are bench/pdf/results/overlay/*-page01-text-layer.png (run 44258321538), drawn by
      bench/pdf/run_pdf.py: red = hidden text-layer word boxes, green = ground-truth word boxes.
      Labels (page size, centre error) are read from results/methods.json, never typed.
  tools/images/figures/data/pdf-methods.jsonl     results/methods.json flattened to JSONL (for charts.py)
  tools/images/figures/data/pdf-dpi-native.jsonl  results/dpi_native.json as JSONL (+ "label")

usage: python3 tools/images/figures/pdf_figures.py
"""
import json
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
RES = os.path.join(REPO, "bench", "pdf", "results")
OUT = os.path.join(HERE, "..", "raw", "pdf")
DATA = os.path.join(HERE, "data")
MONO = os.path.join(HERE, "..", "fonts", "JetBrainsMono-500.ttf")
MONO_B = os.path.join(HERE, "..", "fonts", "JetBrainsMono-600.ttf")
PAPER, INK, MUTED = (245, 244, 239), (14, 17, 22), (91, 99, 114)
RED, GREEN = (200, 0, 0), (0, 140, 0)
W, PH = 1640, 1000  # 2x of the 820 px column; panel height


def write_jsonl(rows, name):
    os.makedirs(DATA, exist_ok=True)
    with open(os.path.join(DATA, name), "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def chart_data():
    methods = json.load(open(os.path.join(RES, "methods.json")))
    write_jsonl([{k: v for k, v in m.items() if not isinstance(v, (list, dict))} for m in methods], "pdf-methods.jsonl")
    rows = json.load(open(os.path.join(RES, "dpi_native.json")))
    for r in rows:
        r["label"] = f"{r['font_pt']} pt @ {r['scan_dpi']} DPI"
    write_jsonl([{k: v for k, v in r.items() if not isinstance(v, (list, dict))} for r in rows], "pdf-dpi-native.jsonl")
    return {m["method"]: m for m in methods}


def text_layer(m):
    by = m
    good, bad = by["pdf2image_pytesseract_dpi300"], by["pdf2image_pytesseract"]
    a = Image.open(os.path.join(RES, "overlay", "pdf2image_pytesseract_dpi300-page01-text-layer.png")).convert("RGB")
    a = a.crop((70, 70, 470, 570)).resize((800, PH), Image.LANCZOS)  # 2x of the 100-dpi overlay
    b = Image.open(os.path.join(RES, "overlay", "pdf2image_pytesseract-page01-text-layer.png")).convert("RGB")
    b = b.resize((round(b.width * PH / b.height), PH), Image.LANCZOS)
    head = 150
    im = Image.new("RGB", (W, head + PH + 70), PAPER)
    d = ImageDraw.Draw(im)
    fb, f = ImageFont.truetype(MONO_B, 26), ImageFont.truetype(MONO, 21)
    size = lambda s: s.replace(" pts", " pt")
    d.text((0, 10), 'config="--dpi 300"', font=fb, fill=INK)
    d.text((0, 52), f"page {size(good['pdf_page_size'])}", font=f, fill=MUTED)
    d.text((0, 84), f"words {good['align_centre_err_pt_median']} pt from true position (median)", font=f, fill=MUTED)
    x2 = 840
    d.text((x2, 10), "no --dpi (code as published before)", font=fb, fill=INK)
    d.text((x2, 52), f"page {size(bad['pdf_page_size'])}", font=f, fill=MUTED)
    d.text((x2, 84), "the real A4 page = green boxes, top left", font=f, fill=MUTED)
    im.paste(a, (0, head))
    im.paste(b, (x2, head))
    d.rectangle([0, head, 799, head + PH - 1], outline=(214, 212, 204), width=2)
    d.rectangle([x2, head, x2 + b.width - 1, head + PH - 1], outline=(214, 212, 204), width=2)
    y = head + PH + 24
    d.rectangle([0, y + 4, 22, y + 22], outline=RED, fill=(255, 220, 220), width=2)
    d.text((34, y), "hidden text layer (word boxes)", font=f, fill=INK)
    d.rectangle([520, y + 4, 542, y + 22], outline=GREEN, width=2)
    d.text((554, y), "ground-truth word positions", font=f, fill=INK)
    os.makedirs(OUT, exist_ok=True)
    im.save(os.path.join(OUT, "text-layer-alignment.png"), optimize=True)


if __name__ == "__main__":
    text_layer(chart_data())
    print("ok")
