"""Generate tesstrain ground truth: one PNG per text line + matching .gt.txt (SYNTHETIC).

usage: python3 make_lines.py OUTDIR --font PATH --split train|heldout [--n N] [--seed S]
Text: Pride and Prejudice ch.1-12 (public domain, bench/pdf/text/). Lines from paragraphs 0..79% go to
'train', the last 20% of paragraphs to 'heldout', so held-out lines are text the model never saw.
Each line is rendered at 300 DPI-equivalent size (12 pt), then lightly degraded (blur, noise, skew).
"""
import argparse, os, random, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
TEXT = os.path.join(HERE, "..", "pdf", "text", "pride-and-prejudice-ch01-12.txt")


def lines_from_text(split, maxlen=48):
    paras = [" ".join(p.split()) for p in open(TEXT, encoding="utf-8").read().split("\n\n") if p.strip()]
    cut = int(len(paras) * 0.8)
    paras = paras[:cut] if split == "train" else paras[cut:]
    out = []
    for p in paras:
        cur = ""
        for w in p.split(" "):
            if len(cur) + 1 + len(w) > maxlen and cur:
                out.append(cur); cur = w
            else:
                cur = (cur + " " + w).strip()
        if cur:
            out.append(cur)
    # OCR-A has no curly quotes (U+201C/U+201D); use the ASCII quote so every glyph exists in the font
    return [l.replace("\u201c", '"').replace("\u201d", '"') for l in out if len(l) >= 8]


def render(text, font, rnd, px=50):
    f = ImageFont.truetype(font, px)
    l, t, r, b = f.getbbox(text)
    pad = 12
    im = Image.new("L", (r - l + 2 * pad, b - t + 2 * pad), 255)
    ImageDraw.Draw(im).text((pad - l, pad - t), text, font=f, fill=0)
    im = im.rotate(rnd.uniform(-0.8, 0.8), resample=Image.BICUBIC, expand=True, fillcolor=255)
    im = im.filter(ImageFilter.GaussianBlur(rnd.uniform(0.4, 1.0)))
    a = np.asarray(im).astype(np.float32)
    a = rnd.uniform(15, 45) + a / 255 * (rnd.uniform(225, 248) - 30)
    a += np.random.default_rng(rnd.randrange(1 << 30)).normal(0, rnd.uniform(3, 9), a.shape)
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out"); ap.add_argument("--font", required=True)
    ap.add_argument("--split", default="train"); ap.add_argument("--n", type=int, default=0)
    ap.add_argument("--seed", type=int, default=1); ap.add_argument("--prefix", default="line")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    rnd = random.Random(a.seed)
    lines = lines_from_text(a.split)
    if a.n:
        lines = lines[:a.n]
    for i, text in enumerate(lines):
        base = os.path.join(a.out, f"{a.prefix}-{i:05d}")
        render(text, a.font, rnd).save(base + ".png", dpi=(300, 300))
        open(base + ".gt.txt", "w", encoding="utf-8").write(text + "\n")
    print(f"{len(lines)} lines -> {a.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
