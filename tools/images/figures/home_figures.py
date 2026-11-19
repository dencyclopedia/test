#!/usr/bin/env python3
"""Raw figures for the tesseractocr.org homepage (/), built from existing bench results (all SYNTHETIC images).

Writes (tools/images/raw/home/):
  receipt-psm3-vs-psm6.png     corpus/receipt/receipt03_freemono.png + Tesseract 5.5.4 output with --psm 3 and
                               --psm 6, read verbatim from bench/psm/results/raw/psm{3,6}/receipt/*.txt;
                               CER from bench/psm/results/per_image.csv.
  screenshot-psm3-vs-psm6.png  corpus/screenshot/inbox_light_2x.png (shown) + the bench's OCR of the 1x capture
                               (bench/psm raw psm3/psm6 inbox_light_1x.txt); CER from per_image.csv.
  scanned-page-text-layer.png  crop of bench/pdf/results/overlay/tesseract_cli_jpeg-page01-text-layer.png
                               (run 44258321538: red = hidden text-layer words, green = ground truth); labels
                               from bench/pdf/results/methods.json.
Nothing is retyped: every OCR line and number is read from the result files.
usage: python3 tools/images/figures/home_figures.py
"""
import csv
import json
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
PSM = os.path.join(REPO, "bench", "psm", "results")
PDF = os.path.join(REPO, "bench", "pdf", "results")
OUT = os.path.join(HERE, "..", "raw", "home")
MONO = os.path.join(HERE, "..", "fonts", "JetBrainsMono-500.ttf")
MONO_B = os.path.join(HERE, "..", "fonts", "JetBrainsMono-600.ttf")
PAPER, INK, MUTED, LINE = (245, 244, 239), (14, 17, 22), (91, 99, 114), (214, 212, 204)
BAD, GOOD, PANEL = (200, 55, 43), (77, 106, 0), (255, 255, 255)
W = 1640


def cer(psm, img_id):
    for r in csv.DictReader(open(os.path.join(PSM, "per_image.csv"), encoding="utf-8")):
        if r["psm"] == str(psm) and r["id"] == img_id:
            return float(r["cer"])
    raise SystemExit(f"no row for psm {psm} {img_id}")


def out_text(psm, kind, name):
    return open(os.path.join(PSM, "raw", f"psm{psm}", kind, name + ".txt"), encoding="utf-8").read().rstrip("\n").split("\n")


def save(im, name):
    """28 px paper margin around the composite, then save."""
    m = 28
    c = Image.new("RGB", (im.width + 2 * m, im.height + 2 * m), PAPER)
    c.paste(im, (m, m))
    c.save(os.path.join(OUT, name), optimize=True)


