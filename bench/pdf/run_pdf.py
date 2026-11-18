"""PDF OCR bench: OCRmyPDF vs Tesseract CLI vs pdf2image+pytesseract vs pdfsandwich.

usage: python3 run_pdf.py WORKDIR RESULTS_DIR [--runs 5] [--part methods|dpi|native|optimize|all]

WORKDIR must contain the output of make_pdf.py. Timing = median of N runs after 1 warm-up (LAB.md);
publishable only when run on GitHub Actions (see results/meta.json).
Environment: TESSDATA_PREFIX must point at a tessdata dir that also holds configs/ and pdf.ttf.
"""
import argparse, csv, difflib, glob, json, os, shutil, statistics, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools"))
import metrics  # noqa: E402

TESS = shutil.which("tesseract")
ENV = dict(os.environ, OMP_THREAD_LIMIT="1")


def sh(cmd, cwd=None, env=None, check=True):
    p = subprocess.run(cmd, shell=True, cwd=cwd, env=env or ENV, capture_output=True, text=True)
    if check and p.returncode != 0:
        raise RuntimeError(f"{cmd}\nrc={p.returncode}\n{p.stdout[-3000:]}\n{p.stderr[-3000:]}")
    return p


def timed(fn, runs):
    fn()  # warm-up
    ts = []
    for _ in range(runs):
        t = time.perf_counter(); fn(); ts.append(time.perf_counter() - t)
    return {"median_s": round(statistics.median(ts), 3), "min_s": round(min(ts), 3),
            "max_s": round(max(ts), 3), "runs": runs, "all_s": [round(x, 3) for x in ts]}


def page_texts(pdf, n):
    return [sh(f"pdftotext -layout -f {i} -l {i} '{pdf}' -").stdout for i in range(1, n + 1)]


def text_scores(pdf, gtdir, n):
    hyps = page_texts(pdf, n)
    gts = [open(os.path.join(gtdir, f"page-{i:02d}.txt")).read() for i in range(1, n + 1)]
    cers = [metrics.cer(g, h) for g, h in zip(gts, hyps)]
    wers = [metrics.wer(g, h) for g, h in zip(gts, hyps)]
    return {"cer_doc": round(metrics.cer("\n".join(gts), "\n".join(hyps)), 5),
            "wer_doc": round(metrics.wer("\n".join(gts), "\n".join(hyps)), 5),
            "cer_page_mean": round(statistics.mean(cers), 5), "cer_page_max": round(max(cers), 5)}, hyps


def text_layer_words(pdf, pageno):
    import pdfplumber
    with pdfplumber.open(pdf) as doc:
        pg = doc.pages[pageno - 1]
        ws = pg.extract_words(keep_blank_chars=False, use_text_flow=True)
        return [(w["text"], w["x0"], w["top"], w["x1"], w["bottom"]) for w in ws], (pg.width, pg.height)


def iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0])); iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / u if u > 0 else 0.0


def alignment(pdf, gtdir, pages=(1, 2, 3)):
    """Match text-layer words to ground-truth words (same text, sequence-aligned) and compare boxes."""
    ious, centre_err_pt, n_gt, n_match = [], [], 0, 0
    for p in pages:
        gt = json.load(open(os.path.join(gtdir, f"page-{p:02d}.boxes.json")))
        k = 72.0 / gt["dpi"]
        gw = [(w, x0 * k, y0 * k, x1 * k, y1 * k) for w, x0, y0, x1, y1 in gt["words"]]
        tw, _ = text_layer_words(pdf, p)
        sm = difflib.SequenceMatcher(a=[w[0] for w in gw], b=[w[0] for w in tw], autojunk=False)
        n_gt += len(gw)
        for blk in sm.get_matching_blocks():
            for j in range(blk.size):
                g, t = gw[blk.a + j], tw[blk.b + j]
                ious.append(iou(g[1:], t[1:]))
                centre_err_pt.append(abs((g[1] + g[3]) / 2 - (t[1] + t[3]) / 2) + abs((g[2] + g[4]) / 2 - (t[2] + t[4]) / 2))
                n_match += 1
    if not ious:
        return {"words_gt": n_gt, "words_matched": 0}
    return {"words_gt": n_gt, "words_matched": n_match,
            "iou_median": round(statistics.median(ious), 3),
            "iou_ge_0.5_pct": round(100 * sum(i >= 0.5 for i in ious) / len(ious), 1),
            "centre_err_pt_median": round(statistics.median(centre_err_pt), 2)}


