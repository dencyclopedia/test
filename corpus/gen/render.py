"""Text-to-image rendering and seeded degradations used by build_corpus.py.

Everything here is deterministic for a given (Pillow, numpy, OpenCV) version and seed.
"""
import io
import math
from pathlib import Path

import cv2
import numpy as np
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

FONT_DIR_CACHE = Path(__file__).resolve().parent / ".cache" / "fonts"

FONTS = {
    # key: (path, family label, style class)
    "dejavu-serif": ("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf", "DejaVu Serif", "serif"),
    "caladea": ("/usr/share/fonts/truetype/crosextra/Caladea-Regular.ttf", "Caladea", "serif"),
    "charter": ("/usr/share/fonts/X11/Type1/c0648bt_.pfb", "Bitstream Charter", "serif"),
    "freeserif": ("/usr/share/fonts/truetype/freefont/FreeSerif.ttf", "FreeSerif", "serif"),
    "dejavu-sans": ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "DejaVu Sans", "sans"),
    "carlito": ("/usr/share/fonts/truetype/crosextra/Carlito-Regular.ttf", "Carlito", "sans"),
    "inter": ("/usr/share/fonts/opentype/inter/Inter-Regular.otf", "Inter", "sans"),
    "freesans": ("/usr/share/fonts/truetype/freefont/FreeSans.ttf", "FreeSans", "sans"),
    "dejavu-mono": ("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", "DejaVu Sans Mono", "mono"),
    "courier10": ("/usr/share/fonts/X11/Type1/c0419bt_.pfb", "Courier 10 Pitch", "mono"),
    "jetbrains-mono": ("/usr/share/fonts/truetype/jetbrains-mono/JetBrainsMono-Regular.ttf", "JetBrains Mono", "mono"),
    "freemono": ("/usr/share/fonts/truetype/freefont/FreeMono.ttf", "FreeMono", "mono"),
    "ipagothic": ("/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf", "IPAGothic", "sans"),
    "noto-sans-sc": (str(FONT_DIR_CACHE / "NotoSansSC[wght].ttf"), "Noto Sans SC", "sans"),
    "noto-sans-kr": (str(FONT_DIR_CACHE / "NotoSansKR[wght].ttf"), "Noto Sans KR", "sans"),
    "noto-naskh-arabic": (str(FONT_DIR_CACHE / "NotoNaskhArabic[wght].ttf"), "Noto Naskh Arabic", "serif"),
    "noto-sans-devanagari": (str(FONT_DIR_CACHE / "NotoSansDevanagari[wdth,wght].ttf"), "Noto Sans Devanagari", "sans"),
}

# ASCII fallbacks for typographic characters, applied only when a font lacks the glyph.
FALLBACK = {"“": '"', "”": '"', "‘": "'", "’": "'", "—": "--", "–": "-", "…": "..."}

_cmaps = {}


def font_cmap(key):
    if key not in _cmaps:
        path = FONTS[key][0]
        if path.endswith(".pfb"):
            # Type1: ask FreeType via Pillow whether a glyph has an outline (bbox) instead of a cmap
            _cmaps[key] = None
        else:
            _cmaps[key] = set(TTFont(path, fontNumber=0, lazy=True).getBestCmap().keys())
    return _cmaps[key]


def has_glyph(key, ch, pil_font):
    cm = font_cmap(key)
    if cm is not None:
        return ord(ch) in cm
    if ch.isspace():
        return True
    # Type1 fonts: a missing glyph renders as .notdef (empty for these fonts)
    return pil_font.getbbox(ch)[2] > 0


def fit_text_to_font(text, key, pil_font):
    """Return (text, substitutions) with characters the font can't draw replaced by ASCII fallbacks.
    Raises if a character has no fallback (so ground truth always equals what is drawn)."""
    subs = {}
    out = []
    for ch in text:
        if ch == "\n" or has_glyph(key, ch, pil_font):
            out.append(ch)
        elif ch in FALLBACK:
            subs[ch] = FALLBACK[ch]
            out.append(FALLBACK[ch])
        else:
            raise ValueError(f"font {key} cannot draw {ch!r} (U+{ord(ch):04X})")
    return "".join(out), subs


def load_font(key, px):
    f = ImageFont.truetype(FONTS[key][0], px, layout_engine=ImageFont.Layout.RAQM)
    try:
        f.set_variation_by_name("Regular")
    except Exception:
        pass
    return f


def wrap(paragraph, font, max_w, direction=None, cjk=False):
    """Greedy wrap. Latin-like scripts break on spaces; CJK breaks between any characters."""
    units = list(paragraph) if cjk else paragraph.split(" ")
    sep = "" if cjk else " "
    lines, cur = [], ""
    for u in units:
        cand = (cur + sep + u) if cur else u
        if font.getlength(cand, direction=direction) <= max_w or not cur:
            cur = cand
        else:
            lines.append(cur)
            cur = u
    if cur:
        lines.append(cur)
    return lines


