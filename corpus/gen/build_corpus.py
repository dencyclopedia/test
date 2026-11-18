#!/usr/bin/env python3
"""Build the OCR test corpus (everything except the Playwright screenshots) and corpus/manifest.json.

Prerequisites: python3 corpus/gen/fetch_sources.py   (texts are committed; fonts are fetched)
               node corpus/gen/screenshots.js          (optional; adds the 'screenshot' set)
Usage:         python3 corpus/gen/build_corpus.py

Deterministic: every random choice comes from a seed derived from the image id (crc32).
"""
import hashlib
import json
import random
import zlib
from pathlib import Path

import numpy as np
import PIL
import cv2
from PIL import Image, ImageDraw

import render as R

HERE = Path(__file__).resolve().parent
CORPUS = HERE.parent
TEXTS = CORPUS / "texts"
MANIFEST = []

GENERATOR = {"script": "corpus/gen/build_corpus.py", "pillow": PIL.__version__, "numpy": np.__version__,
             "opencv": cv2.__version__}


def seed_for(id_):
    return zlib.crc32(id_.encode()) & 0x7FFFFFFF


def text(name):
    return (TEXTS / name).read_text(encoding="utf-8")


def save(id_, img_or_bytes, gt, ext="png", dpi=300, **meta):
    path = CORPUS / f"{id_}.{ext}"
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(img_or_bytes, bytes):
        path.write_bytes(img_or_bytes)
        w, h = Image.open(path).size
    else:
        img = img_or_bytes if isinstance(img_or_bytes, Image.Image) else Image.fromarray(img_or_bytes)
        img.save(path, dpi=(dpi, dpi), optimize=True)
        w, h = img.size
    gt_path = CORPUS / f"{id_}.gt.txt"
    gt_path.write_text(gt, encoding="utf-8")
    entry = {"id": id_, "image": f"{id_}.{ext}", "gt": f"{id_}.gt.txt", "width": w, "height": h, "dpi": dpi,
             "synthetic": True}
    entry.update(meta)
    entry["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    MANIFEST.append(entry)


# ------------------------------------------------------------------ clean
CLEAN_PASSAGES = ["austen", "doyle", "carroll"]
CLEAN_FONTS = ["dejavu-serif", "caladea", "carlito", "inter", "dejavu-mono", "courier10"]
DPIS = [70, 100, 150, 200, 300, 400, 600]
SMALL_FONTS = ["dejavu-serif", "carlito", "dejavu-mono"]  # 8 pt series


def build_clean():
    for p in CLEAN_PASSAGES:
        for f in CLEAN_FONTS:
            for dpi in DPIS:
                img, gt, subs = R.render_page(text(f"{p}.page.txt"), f, 12, dpi)
                save(f"clean/{p}_{f}_{dpi}", img, gt, dpi=dpi, set="clean", lang="eng",
                     source=f"gutenberg:{p}", font=R.FONTS[f][1], font_class=R.FONTS[f][2], size_pt=12,
                     degradation=None, text_substitutions=subs or None)
        for f in SMALL_FONTS:
            for dpi in DPIS:
                img, gt, subs = R.render_page(text(f"{p}.page.txt"), f, 8, dpi)
                save(f"clean/{p}_{f}_8pt_{dpi}", img, gt, dpi=dpi, set="clean", lang="eng",
                     source=f"gutenberg:{p}", font=R.FONTS[f][1], font_class=R.FONTS[f][2], size_pt=8,
                     degradation=None, text_substitutions=subs or None)


# ------------------------------------------------------------------ degraded
DEGRADED_BASES = [("austen", "dejavu-serif"), ("doyle", "carlito"), ("shelley", "courier10"), ("carroll", "inter")]
DEGRADATIONS = (
    [("none", {})]
    + [(f"blur{s}", {"type": "gaussian_blur", "sigma_px": s}) for s in (1, 2, 3)]
    + [(f"noise{s}", {"type": "gaussian_noise", "sigma": s}) for s in (15, 30, 50)]
    + [(f"jpeg{q}", {"type": "jpeg", "quality": q}) for q in (90, 70, 50, 30)]
    + [(f"skew{d}", {"type": "skew", "degrees": d}) for d in (1, 3, 5)]
    + [("light50", {"type": "lighting_gradient", "strength": 0.5}),
       ("light75", {"type": "lighting_gradient", "strength": 0.75})]
    + [("contrast1", {"type": "low_contrast", "ink": 100, "paper": 190}),
       ("contrast2", {"type": "low_contrast", "ink": 150, "paper": 190})]
    + [("phone1", {"type": "phone_photo", "level": 1}), ("phone2", {"type": "phone_photo", "level": 2})]
)


def apply_degradation(a, d, seed):
    t = d.get("type")
    ext, params = "png", dict(d)
    if t is None:
        out = a
    elif t == "gaussian_blur":
        out = R.gaussian_blur(a, d["sigma_px"])
    elif t == "gaussian_noise":
        out = R.gaussian_noise(a, d["sigma"], seed)
    elif t == "jpeg":
        out, ext = R.jpeg_bytes(a, d["quality"]), "jpg"
    elif t == "skew":
        out = R.skew(a, d["degrees"])
    elif t == "lighting_gradient":
        out = R.lighting_gradient(a, d["strength"])
    elif t == "low_contrast":
        out = R.low_contrast(a, d["ink"], d["paper"])
    elif t == "phone_photo":
        out, p = R.phone_photo(a, d["level"], seed)
        params.update(p)
        ext = "jpg"
    else:
        raise ValueError(t)
    return out, ext, params


def build_degraded():
    for p, f in DEGRADED_BASES:
        img, gt, subs = R.render_page(text(f"{p}.half.txt"), f, 12, 300)
        a = np.asarray(img)
        for name, d in DEGRADATIONS:
            id_ = f"degraded/{p}_{f}_{name}"
            s = seed_for(id_)
            out, ext, params = apply_degradation(a, d, s)
            save(id_, out, gt, ext=ext, dpi=300, set="degraded", lang="eng", source=f"gutenberg:{p}",
                 font=R.FONTS[f][1], font_class=R.FONTS[f][2], size_pt=12, base=f"{p}_{f}", level=name,
                 degradation=params or None, seed=s if d.get("type") in ("gaussian_noise", "phone_photo") else None,
                 text_substitutions=subs or None)


# ------------------------------------------------------------------ receipts
STORES = [("MAPLE ROW MARKET", "12 Example Street, Sampletown"), ("NORTHFIELD CORNER SHOP", "4 Placeholder Ave, Testville"),
          ("BLUE KETTLE CAFE", "88 Sample Road, Demoford"), ("OAK AND IRON HARDWARE", "301 Fictional Way, Mockbury"),
          ("GREEN LEAF PHARMACY", "7 Illustrative Lane, Specimen City")]
ITEMS = [("Whole Milk 1L", 1.29), ("Sourdough Loaf", 3.45), ("Free Range Eggs x12", 3.99), ("Bananas", 0.89),
         ("Cheddar 400g", 4.25), ("Orange Juice 1.5L", 2.79), ("Coffee Beans 500g", 8.99), ("Pasta Fusilli", 1.15),
         ("Tomato Passata", 0.95), ("Olive Oil 750ml", 6.49), ("Greek Yoghurt", 2.10), ("Dark Chocolate 85%", 2.35),
         ("Basmati Rice 2kg", 4.80), ("Paper Towels x4", 3.60), ("Dish Soap", 1.99), ("AA Batteries x8", 7.49),
         ("Cappuccino", 3.20), ("Croissant", 2.40), ("Flat White", 3.40), ("Blueberry Muffin", 2.95),
         ("Wood Screws 4x40", 5.75), ("Masking Tape", 2.25), ("Paint Brush 50mm", 4.10), ("Ibuprofen 200mg", 2.49),
         ("Vitamin D3", 6.95), ("Hand Cream 75ml", 4.50), ("Sparkling Water", 0.65), ("Apples 1kg", 2.20)]
RECEIPT_FONTS = ["dejavu-mono", "courier10", "freemono", "jetbrains-mono", "carlito", "inter", "dejavu-sans",
                 "dejavu-mono", "courier10", "freemono"]


def receipt_lines(rng, i):
    store, addr = STORES[i % len(STORES)]
    lines = [("C", store), ("C", addr), ("C", f"Tel 000-555-{rng.randint(1000, 9999)}"), ("B", ""),
             ("LR", (f"Date 2026-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}", f"{rng.randint(7, 21):02d}:{rng.randint(0, 59):02d}")),
             ("LR", (f"Receipt #{rng.randint(10000, 99999)}", f"Till {rng.randint(1, 9)}")), ("B", "")]
    total = 0.0
    for name, price in rng.sample(ITEMS, rng.randint(5, 11)):
        q = rng.choice([1, 1, 1, 2, 3])
        amt = round(q * price, 2)
        total += amt
        if q > 1:
            lines.append(("L", name))
            lines.append(("LR", (f"  {q} x {price:.2f}", f"{amt:.2f}")))
        else:
            lines.append(("LR", (name, f"{amt:.2f}")))
    tax = round(total * 0.2 / 1.2, 2)
    lines += [("B", ""), ("LR", ("SUBTOTAL", f"{total:.2f}")), ("LR", ("VAT 20% incl.", f"{tax:.2f}")),
              ("LR", ("TOTAL", f"{total:.2f}")), ("B", ""),
              ("LR", (rng.choice(["CARD", "CASH", "DEBIT"]), f"{total:.2f}")), ("B", ""),
              ("C", "Thank you for shopping with us"), ("C", "Sample receipt - not a real store")]
    return lines


def render_receipt(lines, font_key, dpi=300, width_mm=80, size_pt=8.5):
    px = round(size_pt / 72 * dpi)
    font = R.load_font(font_key, px)
    W = round(width_mm / 25.4 * dpi)
    m = round(4 / 25.4 * dpi)
    lh = round(px * 1.35)
    H = 2 * m + lh * len(lines)
    img = Image.new("L", (W, H), 255)
    d = ImageDraw.Draw(img)
    gt, y = [], m
    for kind, content in lines:
        if kind == "C":
            w = font.getlength(content)
            d.text(((W - w) / 2, y), content, font=font, fill=0)
            gt.append(content)
        elif kind == "L":
            d.text((m, y), content, font=font, fill=0)
            gt.append(content)
        elif kind == "LR":
            l, r = content
            d.text((m, y), l, font=font, fill=0)
            d.text((W - m - font.getlength(r), y), r, font=font, fill=0)
            gt.append(f"{l} {r}")
        y += lh
    return img, "\n".join(x for x in gt if x) + "\n"


def build_receipts():
    for i, f in enumerate(RECEIPT_FONTS):
        rng = random.Random(seed_for(f"receipt/{i}"))
        lines = receipt_lines(rng, i)
        img, gt = render_receipt(lines, f)
        id_ = f"receipt/receipt{i + 1:02d}_{f}"
        save(id_, img, gt, set="receipt", lang="eng", source="generated (seeded)", font=R.FONTS[f][1],
             font_class=R.FONTS[f][2], size_pt=8.5, paper_width_mm=80, degradation=None, seed=seed_for(f"receipt/{i}"))
        a = np.asarray(img)
        if i < 4:  # faded thermal paper: low contrast + blur + noise
            s = seed_for(id_ + "/faded")
            out = R.gaussian_noise(R.gaussian_blur(R.low_contrast(a, 120, 225), 0.8), 10, s)
            save(id_ + "_faded", out, gt, set="receipt", lang="eng", source="generated (seeded)", font=R.FONTS[f][1],
                 font_class=R.FONTS[f][2], size_pt=8.5, paper_width_mm=80, seed=s,
                 degradation={"type": "faded_thermal", "ink": 120, "paper": 225, "blur_sigma_px": 0.8, "noise_sigma": 10})
        if i in (4, 5):
            s = seed_for(id_ + "/phone")
            jb, params = R.phone_photo(a, 1, s)
            save(id_ + "_phone1", jb, gt, ext="jpg", set="receipt", lang="eng", source="generated (seeded)",
                 font=R.FONTS[f][1], font_class=R.FONTS[f][2], size_pt=8.5, paper_width_mm=80, seed=s,
                 degradation=dict(type="phone_photo", level=1, **params))


# ------------------------------------------------------------------ lines, words, sparse labels, layouts
LINE_SAMPLES = [
    ("dejavu-serif", "It is a truth universally acknowledged, that a single man"),
    ("carlito", "Invoice INV-2026-0418 is due on 30 November 2026."),
    ("inter", "Call +1 555 0142 or email support@example.com"),
    ("courier10", "ERROR 0x80070005: Access is denied. (code 5)"),
    ("caladea", "The quick brown fox jumps over the lazy dog."),
    ("jetbrains-mono", "tesseract scan.png out --psm 7 -l eng"),
    ("freesans", "Total amount payable: $1,284.50 (incl. tax)"),
    ("charter", "Alice was beginning to get very tired of sitting"),
]
WORD_SAMPLES = [("dejavu-serif", "Netherfield"), ("carlito", "INVOICE"), ("inter", "Settings"), ("courier10", "0x7FFF"),
                ("caladea", "acknowledged"), ("jetbrains-mono", "tessdata"), ("freesans", "$42.99"),
                ("charter", "Wonderland"), ("dejavu-sans", "2026-11-18"), ("freemono", "SKU-48213")]


def render_snippet(s, font_key, size_pt=14, dpi=300, pad_px=40):
    px = round(size_pt / 72 * dpi)
    font = R.load_font(font_key, px)
    x0, y0, x1, y1 = font.getbbox(s)
    img = Image.new("L", (x1 - x0 + 2 * pad_px, y1 - y0 + 2 * pad_px), 255)
    ImageDraw.Draw(img).text((pad_px - x0, pad_px - y0), s, font=font, fill=0)
    return img


SPARSE_LABELS = [
    # (font, canvas inches, [(x_in, y_in, size_pt, text)]) -- ground truth is sorted top-to-bottom, left-to-right
    ("dejavu-sans", (4.0, 6.0), [(0.3, 0.3, 9, "FROM:"), (0.3, 0.55, 9, "Sample Sender Ltd"), (0.3, 0.75, 9, "1 Origin Road"),
                                 (2.6, 0.3, 14, "PRIORITY"), (0.3, 1.6, 11, "SHIP TO:"), (0.6, 1.95, 13, "J. Example"),
                                 (0.6, 2.25, 13, "42 Destination Street"), (0.6, 2.55, 13, "Testville TV1 2AB"),
                                 (0.3, 4.3, 10, "WEIGHT 2.4 KG"), (2.4, 4.3, 10, "PKG 1 OF 2"),
                                 (0.3, 5.3, 12, "TRACKING 1Z 999 AA1 01 2345 6784")]),
    ("inter", (5.0, 3.0), [(0.3, 0.3, 16, "Organic Rolled Oats"), (0.3, 0.75, 10, "Net wt 500 g"),
                           (3.4, 0.75, 10, "Best before 03/2027"), (0.3, 1.9, 9, "Store in a cool dry place"),
                           (3.6, 2.4, 18, "$3.49")]),
    ("carlito", (6.0, 4.0), [(0.4, 0.4, 20, "Meeting Room B"), (0.4, 1.4, 12, "10:00 Design review"),
                             (0.4, 1.8, 12, "13:30 Budget sync"), (0.4, 2.2, 12, "16:00 Free"), (4.3, 3.4, 9, "Floor 3")]),
    ("courier10", (4.0, 2.5), [(0.2, 0.2, 10, "ASSET TAG"), (0.2, 0.6, 16, "IT-004817"), (0.2, 1.5, 8, "Property of Example Org"),
                               (2.6, 2.0, 8, "S/N 7Q2K9X")]),
]


def build_lines_words_sparse_layout():
    for i, (f, s) in enumerate(LINE_SAMPLES):
        txt, subs = R.fit_text_to_font(s, f, R.load_font(f, 40))
        save(f"line/line{i + 1:02d}_{f}", render_snippet(txt, f), txt + "\n", set="line", lang="eng",
             source="written for this corpus", font=R.FONTS[f][1], font_class=R.FONTS[f][2], size_pt=14, degradation=None)
    for i, (f, s) in enumerate(WORD_SAMPLES):
        save(f"word/word{i + 1:02d}_{f}", render_snippet(s, f, size_pt=18), s + "\n", set="word", lang="eng",
             source="written for this corpus", font=R.FONTS[f][1], font_class=R.FONTS[f][2], size_pt=18, degradation=None)
    for i, (f, (wi, hi), items) in enumerate(SPARSE_LABELS):
        dpi = 300
        img = Image.new("L", (round(wi * dpi), round(hi * dpi)), 255)
        d = ImageDraw.Draw(img)
        d.rectangle([8, 8, img.width - 9, img.height - 9], outline=0, width=4)
        for x, y, pt, s in items:
            d.text((x * dpi, y * dpi), s, font=R.load_font(f, round(pt / 72 * dpi)), fill=0)
        rows = sorted(items, key=lambda t: (round(t[1], 1), t[0]))
        gt, cur_y, cur = [], None, []
        for x, y, pt, s in rows:  # items on the same baseline row form one line, left to right
            if cur_y is not None and abs(y - cur_y) < 0.05:
                cur.append(s)
            else:
                if cur:
                    gt.append(" ".join(cur))
                cur, cur_y = [s], y
        gt.append(" ".join(cur))
        save(f"sparse/label{i + 1:02d}_{f}", img, "\n".join(gt) + "\n", set="sparse", lang="eng",
             source="written for this corpus", font=R.FONTS[f][1], font_class=R.FONTS[f][2], degradation=None,
             note="ground truth in row order (top-to-bottom, then left-to-right)")
    # two-column page: column 1 then column 2
    for i, (a, b, f) in enumerate([("doyle", "shelley", "dejavu-serif"), ("carroll", "austen", "carlito")]):
        dpi = 300
        ca, ga, _ = R.render_page(text(f"{a}.half.txt"), f, 10, dpi, width_in=3.5, margin_in=0.4)
        cb, gb, _ = R.render_page(text(f"{b}.half.txt"), f, 10, dpi, width_in=3.5, margin_in=0.4)
        W, H = round(8.5 * dpi), max(ca.height, cb.height) + dpi
        img = Image.new("L", (W, H), 255)
        img.paste(ca, (round(0.6 * dpi), dpi // 2))
        img.paste(cb, (round(4.4 * dpi), dpi // 2))
        save(f"layout/twocolumn{i + 1:02d}_{f}", img, ga + gb, set="layout", subset="two-column", lang="eng",
             source=f"gutenberg:{a}+{b}", font=R.FONTS[f][1], font_class=R.FONTS[f][2], size_pt=10,
             degradation=None, note="ground truth = left column then right column")
    for p, f, rot in [("doyle", "caladea", 90), ("shelley", "dejavu-sans", 270), ("austen", "carlito", 180)]:
        img, gt, subs = R.render_page(text(f"{p}.half.txt"), f, 12, 300)
        img = img.rotate(rot, expand=True)
        save(f"layout/rotated{rot}_{p}_{f}", img, gt, set="layout", subset="sideways" if rot != 180 else "upside-down",
             lang="eng", source=f"gutenberg:{p}", font=R.FONTS[f][1], font_class=R.FONTS[f][2], size_pt=12,
             degradation={"type": "rotation", "degrees_ccw": rot})


# ------------------------------------------------------------------ multilingual
LANG_FONTS = {"eng": "dejavu-serif", "deu": "dejavu-serif", "fra": "dejavu-serif", "spa": "dejavu-serif",
              "por": "dejavu-serif", "ita": "dejavu-serif", "rus": "dejavu-serif", "vie": "dejavu-serif",
              "uzb": "dejavu-serif", "chi_sim": "noto-sans-sc", "jpn": "ipagothic", "kor": "noto-sans-kr",
              "ara": "noto-naskh-arabic", "hin": "noto-sans-devanagari"}


def build_multilingual():
    for lang, f in LANG_FONTS.items():
        for k in (1, 2):
            img, gt, subs = R.render_page(text(f"udhr_{lang}.p{k}.txt"), f, 12, 300, rtl=lang == "ara",
                                          cjk=lang in ("chi_sim", "jpn"))
            save(f"multilingual/{lang}_p{k}_{f}", img, gt, set="multilingual", lang=lang, source=f"udhr:{lang}",
                 font=R.FONTS[f][1], font_class=R.FONTS[f][2], size_pt=12, degradation=None,
                 text_substitutions=subs or None)


def main():
    build_clean()
    build_degraded()
    build_receipts()
    build_lines_words_sparse_layout()
    build_multilingual()
    shots = HERE / "screenshots.json"
    if shots.exists():
        for e in json.loads(shots.read_text(encoding="utf-8")):
            e["sha256"] = hashlib.sha256((CORPUS / e["image"]).read_bytes()).hexdigest()
            MANIFEST.append(e)
    MANIFEST.sort(key=lambda e: e["id"])
    out = {"generator": GENERATOR, "fonts": {k: {"family": v[1], "file": Path(v[0]).name} for k, v in R.FONTS.items()},
           "count": len(MANIFEST), "images": MANIFEST}
    (CORPUS / "manifest.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(len(MANIFEST), "images")


if __name__ == "__main__":
    main()