def overlay_png(pdf, gtdir, png, page=1, dpi=100):
    """Render a page and draw the hidden text layer on top (red boxes + the text), GT boxes in green."""
    from PIL import Image, ImageDraw, ImageFont
    base = png[:-4]
    sh(f"pdftoppm -r {dpi} -f {page} -l {page} -png -singlefile '{pdf}' '{base}-bg'")
    im = Image.open(base + "-bg.png").convert("RGB"); os.remove(base + "-bg.png")
    d = ImageDraw.Draw(im, "RGBA")
    k = dpi / 72.0
    gt = json.load(open(os.path.join(gtdir, f"page-{page:02d}.boxes.json")))
    g = dpi / gt["dpi"]
    for w, x0, y0, x1, y1 in gt["words"]:
        d.rectangle([x0 * g, y0 * g, x1 * g, y1 * g], outline=(0, 160, 0, 255), width=1)
    words, _ = text_layer_words(pdf, page)
    try:
        f = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 9)
    except OSError:
        f = ImageFont.load_default()
    for w, x0, y0, x1, y1 in words:
        d.rectangle([x0 * k, y0 * k, x1 * k, y1 * k], outline=(220, 0, 0, 255), fill=(255, 0, 0, 40), width=1)
        d.text((x0 * k, y1 * k), w, font=f, fill=(200, 0, 0, 255))
    im.save(png)


def pdf_info(pdf):
    out = sh(f"pdfinfo '{pdf}'", check=False).stdout
    info = {}
    for line in out.splitlines():
        if ":" in line:
            k, v = line.split(":", 1); info[k.strip()] = v.strip()
    imgs = sh(f"pdfimages -list '{pdf}'", check=False).stdout.splitlines()[2:]
    encs = sorted({l.split()[8] for l in imgs if len(l.split()) > 8})
    return {"pages": info.get("Pages"), "page_size": info.get("Page size"), "producer": info.get("Producer"),
            "pdf_version": info.get("PDF version"), "image_encodings": encs, "images": len(imgs)}


# ---------------------------------------------------------------- methods
def methods(work, n):
    src = os.path.join(work, "scan.pdf")
    tmp = os.path.join(work, "tmp")
    PY = sys.executable

    def rast(fmt="png", dpi=300, pdf=src):
        shutil.rmtree(tmp, ignore_errors=True); os.makedirs(tmp)
        sh(f"pdftoppm -r {dpi} -{fmt} '{pdf}' '{tmp}/pg'")
        files = sorted(glob.glob(f"{tmp}/pg-*"))
        open(f"{tmp}/list.txt", "w").write("\n".join(files) + "\n")
        return f"{tmp}/list.txt"

    def cli(fmt):
        def f(out):
            lst = rast(fmt)
            sh(f"tesseract '{lst}' '{out[:-4]}' -l eng pdf")
        return f

    def textonly(out):
        lst = rast("png")
        sh(f"tesseract '{lst}' '{tmp}/textonly' -l eng -c textonly_pdf=1 pdf")
        sh(f"qpdf '{src}' --overlay '{tmp}/textonly.pdf' -- '{out}'")

    def ocrmypdf(args):
        return lambda out: sh(f"ocrmypdf -q {args} -l eng '{src}' '{out}'")

    def py_pdf2image(out):
        sh(f"'{PY}' '{HERE}/pdf2image_pytesseract.py' '{src}' '{out}'")

    def py_pdf2image_dpi(out):
        sh(f"'{PY}' '{HERE}/pdf2image_pytesseract_dpi.py' '{src}' '{out}'")

    def pdfsandwich(out):
        sh(f"pdfsandwich -quiet -lang eng -o '{out}' '{src}'")

    return {
        "ocrmypdf_default": ("ocrmypdf -l eng in.pdf out.pdf  (defaults: -j = all cores, --optimize 1, --output-type auto)", ocrmypdf("")),
        "ocrmypdf_j1": ("ocrmypdf -j 1 -l eng in.pdf out.pdf", ocrmypdf("-j 1")),
        "tesseract_cli_png": ("pdftoppm -r 300 -png in.pdf pg; tesseract list.txt out -l eng pdf", cli("png")),
        "tesseract_cli_jpeg": ("pdftoppm -r 300 -jpeg in.pdf pg; tesseract list.txt out -l eng pdf", cli("jpeg")),
        "tesseract_textonly_overlay": ("pdftoppm -r 300 -png in.pdf pg; tesseract list.txt t -l eng -c textonly_pdf=1 pdf; qpdf in.pdf --overlay t.pdf -- out.pdf", textonly),
        "pdf2image_pytesseract": ("pdf2image.convert_from_path(dpi=300) + pytesseract.image_to_pdf_or_hocr + pypdf (the /pdf/ page's Method D code)", py_pdf2image),
        "pdf2image_pytesseract_dpi300": ("same as above plus config='--dpi 300' in image_to_pdf_or_hocr", py_pdf2image_dpi),
        "pdfsandwich": ("pdfsandwich -lang eng -o out.pdf in.pdf", pdfsandwich),
    }


