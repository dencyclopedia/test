#!/usr/bin/env bash
# Capture real PDF-workflow errors verbatim (bench/errors/capture.py stores stdout/stderr unedited).
# usage: capture_errors.sh WORKDIR OUTDIR     (WORKDIR = output of make_pdf.py)
set -uo pipefail
W=$1; OUT=$2; mkdir -p "$OUT"; rm -f "$OUT/captures.jsonl"
HERE=$(cd "$(dirname "$0")" && pwd)
C="python3 $HERE/../errors/capture.py $OUT"
PY=$(command -v python)
cd "$W"
cp scan.pdf in.pdf
pdfseparate -f 1 -l 1 in.pdf one.pdf
pdftoppm -r 300 -png -singlefile one.pdf one

# 1. Tesseract cannot read PDFs
$C tesseract-reads-pdf-554 -- tesseract one.pdf out
[ -x /usr/bin/tesseract ] && $C tesseract-reads-pdf-apt -- /usr/bin/tesseract --version '2>&1 | head -1;' /usr/bin/tesseract one.pdf out
# 2. 'textonly_pdf' as a config name (as written on the /pdf/ page) vs the real parameter
$C textonly-pdf-as-config --note "exit code 0 but no PDF is written" -- tesseract one.png t1 textonly_pdf ';' ls t1.*
$C textonly-pdf-as-parameter -- tesseract one.png t2 -c textonly_pdf=1 pdf ';' ls -la t2.* ';' pdfimages -list t2.pdf
# 3. model dir without configs/ (--tessdata-dir pointing at a bare tessdata_fast checkout)
mkdir -p bare; cp "$TESSDATA_PREFIX/eng.traineddata" bare/
$C pdf-config-missing --note "exit code 0 but only a .txt is written" -- tesseract one.png t3 --tessdata-dir "$W/bare" pdf ';' ls t3.*
# 4. OCRmyPDF on a file that already has text
ocrmypdf -q -l eng one.pdf ocred.pdf
$C ocrmypdf-prior-ocr -- ocrmypdf -l eng ocred.pdf again.pdf
$C ocrmypdf-prior-ocr-fix-skip-text -- ocrmypdf --skip-text -l eng ocred.pdf again.pdf
$C ocrmypdf-prior-ocr-fix-force -- ocrmypdf --force-ocr -l eng ocred.pdf again2.pdf
$C ocrmypdf-prior-ocr-fix-redo -- ocrmypdf --redo-ocr -l eng ocred.pdf again3.pdf
# 5. Encrypted PDF (user password 'secret')
qpdf --encrypt secret owner 256 -- one.pdf enc.pdf
$C ocrmypdf-encrypted -- ocrmypdf -l eng enc.pdf enc-out.pdf
$C pdftoppm-encrypted -- pdftoppm -r 300 -png enc.pdf encpg
$C pdftoppm-encrypted-fix -- pdftoppm -upw secret -r 300 -png enc.pdf encpg ';' ls encpg*
$C pdf2image-encrypted -- "$PY" -c "'from pdf2image import convert_from_path; convert_from_path(\"enc.pdf\")'"
$C encrypted-fix-qpdf-decrypt -- qpdf --password=secret --decrypt enc.pdf dec.pdf '&&' ocrmypdf -q -l eng dec.pdf dec-out.pdf '&&' pdftotext dec-out.pdf - '|' head -3
# 6. pdf2image without poppler on PATH
$C pdf2image-no-poppler --path "$(dirname "$PY"):/usr/bin/nonexistent" -- "$PY" -c "'from pdf2image import convert_from_path; convert_from_path(\"one.pdf\")'"
# 7. OCRmyPDF dependencies: PATH with ONLY tesseract + the venv (no gs, no poppler, no pngquant/jbig2)
mkdir -p onlytess; ln -sf "$(command -v tesseract)" onlytess/tesseract
MIN="$W/onlytess:$(dirname "$PY")"
$C ocrmypdf-no-gs-no-poppler --path "$MIN" -- ocrmypdf -l eng one.pdf min.pdf '&&' /usr/bin/pdffonts min.pdf
$C ocrmypdf-no-gs-pdfa --path "$MIN" -- ocrmypdf --output-type pdfa -l eng one.pdf min-pdfa.pdf
$C ocrmypdf-no-gs-optimize2 --path "$MIN" -- ocrmypdf --optimize 2 -l eng one.pdf min-o2.pdf
$C ocrmypdf-no-gs-optimize3 --path "$MIN" -- ocrmypdf --optimize 3 -l eng one.pdf min-o3.pdf
$C ocrmypdf-no-tesseract --path "$(dirname "$PY")" -- ocrmypdf -l eng one.pdf none.pdf
# 8. pdfsandwich: which tesseract it runs, and what it does to the page image
$C pdfsandwich-verbose -- pdfsandwich -verbose -lang eng -o sw.pdf one.pdf ';' pdfimages -list sw.pdf
exit 0
