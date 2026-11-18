#!/usr/bin/env bash
# Training-related errors and checks, captured verbatim. usage: capture_errors.sh WORKDIR OUTDIR (after run_train.sh)
set -uo pipefail
W=$(realpath "$1"); OUT=$(realpath -m "$2"); mkdir -p "$OUT"; rm -f "$OUT/captures.jsonl"
HERE=$(cd "$(dirname "$0")" && pwd)
C="python3 $HERE/../errors/capture.py $OUT"
cd "$W/tesstrain"
M=ocra100
# 1. Do FINETUNE_TYPE / BATCH_SIZE change anything? Compare the commands make would run (dry run).
$C make-dry-run-plain -- make -n training MODEL_NAME=$M START_MODEL=eng TESSDATA=/opt/tessdata/tessdata_best MAX_ITERATIONS=10 '>' /tmp/plain.txt '2>&1;' echo lines: '$(wc -l < /tmp/plain.txt)'
$C make-dry-run-finetune-batch --note "same command list as without the variables => tesstrain ignores them" -- make -n training MODEL_NAME=$M START_MODEL=eng TESSDATA=/opt/tessdata/tessdata_best MAX_ITERATIONS=10 FINETUNE_TYPE=2 BATCH_SIZE=4 '>' /tmp/ft.txt '2>&1;' diff /tmp/plain.txt /tmp/ft.txt '&&' echo IDENTICAL
# 2. START_MODEL missing from TESSDATA
mkdir -p /tmp/emptytd
$C start-model-missing -- make training MODEL_NAME=errmissing START_MODEL=eng TESSDATA=/tmp/emptytd MAX_ITERATIONS=10 GROUND_TRUTH_DIR=data/$M-ground-truth '2>&1 | tail -15'
# 3. Fine-tuning from tessdata_fast (integer model)
$C start-model-fast -- make training MODEL_NAME=errfast START_MODEL=eng TESSDATA=/opt/tessdata/tessdata_fast MAX_ITERATIONS=10 GROUND_TRUTH_DIR=data/$M-ground-truth '2>&1 | tail -15'
# 4. Ground-truth directory empty / wrong name
$C ground-truth-missing -- make training MODEL_NAME=nosuchmodel START_MODEL=eng TESSDATA=/opt/tessdata/tessdata_best '2>&1 | tail -5'
# 5. lstmeval on the held-out list, using the final model
$C lstmeval-heldout -- lstmeval --model "$W/final-$M/$M.traineddata" --eval_listfile "$W/heldout-lstmf.list" '2>&1 | tail -4'
# 6. text2image font names (the page passes --font 'My Custom Font')
$C text2image-list-fonts -- text2image --list_available_fonts --fonts_dir /usr/share/fonts/truetype/ocr-a '2>&1 | tail -8'
$C text2image-wrong-font -- text2image --text=data/$M/all-gt --outputbase=/tmp/t2i --font="'My Custom Font'" --fonts_dir=/usr/share/fonts/truetype/ocr-a --ptsize=14 '2>&1 | tail -6'
# 7. tesseract using the model, -l with a model that is not installed
$C lang-not-installed -- tesseract "$W/gt-heldout/ho-00000.png" - -l $M '2>&1'
$C lang-installed-tessdata-dir -- tesseract "$W/gt-heldout/ho-00000.png" - --tessdata-dir "$W/final-$M" -l $M --psm 7 '2>&1'
exit 0