def hgt(lines, lh):
    return sum(lh if l.strip() else lh // 2 for l in lines)


def panel(d, x, y, w, h, title, sub, lines, colour, font, lh):
    d.rectangle([x, y, x + w - 1, y + h - 1], fill=PANEL, outline=LINE, width=2)
    d.text((x + 22, y + 18), title, font=ImageFont.truetype(MONO_B, 26), fill=INK)
    d.text((x + 22, y + 56), sub, font=ImageFont.truetype(MONO_B, 24), fill=colour)
    ty = y + 104
    for ln in lines:  # blank output lines are kept, at half height
        d.text((x + 22, ty), ln, font=font, fill=INK)
        ty += lh if ln.strip() else lh // 2


def receipt():
    img_id, name = "receipt/receipt03_freemono", "receipt03_freemono"
    p3, p6 = out_text(3, "receipt", name), out_text(6, "receipt", name)
    c3, c6 = cer(3, img_id), cer(6, img_id)
    src = Image.open(os.path.join(REPO, "corpus", "receipt", name + ".png")).convert("RGB")
    iw = 500
    src = src.resize((iw, round(src.height * iw / src.width)), Image.LANCZOS)
    f, lh = ImageFont.truetype(MONO, 21), 26
    ph = 104 + max(hgt(p3, lh), hgt(p6, lh)) + 24
    head = 70
    h = head + max(ph, src.height)
    im = Image.new("RGB", (W, h), PAPER)
    d = ImageDraw.Draw(im)
    d.text((0, 14), "input (synthetic receipt)", font=ImageFont.truetype(MONO_B, 26), fill=INK)
    im.paste(src, (0, head))
    d.rectangle([0, head, iw - 1, head + src.height - 1], outline=LINE, width=2)
    pw = (W - iw - 2 * 30) // 2
    panel(d, iw + 30, head, pw, ph, "tesseract --psm 3", f"default · CER {c3 * 100:.2f}%", p3, BAD, f, lh)
    panel(d, iw + 60 + pw, head, pw, ph, "tesseract --psm 6", f"CER {c6 * 100:.2f}%", p6, GOOD, f, lh)
    save(im, "receipt-psm3-vs-psm6.png")
    return c3, c6


def screenshot():
    img_id, name = "screenshot/inbox_light_1x", "inbox_light_1x"
    p3, p6 = out_text(3, "screenshot", name), out_text(6, "screenshot", name)
    c3, c6 = cer(3, img_id), cer(6, img_id)
    src = Image.open(os.path.join(REPO, "corpus", "screenshot", "inbox_light_2x.png")).convert("RGB")
    src = src.crop((0, 0, src.width, 640))  # the capture's empty lower part is cropped off (nothing OCR'd there)
    src = src.resize((W, round(src.height * W / src.width)), Image.LANCZOS)
    f, lh = ImageFont.truetype(MONO, 19), 25
    pw = (W - 30) // 2
    ph = 104 + lh * max(len(p3), len(p6)) + 24
    # psm 6 lines are long: wrap at the panel width
    maxc = (pw - 44) // 11
    wrap6 = []
    for ln in p6:
        while len(ln) > maxc:
            cut = ln.rfind(" ", 0, maxc)
            wrap6.append(ln[:cut])
            ln = "  " + ln[cut + 1:]
        wrap6.append(ln)
    ph = 104 + max(hgt(p3, lh), hgt(wrap6, lh)) + 24
    head = 60
    h = head + src.height + 30 + ph
    im = Image.new("RGB", (W, h), PAPER)
    d = ImageDraw.Draw(im)
    d.text((0, 12), "input (synthetic UI screenshot, light theme; empty lower part cropped)", font=ImageFont.truetype(MONO_B, 26), fill=INK)
    im.paste(src, (0, head))
    d.rectangle([0, head, W - 1, head + src.height - 1], outline=LINE, width=2)
    y = head + src.height + 30
    panel(d, 0, y, pw, ph, "tesseract --psm 3", f"default · CER {c3 * 100:.2f}%", p3, BAD, f, lh)
    panel(d, pw + 30, y, pw, ph, "tesseract --psm 6", f"CER {c6 * 100:.2f}%", wrap6, GOOD, f, lh)
    save(im, "screenshot-psm3-vs-psm6.png")
    return c3, c6


def text_layer():
    m = {r["method"]: r for r in json.load(open(os.path.join(PDF, "methods.json"), encoding="utf-8"))}["tesseract_cli_jpeg"]
    ov = Image.open(os.path.join(PDF, "overlay", "tesseract_cli_jpeg-page01-text-layer.png")).convert("RGB")
    crop = ov.crop((86, 92, 86 + 740, 92 + 410)).resize((W - 160, round(410 * (W - 160) / 740)), Image.LANCZOS)
    head = 140
    h = head + crop.height + 80
    im = Image.new("RGB", (W, h), PAPER)
    d = ImageDraw.Draw(im)
    fb, f = ImageFont.truetype(MONO_B, 26), ImageFont.truetype(MONO, 22)
    d.text((0, 10), "pdftoppm -r 300 -jpeg, then: tesseract list.txt out -l eng pdf", font=fb, fill=INK)
    d.text((0, 54), f"{m['pdf_pages']} pages in {m['median_s']:.1f} s · text layer CER {m['cer_doc'] * 100:.3f}% · "
                    f"words {m['align_centre_err_pt_median']:.2f} pt from their true position (median)", font=f, fill=MUTED)
    d.text((0, 90), "page 1 (synthetic scan), top", font=f, fill=MUTED)
    im.paste(crop, (80, head))
    d.rectangle([80, head, 80 + crop.width - 1, head + crop.height - 1], outline=LINE, width=2)
    y = head + crop.height + 26
    d.rectangle([80, y + 4, 102, y + 22], outline=(200, 0, 0), fill=(255, 220, 220), width=2)
    d.text((114, y), "hidden text layer written by Tesseract", font=f, fill=INK)
    d.rectangle([760, y + 4, 782, y + 22], outline=(0, 140, 0), width=2)
    d.text((794, y), "ground-truth word positions", font=f, fill=INK)
    save(im, "scanned-page-text-layer.png")
    return m


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    print("receipt", receipt())
    print("screenshot", screenshot())
    m = text_layer()
    print("pdf", m["median_s"], m["cer_doc"], m["align_centre_err_pt_median"])