def render_page(text, font_key, size_pt, dpi, width_in=8.5, margin_in=1.0, line_spacing=1.25,
                para_gap=0.5, rtl=False, cjk=False, min_height_in=None):
    """Render paragraphs (one per line of `text`) as a grayscale page.

    Returns (PIL.Image 'L', ground_truth_text, substitutions). The ground truth is the text exactly as
    drawn: one rendered line per output line."""
    px = round(size_pt / 72 * dpi)
    font = load_font(font_key, px)
    text, subs = fit_text_to_font(text, font_key, font)
    W = round(width_in * dpi)
    m = round(margin_in * dpi)
    max_w = W - 2 * m
    direction = "rtl" if rtl else None
    lines = []  # (text or None for paragraph gap)
    for i, para in enumerate(text.split("\n")):
        if not para.strip():
            continue
        if lines:
            lines.append(None)
        lines.extend(wrap(para, font, max_w, direction, cjk))
    lh = round(px * line_spacing)
    gap = round(px * line_spacing * para_gap)
    H = 2 * m + sum(lh if l is not None else gap for l in lines)
    if min_height_in:
        H = max(H, round(min_height_in * dpi))
    img = Image.new("L", (W, H), 255)
    d = ImageDraw.Draw(img)
    y = m
    for l in lines:
        if l is None:
            y += gap
            continue
        if rtl:
            w = font.getlength(l, direction=direction)
            d.text((W - m - w, y), l, font=font, fill=0, direction=direction)
        else:
            d.text((m, y), l, font=font, fill=0)
        y += lh
    gt = "\n".join(l for l in lines if l is not None) + "\n"
    return img, gt, subs


# ---------------------------------------------------------------- degradations
# All take a uint8 grayscale numpy array and return one, plus the params actually used.

def rng_for(seed):
    return np.random.default_rng(seed)


def gaussian_blur(a, sigma):
    return cv2.GaussianBlur(a, (0, 0), sigmaX=sigma, sigmaY=sigma, borderType=cv2.BORDER_REPLICATE)


def gaussian_noise(a, sigma, seed):
    n = rng_for(seed).normal(0, sigma, a.shape)
    return np.clip(a.astype(np.float64) + n, 0, 255).astype(np.uint8)


def jpeg_bytes(a, quality):
    buf = io.BytesIO()
    Image.fromarray(a).save(buf, "JPEG", quality=quality, subsampling=0, optimize=False)
    return buf.getvalue()


def skew(a, degrees):
    """Rotate counter-clockwise by `degrees` around the centre, enlarging the canvas, white fill."""
    h, w = a.shape
    M = cv2.getRotationMatrix2D((w / 2, h / 2), degrees, 1.0)
    cos, sin = abs(M[0, 0]), abs(M[0, 1])
    nw, nh = int(h * sin + w * cos + 0.5), int(h * cos + w * sin + 0.5)
    M[0, 2] += nw / 2 - w / 2
    M[1, 2] += nh / 2 - h / 2
    return cv2.warpAffine(a, M, (nw, nh), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT, borderValue=255)


def lighting_gradient(a, strength):
    """Multiply by a diagonal gradient: 1.0 at the top-left corner falling to (1-strength) at bottom-right."""
    h, w = a.shape
    yy, xx = np.mgrid[0:h, 0:w]
    t = (xx / max(w - 1, 1) + yy / max(h - 1, 1)) / 2
    g = 1.0 - strength * t
    return np.clip(a.astype(np.float64) * g, 0, 255).astype(np.uint8)


def low_contrast(a, ink, paper):
    """Map black->ink and white->paper linearly."""
    f = a.astype(np.float64) / 255.0
    return np.clip(ink + f * (paper - ink), 0, 255).round().astype(np.uint8)


def perspective(a, max_frac, seed):
    """Random perspective warp: each corner moves inward by up to max_frac of the side. Grey background."""
    r = rng_for(seed)
    h, w = a.shape
    pad = int(max(h, w) * max_frac) + 10
    big = cv2.copyMakeBorder(a, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=120)
    H, W = big.shape
    src = np.float32([[pad, pad], [pad + w, pad], [pad + w, pad + h], [pad, pad + h]])
    jitter = r.uniform(-max_frac, max_frac, (4, 2)) * np.array([w, h])
    dst = (src + jitter).astype(np.float32)
    M = cv2.getPerspectiveTransform(src, dst)
    out = cv2.warpPerspective(big, M, (W, H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT, borderValue=120)
    return out, dst.round(1).tolist()


def vignette(a, strength, seed):
    """Off-centre radial falloff (phone flash / lamp)."""
    r = rng_for(seed)
    h, w = a.shape
    cx, cy = r.uniform(0.3, 0.7) * w, r.uniform(0.3, 0.7) * h
    yy, xx = np.mgrid[0:h, 0:w]
    d = np.sqrt(((xx - cx) / w) ** 2 + ((yy - cy) / h) ** 2) / math.sqrt(0.5)
    g = 1.0 - strength * d ** 1.5
    return np.clip(a.astype(np.float64) * g, 0, 255).astype(np.uint8), [round(cx), round(cy)]


def phone_photo(a, level, seed):
    """'Simulated phone photo': perspective + lighting + slight blur + sensor noise + JPEG q85.
    Returns (jpeg_bytes, params)."""
    p = {1: dict(persp=0.03, vig=0.35, blur=0.8, noise=4), 2: dict(persp=0.06, vig=0.55, blur=1.4, noise=8)}[level]
    out, corners = perspective(a, p["persp"], seed)
    out = low_contrast(out, 35, 235)
    out, centre = vignette(out, p["vig"], seed + 1)
    out = gaussian_blur(out, p["blur"])
    out = gaussian_noise(out, p["noise"], seed + 2)
    params = dict(p, corners=corners, vignette_centre=centre, ink_paper=[35, 235], jpeg_quality=85)
    return jpeg_bytes(out, 85), params
