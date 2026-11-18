"""Method D from tesseractocr.org/pdf/ (pdf2image + pytesseract + pypdf), with ONE change: config="--dpi 300" (pdf2image images carry no DPI, so Tesseract assumes 70 DPI and makes 35x50-inch pages)."""
import io, sys
import pytesseract
from pdf2image import convert_from_path
from pypdf import PdfWriter, PdfReader

pages = convert_from_path(sys.argv[1], dpi=300)  # needs poppler
writer = PdfWriter()
for page in pages:
    pdf_bytes = pytesseract.image_to_pdf_or_hocr(page, extension="pdf", lang="eng", config="--dpi 300")
    writer.add_page(PdfReader(io.BytesIO(pdf_bytes)).pages[0])
with open(sys.argv[2], "wb") as f:
    writer.write(f)
