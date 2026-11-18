"""Synthetic 'scanned page' renderer shared by bench/pdf, bench/api, bench/bindings, bench/python-throughput.

Everything produced here is SYNTHETIC: public-domain text rendered with PIL, then degraded with seeded
noise (small rotation, blur, paper tone, sensor noise, specks, JPEG) to look like a flatbed scan.
"""
import io, os, random, textwrap
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
TEXT = os.path.join(HERE, "text", "pride-and-prejudice-ch01-12.txt")
FONT_DIRS = ["/usr/share/fonts/truetype/liberation", "/usr/share/fonts/truetype/liberation2"]


def font_path(name="LiberationSerif-Regular.ttf"):
    for d in FONT_DIRS:
        p = os.path.join(d, name)
        if os.path.exists(p):
            return p
    raise FileNotFoundError(name + " (apt install fonts-liberation)")


def paragraphs():
    raw = open(TEXT, encoding="utf-8").read()
    paras = [" ".join(p.split()) for p in raw.split("\n\n")]
    return [p for p in paras if p]


def layout_pages(dpi=300, font_pt=11.0, n_pages=20, font="LiberationSerif-Regular.ttf",
                 margin_in=1.0, page_in=(8.27, 11.69), line_spacing=1.25):
    """Greedy layout of the text onto A4 pages. Returns list of pages, each a list of lines ('' = para gap)."""
    px = lambda inch: int(round(inch * dpi))
    W, H = px(page_in[0]), px(page_in[1])
    f = ImageFont.truetype(font_path(font), int(round(font_pt / 72 * dpi)))
    maxw = W - 2 * px(margin_in)
    lh = int(round(font_pt / 72 * dpi * line_spacing))
    max_lines = (H - 2 * px(margin_in)) // lh
    lines = []
    for p in paragraphs():
        words, cur = p.split(" "), ""
        for w in words:
            t = (cur + " " + w).strip()
            if f.getlength(t) <= maxw:
                cur = t
            else:
                lines.append(cur); cur = w
        lines.append(cur)
        lines.append("")
    pages, i = [], 0
    while len(pages) < n_pages and i < len(lines):
        pg = lines[i:i + max_lines]
        while pg and pg[0] == "":
            pg = pg[1:]
        pages.append(pg); i += max_lines
    return pages


def render_lines(lines, dpi=300, font_pt=11.0, font="LiberationSerif-Regular.ttf",
                 margin_in=1.0, page_in=(8.27, 11.69), line_spacing=1.25):
    px = lambda inch: int(round(inch * dpi))
    W, H = px(page_in[0]), px(page_in[1])
    f = ImageFont.truetype(font_path(font), int(round(font_pt / 72 * dpi)))
    lh = int(round(font_pt / 72 * dpi * line_spacing))
    im = Image.new("L", (W, H), 255)
    d = ImageDraw.Draw(im)
    y = px(margin_in)
    boxes = []  # ground-truth word boxes [word, x0, y0, x1, y1] in pixels (before degradation)
    for ln in lines:
        if ln:
            x0 = px(margin_in)
            d.text((x0, y), ln, font=f, fill=0)
            pos = 0
            for w in ln.split(" "):
                start = ln.index(w, pos)
                bx = d.textbbox((x0 + f.getlength(ln[:start]), y), w, font=f)
                boxes.append([w] + [float(v) for v in bx])
                pos = start + len(w)
        y += lh
    render_lines.last_boxes = boxes
    return im


def degrade(im, seed, dpi=300, jpeg_quality=None):
    """Mild, realistic scan degradation, scaled with DPI. Deterministic for a seed."""
    rnd = random.Random(seed)
    rs = np.random.default_rng(seed)
    s = dpi / 300.0
    angle = rnd.uniform(-0.6, 0.6)
    degrade.last_angle = angle
    im = im.rotate(angle, resample=Image.BICUBIC, expand=False, fillcolor=255)
    im = im.filter(ImageFilter.GaussianBlur(radius=0.8 * s))
    a = np.asarray(im).astype(np.float32)
    paper = rnd.uniform(232, 246)
    ink = rnd.uniform(18, 45)
    a = ink + (a / 255.0) * (paper - ink)
    # low-frequency illumination gradient
    h, w = a.shape
    gx = np.linspace(0, 1, w, dtype=np.float32)[None, :]
    a = a - rnd.uniform(0, 10) * gx
    a = a + rs.normal(0, 6, a.shape).astype(np.float32)
    # dust specks
    for _ in range(int(60 * s * s)):
        x, y = rnd.randrange(w), rnd.randrange(h)
        r = max(1, int(rnd.uniform(0.5, 1.6) * s))
        a[max(0, y - r):y + r, max(0, x - r):x + r] = rnd.uniform(40, 120)
    a = np.clip(a, 0, 255).astype(np.uint8)
    out = Image.fromarray(a, "L").filter(ImageFilter.GaussianBlur(radius=0.5 * s))  # scanner optics/MTF
    if jpeg_quality:
        b = io.BytesIO(); out.save(b, "JPEG", quality=jpeg_quality, dpi=(dpi, dpi)); b.seek(0)
        out = Image.open(b); out.load()
    out.info["dpi"] = (dpi, dpi)
    return out


def rotate_boxes(boxes, angle, size):
    """Apply PIL's rotate(angle) (counter-clockwise, about the centre) to word boxes -> axis-aligned boxes."""
    import math
    W, H = size; cx, cy = W / 2, H / 2
    t = math.radians(angle); c, s_ = math.cos(t), math.sin(t)
    out = []
    for w, x0, y0, x1, y1 in boxes:
        pts = []
        for x, y in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)):
            dx, dy = x - cx, y - cy
            pts.append((cx + dx * c + dy * s_, cy - dx * s_ + dy * c))
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        out.append([w, round(min(xs), 1), round(min(ys), 1), round(max(xs), 1), round(max(ys), 1)])
    return out


def gt_text(lines):
    return "\n".join(l for l in lines if l) + "\n"


RECEIPT = [
    ("CORNER MARKET", None), ("12 Harbour Street", None), ("", None),
    ("Oat milk 1L", "2.49"), ("Sourdough loaf", "3.80"), ("Free-range eggs x6", "2.95"),
    ("Bananas 1.2kg", "1.38"), ("Dark chocolate 85%", "2.20"), ("Coffee beans 250g", "6.50"),
    ("", None), ("SUBTOTAL", "19.32"), ("VAT 5%", "0.97"), ("TOTAL", "20.29"), ("", None),
    ("CARD ****4821 APPROVED", None), ("Thank you for shopping!", None),
]


def render_receipt(seed=7, dpi=200, width_in=3.0):
    """Synthetic till receipt (monospace), returns (image, ground_truth)."""
    px = lambda inch: int(round(inch * dpi))
    f = ImageFont.truetype(font_path("LiberationMono-Regular.ttf"), int(round(9 / 72 * dpi)))
    lh = int(round(9 / 72 * dpi * 1.6))
    W = px(width_in); H = px(0.4) * 2 + lh * len(RECEIPT)
    im = Image.new("L", (W, H), 255); d = ImageDraw.Draw(im)
    y = px(0.4); gt = []
    for left, right in RECEIPT:
        if left:
            d.text((px(0.2), y), left, font=f, fill=0)
            if right:
                d.text((W - px(0.2) - f.getlength(right), y), right, font=f, fill=0)
            gt.append(left + (" " + right if right else ""))
        y += lh
    return degrade(im, seed, dpi=dpi), "\n".join(gt) + "\n"