def run_methods(work, res, runs, n):
    rows = []
    gtdir = os.path.join(work, "gt")
    os.makedirs(os.path.join(res, "overlay"), exist_ok=True)
    os.makedirs(os.path.join(res, "raw"), exist_ok=True)
    src_size = os.path.getsize(os.path.join(work, "scan.pdf"))
    for name, (cmd, fn) in methods(work, n).items():
        out = os.path.join(work, f"out-{name}.pdf")
        row = {"method": name, "command": cmd, "input_bytes": src_size}
        try:
            row.update(timed(lambda: fn(out), runs))
            row["output_bytes"] = os.path.getsize(out)
            row["size_ratio"] = round(row["output_bytes"] / src_size, 3)
            sc, hyps = text_scores(out, gtdir, n)
            row.update(sc)
            row.update({"align_" + k: v for k, v in alignment(out, gtdir).items()})
            row.update({"pdf_" + k: v for k, v in pdf_info(out).items()})
            open(os.path.join(res, "raw", f"{name}.pdftotext.txt"), "w").write("\f".join(hyps))
            overlay_png(out, gtdir, os.path.join(res, "overlay", f"{name}-page01-text-layer.png"))
            row["status"] = "ok"
        except Exception as e:  # record failures as they are
            row["status"] = "failed"; row["error"] = str(e)[-2000:]
        print(json.dumps(row), flush=True)
        rows.append(row)
    json.dump(rows, open(os.path.join(res, "methods.json"), "w"), indent=2)


def run_optimize(work, res, runs, n):
    rows = []
    src = os.path.join(work, "scan.pdf")
    for lvl in (0, 1, 2, 3):
        out = os.path.join(work, f"opt{lvl}.pdf")
        row = {"optimize": lvl, "command": f"ocrmypdf --optimize {lvl} -l eng in.pdf out.pdf"}
        p = sh(f"ocrmypdf --optimize {lvl} -l eng '{src}' '{out}'", check=False)
        row["rc"] = p.returncode
        row["stderr_tail"] = p.stderr[-1500:]
        if p.returncode == 0:
            row.update(timed(lambda: sh(f"ocrmypdf -q --optimize {lvl} -l eng '{src}' '{out}'"), runs))
            row["output_bytes"] = os.path.getsize(out)
            row["size_ratio"] = round(row["output_bytes"] / os.path.getsize(src), 3)
            row.update(text_scores(out, os.path.join(work, "gt"), n)[0])
            row.update({"pdf_" + k: v for k, v in pdf_info(out).items()})
        print(json.dumps(row), flush=True)
        rows.append(row)
    json.dump(rows, open(os.path.join(res, "optimize.json"), "w"), indent=2)


