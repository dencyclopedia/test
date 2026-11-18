#!/usr/bin/env python3
"""Preprocessing pipelines (OpenCV / scikit-image) in front of pytesseract, on degraded images.

Engine: pytesseract -> Tesseract 5.5.4, tessdata (standard) eng, --oem 1 --psm 3.
Images: corpus 'degraded' set (4 base pages x 20 levels incl. 'none') + clean pages at 150 DPI (18, 'lowres')
        + faded / phone receipts (6).
Pipelines (each starts from the image file as loaded by OpenCV in colour, IMREAD_COLOR):
  raw          the BGR array as loaded, handed to pytesseract unchanged
  gray         cvtColor to grayscale
  upscale2x    gray, resized x2 with INTER_CUBIC
  otsu         gray -> global Otsu threshold
  adaptive     gray -> cv2.adaptiveThreshold (Gaussian, block 31, C 15)
  sauvola      gray -> skimage threshold_sauvola (window 25, k 0.2)
  deskew       gray -> angle from minAreaRect of dark pixels (Otsu mask) -> rotate back
  denoise      gray -> cv2.fastNlMeansDenoising (h 15)
  median3      gray -> medianBlur 3
  denoise+otsu, deskew+otsu, upscale2x+otsu, full (gray -> denoise -> deskew -> otsu)
Usage: python3 bench/preprocess/run.py
"""
import os
import statistics
import sys
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import cv2
import numpy as np
import pytesseract
from skimage.filters import threshold_sauvola

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "accuracy"))
import benchlib as B  # noqa: E402

RES = HERE / "results"
CONFIG = f"--tessdata-dir {B.MODELS['standard']} --oem 1 --psm 3"
pytesseract.pytesseract.tesseract_cmd = B.TESS["5.5.4"]


def gray(a):
    return cv2.cvtColor(a, cv2.COLOR_BGR2GRAY) if a.ndim == 3 else a


def otsu(g):
    return cv2.threshold(g, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]


def adaptive(g):
    return cv2.adaptiveThreshold(g, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 15)


def sauvola(g):
    t = threshold_sauvola(g, window_size=25, k=0.2)
    return ((g > t) * 255).astype(np.uint8)


def deskew_angle(g):
    mask = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    pts = np.column_stack(np.where(mask > 0))[:, ::-1].astype(np.float32)
    if len(pts) < 50:
        return 0.0
    (_, _), (w, h), ang = cv2.minAreaRect(pts)
    # OpenCV >= 4.5: angle in [0, 90); map to the small correction angle
    if w < h:
        ang = ang - 90
    while ang > 45:
        ang -= 90
    while ang <= -45:
        ang += 90
    return ang


def deskew(g):
    ang = deskew_angle(g)
    if abs(ang) < 0.1 or abs(ang) > 15:
        return g
    h, w = g.shape
    M = cv2.getRotationMatrix2D((w / 2, h / 2), ang, 1.0)
    return cv2.warpAffine(g, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)


def upscale(g):
    return cv2.resize(g, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)


def denoise(g):
    return cv2.fastNlMeansDenoising(g, None, h=15)


PIPELINES = {
    "raw": lambda a: a,
    "gray": lambda a: gray(a),
    "upscale2x": lambda a: upscale(gray(a)),
    "otsu": lambda a: otsu(gray(a)),
    "adaptive": lambda a: adaptive(gray(a)),
    "sauvola": lambda a: sauvola(gray(a)),
    "deskew": lambda a: deskew(gray(a)),
    "denoise": lambda a: denoise(gray(a)),
    "median3": lambda a: cv2.medianBlur(gray(a), 3),
    "denoise+otsu": lambda a: otsu(denoise(gray(a))),
    "deskew+otsu": lambda a: otsu(deskew(gray(a))),
    "upscale2x+otsu": lambda a: otsu(upscale(gray(a))),
    "full": lambda a: otsu(deskew(denoise(gray(a)))),
}


def images():
    imgs = B.manifest(set="degraded")
    imgs += B.manifest(set="clean", dpi=150, size_pt=12)
    imgs += B.manifest(set="receipt", degradation=lambda d: bool(d))
    return imgs


def category(e):
    if e["set"] == "degraded":
        lvl = e["level"]
        return "none" if lvl == "none" else lvl.rstrip("0123456789")
    if e["set"] == "clean":
        return "lowres150"
    return "receipt-" + e["degradation"]["type"]


def work(args):
    id_, path, truth, pipe = args
    os.environ["OMP_THREAD_LIMIT"] = "1"
    a = cv2.imread(str(path), cv2.IMREAD_COLOR)
    p = PIPELINES[pipe](a)
    if p.ndim == 3:
        p = cv2.cvtColor(p, cv2.COLOR_BGR2RGB)
    txt = pytesseract.image_to_string(p, config=CONFIG)
    out = RES / "raw" / pipe / (id_ + ".txt")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(txt, encoding="utf-8")
    return (pipe, id_), B.score(truth, txt)


def main():
    imgs = images()
    jobs = [(e["id"], B.CORPUS / e["image"], B.gt(e), p) for e in imgs for p in PIPELINES]
    print(len(jobs), "runs")
    res = {}
    with ProcessPoolExecutor(B.WORKERS) as ex:
        for i, (k, s) in enumerate(ex.map(work, jobs, chunksize=1)):
            res[k] = s
            if (i + 1) % 50 == 0:
                print(f"  {i + 1}/{len(jobs)}", flush=True)
    by_id = {e["id"]: e for e in imgs}
    rows = [dict(pipeline=p, id=i, category=category(by_id[i]), level=by_id[i].get("level", ""), **s)
            for (p, i), s in sorted(res.items())]
    B.write_csv(RES / "per_image.csv", rows)
    g = defaultdict(list)
    for r in rows:
        g[(r["category"], r["pipeline"])].append(r)
    raw_mean = {c: B.mean(r["cer"] for r in rs) for (c, p), rs in g.items() if p == "raw"}
    summ = []
    for (c, p), rs in sorted(g.items()):
        m = B.mean(r["cer"] for r in rs)
        summ.append(dict(category=c, pipeline=p, n=len(rs), cer_mean=m, cer_median=statistics.median(r["cer"] for r in rs),
                         wer_mean=B.mean(r["wer"] for r in rs), delta_vs_raw=m - raw_mean[c]))
    B.write_csv(RES / "summary.csv", summ)
    lv = defaultdict(list)
    for r in rows:
        if r["level"]:
            lv[(r["level"], r["pipeline"])].append(r)
    B.write_csv(RES / "summary_by_level.csv", [dict(level=l, pipeline=p, n=len(rs), cer_mean=B.mean(r["cer"] for r in rs))
                                               for (l, p), rs in sorted(lv.items())])
    B.write_meta(RES / "meta.json", {"pytesseract_config": CONFIG},
                 {"pytesseract": pytesseract.get_tesseract_version().public, "opencv": cv2.__version__,
                  "pipelines": list(PIPELINES), "images": len(imgs)})


if __name__ == "__main__":
    main()
