#!/usr/bin/env bash
# Install EasyOCR and PaddleOCR into fresh venvs and record what they cost on disk (GitHub runner).
# Writes <out>/install-size.csv and <out>/pip-*.log.
set -euo pipefail
OUT=${1:-bench/engines/results/timing}
mkdir -p "$OUT"
csv="$OUT/install-size.csv"
echo "item,bytes,note" > "$csv"
sp() { "$1/bin/python" -c 'import sysconfig;print(sysconfig.get_paths()["purelib"])'; }

# Tesseract: binary + libs we built, and eng model sizes
echo "tesseract-5.5.4-install,$(du -sb /opt/tess554 | cut -f1),/opt/tess554 built from source (bin+lib+include)" >> "$csv"
for d in tessdata_fast tessdata tessdata_best; do
  echo "tesseract-model-eng-$d,$(stat -c %s /opt/tessdata/$d/eng.traineddata),eng.traineddata" >> "$csv"
done

# EasyOCR default 'pip install easyocr' on Linux pulls CUDA builds of torch: measure the download only
mkdir -p "$RUNNER_TEMP/easyocr-default"
python3 -m pip download -q easyocr -d "$RUNNER_TEMP/easyocr-default" > "$OUT/pip-easyocr-default-download.log" 2>&1 || true
echo "easyocr-default-pip-download,$(du -sb "$RUNNER_TEMP/easyocr-default" | cut -f1),all wheels 'pip download easyocr' fetches (CUDA torch on Linux)" >> "$csv"
rm -rf "$RUNNER_TEMP/easyocr-default"

# EasyOCR, CPU-only torch
python3 -m venv ~/venv-easyocr
base=$(du -sb "$(sp ~/venv-easyocr)" | cut -f1)
~/venv-easyocr/bin/pip install -q --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu > "$OUT/pip-easyocr.log" 2>&1
~/venv-easyocr/bin/pip install -q --no-cache-dir easyocr >> "$OUT/pip-easyocr.log" 2>&1
echo "easyocr-cpu-site-packages,$(( $(du -sb "$(sp ~/venv-easyocr)" | cut -f1) - base )),site-packages growth: torch+torchvision CPU wheels then easyocr" >> "$csv"
~/venv-easyocr/bin/python -c "import easyocr; easyocr.Reader(['en'], gpu=False, verbose=False)"
echo "easyocr-models-en,$(du -sb ~/.EasyOCR/model | cut -f1),~/.EasyOCR/model after Reader(['en']) (detector + english recogniser)" >> "$csv"

# PaddleOCR + paddlepaddle CPU
python3 -m venv ~/venv-paddle
base=$(du -sb "$(sp ~/venv-paddle)" | cut -f1)
~/venv-paddle/bin/pip install -q --no-cache-dir paddlepaddle paddleocr > "$OUT/pip-paddle.log" 2>&1
echo "paddleocr-site-packages,$(( $(du -sb "$(sp ~/venv-paddle)" | cut -f1) - base )),site-packages growth: paddlepaddle (CPU) + paddleocr" >> "$csv"
~/venv-paddle/bin/python -c "
from paddleocr import PaddleOCR
PaddleOCR(lang='en', use_doc_orientation_classify=False, use_doc_unwarping=False, use_textline_orientation=False, enable_mkldnn=False)"
echo "paddleocr-models-en,$(du -sb ~/.paddlex/official_models | cut -f1),~/.paddlex/official_models after PaddleOCR(lang='en') default det+rec" >> "$csv"
ls ~/.paddlex/official_models >> "$OUT/pip-paddle.log"
cat "$csv"
