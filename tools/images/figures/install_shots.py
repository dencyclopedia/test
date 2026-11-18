#!/usr/bin/env python3
"""Raw figures for tesseractocr.org/install/ from the install captures (install/windows, install/macos).

The captures themselves are never changed. This script only
  * crops console screenshots to the rows that hold text (the rest of the 1024x720 window is empty), and
  * puts two real screenshots side by side (same run, nothing redrawn),
and writes the results to tools/images/raw/install/. tools/images/brand.py (jobs/install.json) then frames,
resizes and tags them. Single wizard/dialog shots are used straight from install/ by the job file.

  installer-components-default-vs-all.png  gui-default 05 (default, 96.9 MB) | gui-all 09 (all languages, 728.7 MB)
  path-system-too-large.png                 gui-default 04-c (system Path edit) | 04-d (2047-character message box)
  cmd-not-recognized.png                    crop of gui-default windows-path-01-cmd-not-recognized.png
  cmd-working.png                           crop of gui-default windows-path-07-cmd-working.png
  wsl-ubuntu-tesseract.png                  crop of wsl/windows-wsl-ubuntu-tesseract.png

usage: python3 tools/images/figures/install_shots.py
"""
import os

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
WIN = os.path.join(REPO, "install", "windows")
OUT = os.path.join(REPO, "tools", "images", "raw", "install")
GAP = 16
BG = (11, 15, 21)


def side_by_side(a, b, name):
    A, B = Image.open(a).convert("RGB"), Image.open(b).convert("RGB")
    h = max(A.height, B.height)
    im = Image.new("RGB", (A.width + GAP + B.width, h), BG)
    im.paste(A, (0, 0))
    im.paste(B, (A.width + GAP, (h - B.height) // 2))
    im.save(os.path.join(OUT, name), optimize=True)


def crop_rows(src, name, pad=14, min_w=0):
    """Keep the window's title bar and every row down to the last line of text (+pad)."""
    im = Image.open(src).convert("RGB")
    g = im.convert("L")
    bg = g.getpixel((im.width // 2, im.height - 4))
    last = 0
    for y in range(40, im.height):
        row = [g.getpixel((x, y)) for x in range(0, im.width, 2)]
        if any(abs(v - bg) > 40 for v in row):
            last = y
    right = im.width
    if min_w:
        cols = [x for x in range(im.width) if any(abs(g.getpixel((x, y)) - bg) > 40 for y in range(40, last + 1, 2))]
        right = max(min_w, (max(cols) if cols else im.width) + pad)
        right = min(right, im.width)
    im.crop((0, 0, right, min(im.height, last + pad))).save(os.path.join(OUT, name), optimize=True)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    gd, ga = os.path.join(WIN, "gui-default"), os.path.join(WIN, "gui-all")
    side_by_side(os.path.join(gd, "windows-installer-05-components.png"),
                 os.path.join(ga, "windows-installer-09-components-additional-language-data-ticked.png"),
                 "installer-components-default-vs-all.png")
    side_by_side(os.path.join(gd, "windows-path-04-system-path-c-edit-added.png"),
                 os.path.join(gd, "windows-path-04-system-path-d-message-box.png"),
                 "path-system-too-large.png")
    crop_rows(os.path.join(gd, "windows-path-01-cmd-not-recognized.png"), "cmd-not-recognized.png", min_w=640)
    crop_rows(os.path.join(gd, "windows-path-07-cmd-working.png"), "cmd-working.png")
    crop_rows(os.path.join(WIN, "wsl", "windows-wsl-ubuntu-tesseract.png"), "wsl-ubuntu-tesseract.png")
    for f in sorted(os.listdir(OUT)):
        if f.endswith(".png"):
            print(f, Image.open(os.path.join(OUT, f)).size)
