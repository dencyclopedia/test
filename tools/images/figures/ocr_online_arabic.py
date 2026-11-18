#!/usr/bin/env python3
"""Raw composite for tesseractocr.org/ocr-online/: the tool's output on the SYNTHETIC Arabic UDHR test page
before and after the RTL fix, side by side. Inputs are the untouched Playwright captures written by
ocr_online_capture.js (raw/ocr-online/arabic-output-{before,after}-rtl-fix.png); the CER labels are read from
bench/ocr-online/results-2026-11-18-rtl-fix/before_after.csv, never typed.
usage: python3 tools/images/figures/ocr_online_arabic.py  -> raw/ocr-online/arabic-output-before-after-rtl-fix.png
"""
import csv
import os
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
RAW = os.path.join(HERE, "..", "raw", "ocr-online")
row = next(r for r in csv.DictReader(open(os.path.join(REPO, "bench", "ocr-online", "results-2026-11-18-rtl-fix", "before_after.csv"), encoding="utf-8"))
           if r["lang"] == "ara")
labels = [f"Before the fix · CER {float(row['browser_cer_before']) * 100:.2f}%",
          f"After the fix · CER {float(row['browser_cer_after']) * 100:.2f}%"]
shots = [Image.open(os.path.join(RAW, f"arabic-output-{t}-rtl-fix.png")).convert("RGB") for t in ("before", "after")]
# keep the header + text box, drop the action buttons below it (identical in both)
crop_h = min(s.height for s in shots) - 470
shots = [s.crop((0, 0, s.width, crop_h)) for s in shots]
font = ImageFont.truetype(os.path.join(HERE, "..", "fonts", "JetBrainsMono-600.ttf"), 30)
gap, head = 40, 70
W = sum(s.width for s in shots) + gap
img = Image.new("RGB", (W, crop_h + head), (245, 244, 239))
d = ImageDraw.Draw(img)
x = 0
for s, lab, col in zip(shots, labels, [(200, 55, 43), (77, 106, 0)]):
    d.text((x + 34, 18), lab, font=font, fill=col)
    img.paste(s, (x, head))
    x += s.width + gap
img.save(os.path.join(RAW, "arabic-output-before-after-rtl-fix.png"))
print(labels, img.size)
