#!/usr/bin/env bash
# Capture real Tesseract / wrapper error messages verbatim, each followed by the fix that worked.
# usage: run_errors.sh OUTDIR       env: PY (python with pytesseract, pillow, opencv-python-headless, pdf2image),
#        T554 (tesseract 5.5.4 binary), TD (tessdata root with tessdata_fast/ tessdata/ tessdata_best/)
set -uo pipefail
OUT=$(realpath -m "$1"); mkdir -p "$OUT"; rm -f "$OUT/captures.jsonl"
HERE=$(cd "$(dirname "$0")" && pwd)
PY=${PY:-python3}; T=${T554:-/opt/tess554/bin/tesseract}; TD=${TD:-/opt/tessdata}
C="python3 $HERE/capture.py $OUT"
W=$(mktemp -d); cd "$W"
TB=$(dirname "$T"); PYB=$(dirname "$PY")

# inputs (synthetic)
$PY - <<'EOF'
from PIL import Image, ImageDraw, ImageFont
f = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf", 46)
im = Image.new("L", (900, 120), 255); ImageDraw.Draw(im).text((20, 30), "It is a truth universally acknowledged", font=f, fill=0)
im.save("line.png", dpi=(300, 300)); im.save("line-nodpi.png"); im.convert("RGB").save("line-rgb.jpg")
Image.new("L", (900, 300), 255).save("blank.png", dpi=(300, 300))
im.crop((20, 30, 60, 60)).save("tiny.png", dpi=(300, 300))
Image.new("L", (2, 2), 0).save("2x2.png", dpi=(300, 300))
Image.new("L", (3, 40), 0).save("vbar.png", dpi=(300, 300))  # a 3x40 px black bar
open("notanimage.png", "w").write("this is text, not a PNG\n")
EOF
cp line.png line.gif 2>/dev/null; $PY -c "from PIL import Image; Image.open('line.png').save('line.webp'); Image.open('line.png').save('line.bmp')"
printf '<svg xmlns="http://www.w3.org/2000/svg" width="200" height="50"><text x="5" y="35">Hello</text></svg>' > line.svg

