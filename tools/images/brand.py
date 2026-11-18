#!/usr/bin/env python3
"""tesseractocr.org image pipeline (plan §11): raw capture -> branded frame -> AVIF/WebP/JPEG
at 1x and 2x -> embedded IPTC/XMP -> site manifest.

usage:
  python3 tools/images/brand.py tools/images/jobs/<page>.json [--site /home/user/tesseract] [--only NAME]

A job file is a JSON list. One entry per published image:
  {
    "src":      "tools/images/raw/train/heldout-before-after.png",  # path in THIS repo (kept untouched)
    "name":     "tesstrain-ocr-a-heldout-lines-stock-vs-fine-tuned", # kebab-case, keyword first, no digits-only
    "page":     "train",                       # site folder; output goes to assets/img/<page>/
    "kind":     "result" | "screenshot" | "third-party",
    "alt":      "...",                         # <= 125 chars, says what is in the image (also IPTC Description)
    "caption":  "...",                         # one sentence takeaway (visible <figcaption> + ImageObject caption)
    "machine":  "GitHub Actions ubuntu-24.04 runner, AMD EPYC 9V74",   # caption bar + manifest
    "version":  "5.5.4",                       # Tesseract version shown in the caption bar
    "date":     "2026-11",                     # YYYY-MM of the capture/run
    "run_id":   "44264145436",                 # GitHub Actions run (or "local-YYYY-MM-DD")
    "synthetic": true,                         # optional: test image is synthetic (say so in the caption)
    "display_width": 820,                      # optional: CSS px of the 1x file (default min(src, 820))
    "credit":   "Scan: Internet Archive (public domain)"  # third-party only: replaces our credit line
  }

Branding (§11.3): the capture pixels are never altered. Our own images ("result", "screenshot") get a
12 px frame, a slim caption bar below the capture 'tesseractocr.org · <machine> · Tesseract <ver> · <YYYY-MM>'
and the hypercube mark at 35 % opacity at the right end of the bar (never over the capture).
"third-party" images get NO frame or mark: only the metadata credit line is theirs and the page shows a
visible credit.

Outputs (site repo): assets/img/<page>/<name>.{avif,webp,jpg} (1x) and <name>@2x.{avif,webp,jpg} (2x,
only when the source is wide enough); manifest entry in assets/img/manifest.json (merged by name).
Metadata via exiftool: all source metadata stripped (GPS, device), then Creator, Credit Line, Copyright
Notice, Web Statement of Rights, Licensor URL, Description (= alt). Needs: Pillow with AVIF/WebP,
exiftool (apt install libimage-exiftool-perl).
"""
import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
TEST_URL = "https://github.com/dencyclopedia/test/blob/claude/upbeat-volta-fdndl6/"
FONT = os.path.join(HERE, "fonts", "JetBrainsMono-500.ttf")
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+){2,}$")
BUDGET_1X = 120 * 1024

INK = (11, 15, 21)       # --bg-raised (dark)
LINE = (38, 46, 58)
TEXT = (196, 204, 216)
MUTED = (124, 134, 150)
LIME = (200, 245, 66)

CREATOR = "tesseractocr.org"
CREDIT = "tesseractocr.org test lab"
LICENCE_URL = "https://tesseractocr.org/about/#image-licence"
COPYRIGHT = "© {year} tesseractocr.org. Licensed CC BY 4.0: credit 'tesseractocr.org' with a link."


def mark(size, alpha=0.35):
    """The brand mark (geometry of assets/lab/brand/mark.svg, 32-unit grid), RGBA."""
    k = 4  # supersample, then downscale for clean anti-aliasing
    S = size * k
    s = S / 32
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    a = int(255 * alpha)
    w = max(1, round(2.25 * s))
    for pts in ([(3, 11), (3, 3), (11, 3)], [(21, 3), (29, 3), (29, 11)], [(29, 21), (29, 29), (21, 29)], [(11, 29), (3, 29), (3, 21)]):
        d.line([(x * s, y * s) for x, y in pts], fill=TEXT + (a,), width=w, joint="curve")
    for (x1, y1, x2, y2) in ((3, 3, 11.5, 11.5), (29, 3, 20.5, 11.5), (29, 29, 20.5, 20.5), (3, 29, 11.5, 20.5)):
        d.line([(x1 * s, y1 * s), (x2 * s, y2 * s)], fill=TEXT + (int(a * 0.55),), width=w)
    d.rounded_rectangle([11 * s, 11 * s, 21 * s, 21 * s], radius=1.2 * s, fill=LIME + (a,))
    return im.resize((size, size), Image.LANCZOS)


