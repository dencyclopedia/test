#!/usr/bin/env python3
"""Raw figures for tesseractocr.org/train/ from bench/train (SYNTHETIC OCR-A lines).

Writes two composites into tools/images/raw/train/ (the branded/resized copies are made by
tools/images/brand.py from jobs/train.json):

  ground-truth-pairs.png    three training lines exactly as tesstrain reads them: PNG + .gt.txt
  heldout-before-after.png  three held-out lines: ground truth, stock eng (tessdata_best) output and
                            the 300-line fine-tuned model's output, wrong characters marked

Line images are re-rendered with bench/train/make_lines.py and the same seeds as run_train.sh
(train --seed 1, heldout --n 300 --seed 2). Re-rendering is pixel-identical to the committed
sample (results/raw/sample-train-line.png). OCR text is NOT re-run: it is read from
bench/train/results/heldout.jsonl (run 44264145436). A line that is absent from a model's
'worst' list was read exactly (the list holds every wrong line when it has < 5 entries).

usage: python3 tools/images/figures/train_lines.py
"""
import difflib
import json
import os
import random
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
BENCH = os.path.join(REPO, "bench", "train")
OUT = os.path.join(HERE, "..", "raw", "train")
FONT_OCRA = os.environ.get("FONT", "/usr/share/fonts/truetype/ocr-a/OCRA.ttf")
MONO = os.path.join(HERE, "..", "fonts", "JetBrainsMono-500.ttf")
MONO_B = os.path.join(HERE, "..", "fonts", "JetBrainsMono-600.ttf")
sys.path.insert(0, BENCH)
import make_lines  # noqa: E402

PAPER, INK, MUTED, LINE = (245, 244, 239), (14, 17, 22), (91, 99, 114), (214, 212, 204)
BAD_BG, BAD_UL, GOOD = (255, 214, 208), (200, 55, 43), (77, 106, 0)
W = 1640  # 2x of the 820 px article column


def lines(split, n, seed, prefix):
    """Re-render make_lines.py output in memory: [(name, image, gt)]."""
    rnd = random.Random(seed)
    out = []
    for i, text in enumerate(make_lines.lines_from_text(split)[:n]):
        out.append((f"{prefix}-{i:05d}", make_lines.render(text, FONT_OCRA, rnd), text))
    return out


def fit(im, maxw):
    if im.width <= maxw:
        return im
    return im.resize((maxw, round(im.height * maxw / im.width)), Image.LANCZOS)


def ground_truth_pairs():
    sel = lines("train", 3, 1, "tr")
    f, fb = ImageFont.truetype(MONO, 22), ImageFont.truetype(MONO_B, 22)
    pad, gap = 40, 34
    blocks = []
    for name, im, gt in sel:
        im = fit(im.convert("RGB"), W - 2 * pad)
        blocks.append((name, im, gt))
    h = pad + sum(30 + b[1].height + 12 + 44 + gap for b in blocks) - gap + pad
    can = Image.new("RGB", (W, h), PAPER)
    d = ImageDraw.Draw(can)
    y = pad
    for name, im, gt in blocks:
        d.text((pad, y), f"{name}.png", font=fb, fill=INK)
        y += 30
        can.paste(im, (pad, y))
        d.rectangle([pad - 1, y - 1, pad + im.width, y + im.height], outline=LINE)
        y += im.height + 12
        d.rounded_rectangle([pad, y, W - pad, y + 44], radius=6, fill=(232, 230, 222))
        d.text((pad + 14, y + 10), f"{name}.gt.txt", font=fb, fill=MUTED)
        d.text((pad + 14 + d.textlength(f"{name}.gt.txt", font=fb) + 24, y + 10), gt, font=f, fill=INK)
        y += 44 + gap
    return can, [(n, g) for n, _, g in blocks]