# --- pytesseract cannot find the tesseract binary
$C pytesseract-not-found --path "$PYB" -- "$PY" -c "'import pytesseract; from PIL import Image; print(pytesseract.image_to_string(Image.open(\"line.png\")))'"
$C pytesseract-not-found-fix --path "$PYB" -- "$PY" -c "'import pytesseract; from PIL import Image; pytesseract.pytesseract.tesseract_cmd = \"$T\"; print(pytesseract.image_to_string(Image.open(\"line.png\")))'"
# --- language pack missing
$C lang-missing-554 --env TESSDATA_PREFIX="$TD/tessdata_fast" -- "$T" line.png - -l xyz
$C lang-missing-fra-onlyeng --env TESSDATA_PREFIX="$W/onlyeng" -- mkdir -p "$W/onlyeng" ';' cp "$TD/tessdata_fast/eng.traineddata" "$W/onlyeng/" ';' "$T" line.png - -l fra
$C lang-missing-apt-534 -- /usr/bin/tesseract line.png - -l fra
$C lang-missing-fix-tessdata-dir -- "$T" line.png - -l fra --tessdata-dir "$TD/tessdata_fast"
$C lang-plus-one-missing --env TESSDATA_PREFIX="$W/onlyeng" -- "$T" line.png - -l eng+fra
$C pytesseract-lang-missing --env TESSDATA_PREFIX="$W/onlyeng" -- "$PY" -c "'import pytesseract; pytesseract.pytesseract.tesseract_cmd=\"$T\"; print(pytesseract.image_to_string(\"line.png\", lang=\"fra\"))'"
# --- TESSDATA_PREFIX wrong (pointing at the parent dir, or at a dir that does not exist)
$C tessdata-prefix-parent --env TESSDATA_PREFIX="$TD" -- "$T" line.png - -l eng
$C tessdata-prefix-nonexistent --env TESSDATA_PREFIX=/nonexistent/tessdata -- "$T" line.png - -l eng
$C tessdata-prefix-fix --env TESSDATA_PREFIX="$TD/tessdata_fast" -- "$T" line.png - -l eng
$C tessdata-dir-trailing-file -- "$T" line.png - -l eng --tessdata-dir "$TD/tessdata_fast/eng.traineddata"
# --- unsupported / broken image formats
$C format-svg -- "$T" line.svg - --tessdata-dir "$TD/tessdata_fast"
$C format-text-as-png -- "$T" notanimage.png - --tessdata-dir "$TD/tessdata_fast"
$C format-webp -- "$T" line.webp - --tessdata-dir "$TD/tessdata_fast"
$C format-bmp -- "$T" line.bmp - --tessdata-dir "$TD/tessdata_fast"
$C format-missing-file -- "$T" nosuchfile.png - --tessdata-dir "$TD/tessdata_fast"
$C pytesseract-svg -- "$PY" -c "'import pytesseract; from PIL import Image; pytesseract.pytesseract.tesseract_cmd=\"$T\"; print(pytesseract.image_to_string(Image.open(\"line.svg\")))'"
# --- resolution / page warnings
$C estimating-resolution -- "$T" line-nodpi.png - --tessdata-dir "$TD/tessdata_fast"
$C estimating-resolution-fix-dpi -- "$T" line-nodpi.png - --tessdata-dir "$TD/tessdata_fast" --dpi 300
$C empty-page -- "$T" blank.png - --tessdata-dir "$TD/tessdata_fast"
$C empty-page-psm7 -- "$T" blank.png - --tessdata-dir "$TD/tessdata_fast" --psm 7
$C too-small-to-scale -- "$T" 2x2.png - --tessdata-dir "$TD/tessdata_fast"
$C vbar-psm7 --note "prints internal statistics instead of an error" -- "$T" vbar.png - --tessdata-dir "$TD/tessdata_fast" --psm 7
$C too-small-crop -- "$T" tiny.png - --tessdata-dir "$TD/tessdata_fast" --psm 7
$C too-small-crop-fix-upscale -- "$PY" -c "'from PIL import Image; im=Image.open(\"tiny.png\"); im.resize((im.width*4, im.height*4), Image.LANCZOS).save(\"tiny4.png\", dpi=(300,300))'" '&&' "$T" tiny4.png - --tessdata-dir "$TD/tessdata_fast" --psm 7
# --- OEM / model mismatches
$C oem0-tessdata-fast -- "$T" line.png - --tessdata-dir "$TD/tessdata_fast" --oem 0
$C oem0-tessdata-best -- "$T" line.png - --tessdata-dir "$TD/tessdata_best" --oem 0
$C oem0-tessdata-standard -- "$T" line.png - --tessdata-dir "$TD/tessdata" --oem 0
$C oem2-tessdata-fast -- "$T" line.png - --tessdata-dir "$TD/tessdata_fast" --oem 2
$C psm-invalid -- "$T" line.png - --tessdata-dir "$TD/tessdata_fast" --psm 14
$C psm-old-syntax -- "$T" line.png - --tessdata-dir "$TD/tessdata_fast" -psm 7
# --- config names that are not config files
$C pdf-config-missing -- mkdir -p bare ';' cp "$TD/tessdata_fast/eng.traineddata" bare/ ';' "$T" line.png out --tessdata-dir "$W/bare" pdf ';' ls out.*
$C textonly-pdf-as-config --env TESSDATA_PREFIX="$TD/tessdata_fast" -- "$T" line.png out2 textonly_pdf ';' ls out2.*
# --- pytesseract timeout, OpenCV threshold on a colour image
$C pytesseract-timeout -- "$PY" -c "'import pytesseract; pytesseract.pytesseract.tesseract_cmd=\"$T\"; print(pytesseract.image_to_string(\"line.png\", timeout=0.01, config=\"--tessdata-dir $TD/tessdata_fast\"))'"
$C opencv-threshold-colour -- "$PY" -c "'import cv2; img=cv2.imread(\"line-rgb.jpg\"); cv2.threshold(img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)'"
$C opencv-threshold-colour-fix -- "$PY" -c "'import cv2; img=cv2.imread(\"line-rgb.jpg\"); g=cv2.cvtColor(img, cv2.COLOR_BGR2GRAY); print(cv2.threshold(g, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[0])'"
# --- PDF input (more in bench/pdf/results/errors)
$PY -c "from PIL import Image; Image.open('line.png').save('line.pdf', resolution=300)"
$C tesseract-pdf-input -- "$T" line.pdf - --tessdata-dir "$TD/tessdata_fast"
$C pdf2image-no-poppler --path "$PYB" -- "$PY" -c "'from pdf2image import convert_from_path; convert_from_path(\"line.pdf\")'"
# --- Node: a pdftoppm wrapper with no poppler-utils on PATH
NODEB=$(dirname "$(command -v node)"); mkdir -p "$W/wh"; ln -sf "$(command -v which)" "$W/wh/which"; ln -sf "$(command -v find)" "$W/wh/find"; NODEB="$NODEB:$W/wh"  # node + `which` + `find`, no poppler
$C node-pdftoppm-enoent --path "$NODEB" -- node "$HERE/node/pdftoppm-missing.js" node-pdftoppm "$W/line.pdf"
$C node-poppler-missing --path "$NODEB" -- node "$HERE/node/pdftoppm-missing.js" node-poppler "$W/line.pdf"
$C node-pdftoppm-fix --path "$NODEB:/usr/bin" -- node "$HERE/node/pdftoppm-missing.js" node-pdftoppm "$W/line.pdf"
# --- Tess4J newest release vs Ubuntu 24.04's leptonica 1.82 (see bench/bindings)
J=$HERE/../bindings/java
if [ -d "$J/target/classes" ]; then
  $C tess4j-5.16-leptonica-1.82 -- "(cd $J && rm -rf target/lib && mvn -q -B package -DskipTests -Dtess4j.version=5.16.0 >/dev/null 2>&1)" ';' java -Djna.library.path="$TB/../lib" -cp "'$J/target/classes:$J/target/lib/*'" bench.Harness "$TD/tessdata_fast" eng default 0 line.png line.png '2>&1 | grep -v -E "^Picked up|SLF4J" | head -8'
  $C tess4j-5.14-fix -- "(cd $J && rm -rf target/lib && mvn -q -B package -DskipTests -Dtess4j.version=5.14.0 >/dev/null 2>&1)" ';' java -Djna.library.path="$TB/../lib" -cp "'$J/target/classes:$J/target/lib/*'" bench.Harness "$TD/tessdata_fast" eng default 0 line.png line.png '2>&1 | grep -v -E "^Picked up|SLF4J" | cut -c1-200'
fi
"$T" --version > "$OUT/engine-version.txt" 2>&1; /usr/bin/tesseract --version >> "$OUT/engine-version.txt" 2>&1
$PY -m pip freeze > "$OUT/pip-freeze.txt" 2>/dev/null
rm -rf "$W"
echo done
