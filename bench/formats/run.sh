#!/usr/bin/env bash
# Output formats of the tesseract CLI on one corpus receipt: real files, sizes, and the CLI help.
# Usage: bash bench/formats/run.sh   (from the repo root)
set -u
cd "$(dirname "$0")/../.."
T=/opt/tess554/bin/tesseract
MODELS=/opt/tessdata/tessdata   # git checkout of tesseract-ocr/tessdata: models only, no configs/ folder
# Output-format names (hocr, pdf, tsv ...) are config files in <tessdata>/configs. A bare model checkout has none,
# so build a tessdata dir = the standard models + the configs installed with Tesseract 5.5.4.
TD=$(mktemp -d)/tessdata; mkdir -p "$TD"
ln -s $MODELS/*.traineddata "$TD"/; cp -r /opt/tess554/share/tessdata/configs "$TD"/
IMG=corpus/receipt/receipt01_dejavu-mono.png
OUT=bench/formats/results
rm -rf "$OUT"; mkdir -p "$OUT/out"
export OMP_THREAD_LIMIT=1
{
  echo "date_utc: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "machine: development container (output formats and help text only; no timings)"
  echo "cpu: $(grep -m1 'model name' /proc/cpuinfo | cut -d: -f2 | sed 's/^ //')"
  echo "os: $(. /etc/os-release; echo "$PRETTY_NAME") $(uname -r)"
  echo "models: tessdata (standard) ced78752cc61322fb554c280d13360b35b8684e4, eng; configs/ from /opt/tess554/share/tessdata (Tesseract 5.5.4 install)"
  echo "options: --oem 1 --psm 6, OMP_THREAD_LIMIT=1"
  echo "image: $IMG ($(stat -c %s $IMG) bytes)"
  echo "--- tesseract --version"
  $T --version 2>&1
} > "$OUT/meta.txt"
run() { # name, args...
  local name=$1; shift
  echo "\$ tesseract $IMG out/$name $*" >> "$OUT/commands.txt"
  $T "$IMG" "$OUT/out/$name" --tessdata-dir $TD -l eng --oem 1 --psm 6 "$@" >> "$OUT/commands.txt" 2>&1
  echo "exit=$?" >> "$OUT/commands.txt"
}
run receipt                       # txt (default)
run receipt-hocr hocr
run receipt-tsv tsv
run receipt-alto alto
run receipt-page page
run receipt-box makebox
run receipt-pdf pdf
run receipt-textonly -c textonly_pdf=1 pdf
run receipt-wrong textonly_pdf    # the form some guides print: textonly_pdf as a config file
run receipt-all txt hocr tsv alto pdf
# the same command with --tessdata-dir pointing at the bare model checkout (no configs/): what happens
echo "--- with --tessdata-dir $MODELS (no configs/ folder)" >> "$OUT/commands.txt"
echo "\$ tesseract $IMG out/noconfigs --tessdata-dir $MODELS -l eng hocr" >> "$OUT/commands.txt"
$T "$IMG" "$OUT/out/noconfigs" --tessdata-dir $MODELS -l eng --oem 1 --psm 6 hocr >> "$OUT/commands.txt" 2>&1; echo "exit=$?" >> "$OUT/commands.txt"
( cd "$OUT/out" && for f in *; do printf '%s,%s\n' "$f" "$(stat -c %s "$f")"; done ) | sort > "$OUT/sizes.csv"
sed -i '1i file,bytes' "$OUT/sizes.csv"
$T --help-extra > "$OUT/help-extra.txt" 2>&1
$T --help-psm > "$OUT/help-psm.txt" 2>&1
$T --help-oem > "$OUT/help-oem.txt" 2>&1
$T --list-langs --tessdata-dir $MODELS > "$OUT/list-langs.txt" 2>&1
$T --print-parameters > "$OUT/print-parameters.txt" 2>&1
command -v pdffonts >/dev/null && { pdffonts "$OUT/out/receipt-pdf.pdf"; pdfimages -list "$OUT/out/receipt-pdf.pdf"; pdfimages -list "$OUT/out/receipt-textonly.pdf"; } > "$OUT/pdf-inspect.txt" 2>&1
echo done
