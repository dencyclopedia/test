"""Method D from tesseractocr.org/pdf/ (pdf2image + pytesseract + pypdf), unchanged apart from argv paths."""
import io, sys
import pytesseract
from pdf2image import convert_from_path
from pypdf import PdfWriter, PdfReader

pages = convert_from_path(sys.argv[1], dpi=300)  # needs poppler
writer = PdfWriter()
for page in pages:
    pdf_bytes = pytesseract.image_to_pdf_or_hocr(page, extension="pdf", lang="eng")
    writer.add_page(PdfReader(io.BytesIO(pdf_bytes)).pages[0])
with open(sys.argv[2], "wb") as f:
    writer.write(f)
