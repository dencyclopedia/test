"""The shared image subset for the engine comparison (ids from corpus/manifest.json)."""
import json
from pathlib import Path

CORPUS = Path(__file__).resolve().parents[2] / "corpus"
DEG = ["blur2", "noise30", "jpeg30", "skew3", "light75", "contrast2", "phone1", "phone2"]
LANGS = ["deu", "rus", "chi_sim", "ara"]
# corpus lang code -> EasyOCR code, PaddleOCR code
EASYOCR_LANG = {"eng": "en", "deu": "de", "rus": "ru", "chi_sim": "ch_sim", "ara": "ar"}
PADDLE_LANG = {"eng": "en", "deu": "german", "rus": "ru", "chi_sim": "ch", "ara": "ar"}


def subset():
    m = json.loads((CORPUS / "manifest.json").read_text(encoding="utf-8"))["images"]
    out = []
    for e in m:
        s = e["set"]
        if s == "clean" and e["dpi"] == 300 and e["size_pt"] == 12 and e["id"].split("/")[1].split("_")[0] in ("austen", "doyle") \
                and e["font"] in ("DejaVu Serif", "Carlito", "DejaVu Sans Mono"):
            out.append(("clean", e))
        elif s == "degraded" and e["level"] in DEG and e["base"] in ("austen_dejavu-serif", "doyle_carlito"):
            out.append(("degraded", e))
        elif s == "receipt":
            out.append(("receipt", e))
        elif s == "screenshot" and e["device_scale_factor"] == 1:
            out.append(("screenshot", e))
        elif s == "multilingual" and e["lang"] in LANGS:
            out.append(("lang:" + e["lang"], e))
    return out


def lines_from_boxes(items, rtl=False):
    """items: list of (x0, y0, x1, y1, text). Group boxes into lines (vertical centre within half the box height of
    the line's running centre), sort lines top to bottom and boxes left to right (right to left for Arabic), join
    with spaces / newlines.
    Used for EasyOCR and PaddleOCR, which return boxes, not page text."""
    items = sorted(items, key=lambda t: (t[1] + t[3]) / 2)
    lines = []
    for it in items:
        cy, h = (it[1] + it[3]) / 2, it[3] - it[1]
        for ln in lines:
            if abs(ln["cy"] - cy) < 0.5 * max(h, ln["h"]):
                ln["items"].append(it)
                ln["cy"] = sum((i[1] + i[3]) / 2 for i in ln["items"]) / len(ln["items"])
                break
        else:
            lines.append({"cy": cy, "h": h, "items": [it]})
    lines.sort(key=lambda l: l["cy"])
    return "\n".join(" ".join(i[4] for i in sorted(l["items"], key=lambda t: -t[2] if rtl else t[0])) for l in lines) + "\n"
