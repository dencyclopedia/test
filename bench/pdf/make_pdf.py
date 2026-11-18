"""Build the synthetic 20-page 'scanned' PDF and the native-DPI page sets.
usage: python3 make_pdf.py OUTDIR [N_PAGES]
Outputs (all SYNTHETIC, see text/SOURCES.md):
  OUTDIR/scan.pdf                   image-only PDF, 20 A4 pages, 300 DPI grayscale JPEG (q=75), built with img2pdf
  OUTDIR/pages/page-NN.jpg          the same page images
  OUTDIR/gt/page-NN.txt             ground-truth text per page
  OUTDIR/gt/page-NN.boxes.json      ground-truth word boxes (pixels at 300 DPI, after the simulated skew)
  OUTDIR/native/<dpi>dpi-<pt>pt/page-NN.jpg + .txt   pages 'scanned' natively at 150..600 DPI, 11 pt and 7 pt text
"""
import json, os, sys
import img2pdf
import scanlib

out = sys.argv[1]
N = int(sys.argv[2]) if len(sys.argv) > 2 else 20      # pages (20 for the published run)
NATIVE = os.environ.get("NATIVE", "1") == "1"
for d in ("pages", "gt", "native"):
    os.makedirs(os.path.join(out, d), exist_ok=True)

pages = scanlib.layout_pages(dpi=300, font_pt=11, n_pages=N)
jpgs = []
for i, lines in enumerate(pages, 1):
    im = scanlib.render_lines(lines, dpi=300, font_pt=11)
    boxes = scanlib.render_lines.last_boxes
    deg = scanlib.degrade(im, seed=1000 + i, dpi=300)
    boxes = scanlib.rotate_boxes(boxes, scanlib.degrade.last_angle, im.size)
    p = os.path.join(out, "pages", f"page-{i:02d}.jpg")
    deg.save(p, "JPEG", quality=75, dpi=(300, 300))
    jpgs.append(p)
    open(os.path.join(out, "gt", f"page-{i:02d}.txt"), "w").write(scanlib.gt_text(lines))
    json.dump({"dpi": 300, "size": im.size, "angle": scanlib.degrade.last_angle, "words": boxes},
              open(os.path.join(out, "gt", f"page-{i:02d}.boxes.json"), "w"))
with open(os.path.join(out, "scan.pdf"), "wb") as f:
    f.write(img2pdf.convert(jpgs))

# native 'scan' resolution sweep: first 4 pages' text, 11 pt (body text) and 7 pt (small print)
for pt in ((11, 7) if NATIVE else ()):
    lay = scanlib.layout_pages(dpi=300, font_pt=pt, n_pages=4)
    for dpi in (150, 200, 300, 400, 600):
        d = os.path.join(out, "native", f"{dpi}dpi-{pt}pt"); os.makedirs(d, exist_ok=True)
        for i, lines in enumerate(lay, 1):
            im = scanlib.render_lines(lines, dpi=dpi, font_pt=pt)
            scanlib.degrade(im, seed=2000 + i, dpi=dpi).save(os.path.join(d, f"page-{i:02d}.jpg"), "JPEG",
                                                           quality=75, dpi=(dpi, dpi))
            open(os.path.join(d, f"page-{i:02d}.txt"), "w").write(scanlib.gt_text(lines))
print("ok", len(jpgs), "pages")