def marked(d, x, y, ref, hyp, font, ok_col):
    """Draw hyp; characters that differ from ref get a red box + underline (not colour alone)."""
    sm = difflib.SequenceMatcher(None, ref, hyp, autojunk=False)
    bad = set()
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op in ("replace", "insert"):
            bad.update(range(j1, j2))
    for k, ch in enumerate(hyp):
        cw = d.textlength(ch, font=font)
        if k in bad:
            d.rectangle([x - 1, y - 2, x + cw + 1, y + 30], fill=BAD_BG)
            d.line([x - 1, y + 31, x + cw + 1, y + 31], fill=BAD_UL, width=3)
        d.text((x, y), ch, font=font, fill=INK if k in bad else ok_col)
        x += cw
    return len(bad) + sum(i2 - i1 for op, i1, i2, _, _ in sm.get_opcodes() if op == "delete")


def heldout_before_after(gt_wanted):
    res = {}
    for l in open(os.path.join(BENCH, "results", "heldout.jsonl"), encoding="utf-8"):
        r = json.loads(l)
        if r["label"].startswith("base eng tessdata_best") or r["label"].startswith("fine-tuned 300 lines, final"):
            res["stock" if r["label"].startswith("base") else "ft300"] = r
    assert len(res["ft300"]["worst"]) < 5, "worst list may be truncated; cannot infer exact reads"
    sel = [x for x in lines("heldout", 300, 2, "ho") if x[2] in gt_wanted]
    f = ImageFont.truetype(MONO, 25)
    fl = ImageFont.truetype(MONO_B, 17)
    pad, gap, row = 40, 40, 40
    labw = 300
    h = 2 * pad
    blocks = []
    for name, im, gt in sel:
        im = fit(im.convert("RGB"), W - 2 * pad)
        stock = next(w["ocr"] for w in res["stock"]["worst"] if w["gt"] == gt)
        ft = next((w["ocr"] for w in res["ft300"]["worst"] if w["gt"] == gt), gt)
        blocks.append((name, im, gt, stock, ft))
        h += im.height + 14 + 3 * row + gap
    h -= gap
    can = Image.new("RGB", (W, h), PAPER)
    d = ImageDraw.Draw(can)
    y = pad
    report = []
    for bi, (name, im, gt, stock, ft) in enumerate(blocks):
        if bi:
            d.line([pad, y - gap // 2, W - pad, y - gap // 2], fill=LINE, width=1)
        can.paste(im, (pad, y))
        d.rectangle([pad - 1, y - 1, pad + im.width, y + im.height], outline=LINE)
        y += im.height + 14
        for lab, txt, col in (("GROUND TRUTH", gt, INK), ("STOCK ENG (BEST)", stock, INK), ("FINE-TUNED · 300", ft, GOOD)):
            d.text((pad, y + 9), lab, font=fl, fill=MUTED)
            n = marked(d, pad + labw, y + 2, gt, txt, f, col)
            if lab != "GROUND TRUTH":
                tag = f"{n} wrong" if n else "exact"
                tw = d.textlength(tag, font=fl)
                d.text((W - pad - tw, y + 9), tag, font=fl, fill=BAD_UL if n else GOOD)
            report.append((name, lab, txt, n))
            y += row
        y += gap
    return can, report


def main():
    os.makedirs(OUT, exist_ok=True)
    a, pairs = ground_truth_pairs()
    a.save(os.path.join(OUT, "ground-truth-pairs.png"), optimize=True)
    print("ground-truth-pairs.png", a.size, pairs)
    b, rep = heldout_before_after({
        '"Your humility, Mr. Bingley," said Elizabeth,',
        "yours till I am out of the room, I shall be very",
        '"Oh!" said she, "I heard you before, but I could',
    })
    b.save(os.path.join(OUT, "heldout-before-after.png"), optimize=True)
    print("heldout-before-after.png", b.size)
    for r in rep:
        print("  ", r)


if __name__ == "__main__":
    main()