def frame(cap, caption, k):
    """Branded master at source resolution. k = source px per CSS px of the 1x file."""
    pad, bar, fs, ms = round(12 * k), round(40 * k), round(13 * k), round(22 * k)
    W, H = cap.size
    out = Image.new("RGB", (W + 2 * pad, H + pad + bar), INK)
    out.paste(cap, (pad, pad))
    d = ImageDraw.Draw(out)
    d.rectangle([pad - 1, pad - 1, pad + W, pad + H], outline=LINE, width=max(1, round(k)))
    f = ImageFont.truetype(FONT, fs)
    ty = pad + H + (bar - fs) // 2 - round(2 * k)
    head = "tesseractocr.org"
    d.text((pad + 2, ty), head, font=f, fill=TEXT)
    rest = " · " + caption
    maxw = W - ms - round(16 * k) - d.textlength(head, font=f)
    while d.textlength(rest, font=f) > maxw and len(rest) > 10:  # never run under the mark
        rest = rest[:-2].rstrip() + "…"
    d.text((pad + 2 + d.textlength(head, font=f), ty), rest, font=f, fill=MUTED)
    m = mark(ms, 0.35)
    out.paste(m, (pad + W - ms, pad + H + (bar - ms) // 2), m)
    return out


def save_all(im, stem):
    """AVIF + WebP + JPEG; lower quality step by step until the 1x AVIF fits the budget."""
    sizes = {}
    for q_avif, q_webp, q_jpg in ((62, 82, 82), (52, 74, 76), (44, 66, 70), (36, 58, 62)):
        im.save(stem + ".avif", quality=q_avif)
        im.save(stem + ".webp", quality=q_webp, method=6)
        im.save(stem + ".jpg", quality=q_jpg, optimize=True, progressive=True)
        sizes = {e: os.path.getsize(f"{stem}.{e}") for e in ("avif", "webp", "jpg")}
        if sizes["avif"] <= BUDGET_1X and sizes["webp"] <= BUDGET_1X:
            break
    return sizes


def exif(paths, job, year):
    third = job["kind"] == "third-party"
    credit = job.get("credit", CREDIT) if third else CREDIT
    creator = job.get("creator", "") if third else CREATOR
    desc = job["alt"]
    args = ["exiftool", "-q", "-overwrite_original", "-all=", "-charset", "iptc=UTF8", "-codedcharacterset=utf8",
            f"-XMP-dc:Creator={creator}", f"-XMP-dc:Description={desc}", f"-XMP-photoshop:Credit={credit}",
            f"-XMP-xmpRights:WebStatement={LICENCE_URL}", f"-XMP-plus:LicensorURL={LICENCE_URL}" if not third else "-XMP-plus:LicensorURL=",
            f"-XMP-dc:Rights={job.get('copyright') if third else COPYRIGHT.format(year=year)}",
            f"-XMP-dc:Title={job['name']}"]
    jpg_only = [f"-IPTC:By-line={creator}", f"-IPTC:Credit={credit}", f"-IPTC:Caption-Abstract={desc}",
                f"-IPTC:CopyrightNotice={job.get('copyright') if third else COPYRIGHT.format(year=year)}"]
    for p in paths:
        a = args + (jpg_only if p.endswith(".jpg") else []) + [p]
        r = subprocess.run(a, capture_output=True, text=True)
        if r.returncode:
            raise SystemExit(f"exiftool failed on {p}: {r.stderr.strip()}")


def run(job, site):
    name = job["name"]
    words = name.split("-")
    if not NAME_RE.match(name) or any(words.count(x) > 2 for x in words if len(x) > 2) or name.replace("-", "").isdigit():
        raise SystemExit(f"{name}: file name must be kebab-case, >= 3 words, no keyword stuffing")
    if len(job["alt"]) > 125:
        raise SystemExit(f"{name}: alt is {len(job['alt'])} chars (max 125)")
    src = os.path.join(REPO, job["src"])
    cap = Image.open(src).convert("RGB")
    dw = job.get("display_width") or min(cap.width, 820)
    third = job["kind"] == "third-party"
    k = cap.width / dw if third else cap.width / (dw - 24)  # framed: 12 px frame each side at 1x
    if third:
        master = cap
    else:
        bar = f"{job.get('bar_machine', job['machine'])} · Tesseract {job['version']} · {job['date']}"
        master = frame(cap, bar, k)
    outdir = os.path.join(site, "assets", "img", job["page"])
    os.makedirs(outdir, exist_ok=True)
    w1 = round(master.width / k)
    h1 = round(master.height * w1 / master.width)
    files, sizes = {}, {}
    one = master.resize((w1, h1), Image.LANCZOS)
    stem1 = os.path.join(outdir, name)
    sizes["1x"] = save_all(one, stem1)
    made = [stem1 + e for e in (".avif", ".webp", ".jpg")]
    if master.width >= 2 * w1 * 0.98:
        two = master.resize((2 * w1, 2 * h1), Image.LANCZOS) if master.width != 2 * w1 else master
        stem2 = stem1 + "@2x"
        sizes["2x"] = save_all(two, stem2)
        made += [stem2 + e for e in (".avif", ".webp", ".jpg")]
    year = job["date"][:4]
    exif(made, job, year)
    sizes = {s: {e: os.path.getsize(f"{stem1}{'' if s == '1x' else '@2x'}.{e}") for e in ("avif", "webp", "jpg")} for s in sizes}
    rel = lambda p: "/" + os.path.relpath(p, site).replace(os.sep, "/")
    for ext in ("avif", "webp", "jpg"):
        files[ext] = [rel(f"{stem1}.{ext}")] + ([rel(f"{stem1}@2x.{ext}")] if "2x" in sizes else [])
    commit = subprocess.run(["git", "log", "-1", "--format=%h", "--", job["src"]], cwd=REPO, capture_output=True, text=True).stdout.strip()
    entry = {
        "name": name, "page": job["page"], "kind": job["kind"], "src": files["jpg"][0], "files": files,
        "width": w1, "height": h1, "alt": job["alt"], "caption": job["caption"],
        "keyword": job.get("keyword", ""), "machine": job.get("machine", ""), "version": job.get("version", ""),
        "date": job["date"], "run_id": job.get("run_id", ""), "synthetic": bool(job.get("synthetic", False)),
        "source": job["src"], "source_url": TEST_URL + job["src"], "source_commit": commit or "uncommitted",
        "credit": job.get("credit", CREDIT) if third else CREDIT, "bytes": sizes,
        "built": dt.date.today().isoformat(),
    }
    over = [f"{e} {b // 1024} KB" for e, b in sizes["1x"].items() if e != "jpg" and b > BUDGET_1X]
    print(f"{name}: {w1}x{h1} 1x {sizes['1x']}" + (f" 2x {sizes['2x']}" if "2x" in sizes else "") + (f"  OVER BUDGET: {over}" if over else ""))
    return entry


def merge_manifest(site, entries):
    path = os.path.join(site, "assets", "img", "manifest.json")
    data = {"version": 1, "about": "Every published image: written by dencyclopedia/test tools/images/brand.py and "
            "ops/tools/charts/charts.py. Read by page templates, ops/seo/audit.py and ops/tools/image_sitemap.py.",
            "images": []}
    if os.path.exists(path):
        data = json.load(open(path, encoding="utf-8"))
    by = {i["name"]: i for i in data["images"]}
    for e in entries:
        by[e["name"]] = e
    data["images"] = sorted(by.values(), key=lambda i: (i["page"], i["name"]))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"manifest: {len(data['images'])} images -> {path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("job")
    ap.add_argument("--site", default=os.environ.get("SITE", "/home/user/tesseract"))
    ap.add_argument("--only")
    a = ap.parse_args()
    jobs = json.load(open(a.job, encoding="utf-8"))
    entries = [run(j, a.site) for j in jobs if not a.only or j["name"] == a.only]
    merge_manifest(a.site, entries)


if __name__ == "__main__":
    main()