def run_dpi(work, res, runs, n_pages=5):
    """Rasterise the 300-DPI scan at different pdftoppm -r values, OCR to PDF; first n_pages pages."""
    rows = []
    src = os.path.join(work, "scan.pdf")
    tmp = os.path.join(work, "dpi")
    gtdir = os.path.join(work, "gt")
    for dpi in (150, 200, 300, 400, 600):
        shutil.rmtree(tmp, ignore_errors=True); os.makedirs(tmp)
        sh(f"pdftoppm -r {dpi} -png -l {n_pages} '{src}' '{tmp}/pg'")
        files = sorted(glob.glob(f"{tmp}/pg-*.png"))
        open(f"{tmp}/list.txt", "w").write("\n".join(files) + "\n")
        out = f"{tmp}/out"
        t = timed(lambda: sh(f"tesseract '{tmp}/list.txt' '{out}' -l eng pdf txt"), runs)
        hyp = open(out + ".txt").read()
        gt = "".join(open(os.path.join(gtdir, f"page-{i:02d}.txt")).read() for i in range(1, n_pages + 1))
        row = {"rasterize_dpi": dpi, "pages": n_pages, "source": "300-DPI JPEG scan, re-rasterised with pdftoppm",
               "ocr_s_per_page_median": round(t["median_s"] / n_pages, 3), **t,
               "png_bytes_total": sum(os.path.getsize(f) for f in files),
               "output_pdf_bytes": os.path.getsize(out + ".pdf"),
               "cer": round(metrics.cer(gt, hyp), 5), "wer": round(metrics.wer(gt, hyp), 5),
               "cer_text_layer": round(metrics.cer(gt, sh(f"pdftotext -layout '{out}.pdf' -").stdout), 5)}
        print(json.dumps(row), flush=True)
        rows.append(row)
    json.dump(rows, open(os.path.join(res, "dpi_rasterize.json"), "w"), indent=2)


def run_native(work, res, runs):
    """Pages 'scanned' natively at each DPI (11 pt and 7 pt text), OCR straight from the JPEG."""
    rows = []
    for d in sorted(glob.glob(os.path.join(work, "native", "*"))):
        name = os.path.basename(d)
        dpi, pt = int(name.split("dpi")[0]), int(name.split("-")[1][:-2])
        files = sorted(glob.glob(f"{d}/page-*.jpg"))
        open(f"{d}/list.txt", "w").write("\n".join(files) + "\n")
        t = timed(lambda: sh(f"tesseract '{d}/list.txt' '{d}/out' -l eng txt"), runs)
        hyp = open(f"{d}/out.txt").read()
        gt = "".join(open(f[:-4] + ".txt").read() for f in files)
        rows.append({"scan_dpi": dpi, "font_pt": pt, "pages": len(files),
                     "x_height_px_approx": round(pt / 72 * dpi * 0.46, 1),
                     "cer": round(metrics.cer(gt, hyp), 5), "wer": round(metrics.wer(gt, hyp), 5),
                     "ocr_s_per_page_median": round(t["median_s"] / len(files), 3), **t,
                     "jpeg_bytes_per_page": round(sum(os.path.getsize(f) for f in files) / len(files))})
        print(json.dumps(rows[-1]), flush=True)
    json.dump(rows, open(os.path.join(res, "dpi_native.json"), "w"), indent=2)


def run_breakdown(work, res, runs):
    """Where does the time go in 'pdftoppm -> tesseract list pdf'? Rasterise and OCR timed separately (20 pages)."""
    src = os.path.join(work, "scan.pdf")
    rows = []
    for fmt in ("png", "jpeg"):
        d = os.path.join(work, f"bd-{fmt}")
        def rast():
            shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
            sh(f"pdftoppm -r 300 -{fmt} '{src}' '{d}/pg'")
        t_r = timed(rast, runs)
        files = sorted(glob.glob(f"{d}/pg-*"))
        open(f"{d}/list.txt", "w").write("\n".join(files) + "\n")
        for out in ("txt", "pdf", "-c textonly_pdf=1 pdf"):
            t_o = timed(lambda: sh(f"tesseract '{d}/list.txt' '{d}/o' -l eng {out}"), runs)
            rows.append({"raster_format": fmt, "tesseract_output": out, "pages": len(files),
                         "raster_bytes_total": sum(os.path.getsize(f) for f in files),
                         "pdftoppm": t_r, "tesseract": t_o})
            print(json.dumps(rows[-1]), flush=True)
    json.dump(rows, open(os.path.join(res, "breakdown.json"), "w"), indent=2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("work"); ap.add_argument("res")
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--part", default="all")
    ap.add_argument("--pages", type=int, default=20)
    a = ap.parse_args()
    os.makedirs(a.res, exist_ok=True)
    print("tesseract:", TESS, file=sys.stderr)
    if a.part in ("methods", "all"):
        run_methods(a.work, a.res, a.runs, a.pages)
    if a.part in ("optimize", "all"):
        run_optimize(a.work, a.res, a.runs, a.pages)
    if a.part in ("dpi", "all"):
        run_dpi(a.work, a.res, a.runs)
    if a.part == "breakdown":
        run_breakdown(a.work, a.res, a.runs)
    if a.part in ("native", "all"):
        run_native(a.work, a.res, a.runs)


if __name__ == "__main__":
    main()
