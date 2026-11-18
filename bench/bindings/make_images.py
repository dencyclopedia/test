"""10 test images (SYNTHETIC) for the bindings/throughput benches + one tiny image for per-call overhead.
usage: python3 make_images.py OUTDIR
img-01..10.png: 2481 x 1170 px grayscale (A4 width, about a third of a page) at 300 DPI, Liberation Serif 11 pt,
seeded scan degradation (bench/pdf/scanlib.py), consecutive passages of Pride and Prejudice (public domain).
tiny.png: one word, 300 DPI."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pdf"))
import scanlib
from PIL import Image, ImageDraw, ImageFont

out = sys.argv[1]; os.makedirs(out, exist_ok=True)
pages = scanlib.layout_pages(dpi=300, font_pt=11, n_pages=10, page_in=(8.27, 3.9), margin_in=0.5)
for i, lines in enumerate(pages, 1):
    im = scanlib.render_lines(lines, dpi=300, font_pt=11, page_in=(8.27, 3.9), margin_in=0.5)
    scanlib.degrade(im, seed=3000 + i).save(os.path.join(out, f"img-{i:02d}.png"), dpi=(300, 300))
    open(os.path.join(out, f"img-{i:02d}.gt.txt"), "w").write(scanlib.gt_text(lines))
f = ImageFont.truetype(scanlib.font_path(), 46)
im = Image.new("L", (420, 90), 255); ImageDraw.Draw(im).text((20, 15), "Tesseract", font=f, fill=0)
im.save(os.path.join(out, "tiny.png"), dpi=(300, 300))
print("ok")
