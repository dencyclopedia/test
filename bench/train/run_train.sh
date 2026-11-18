#!/usr/bin/env bash
# Fine-tune eng (tessdata_best) on the OCR-A font with tesstrain; learning curve vs lines and iterations.
# usage: run_train.sh WORKDIR RESULTS_DIR        env: SIZES="100 300 1000" ITER=3000 HELDOUT=300
# Needs: tesseract + training tools on PATH, TESSDATA_PREFIX=<tessdata_best dir with configs/>, git, wget, make.
set -euo pipefail
W=$(realpath -m "$1"); RES=$(realpath -m "$2")
HERE=$(cd "$(dirname "$0")" && pwd)
SIZES=${SIZES:-"100 300 1000"}; ITER=${ITER:-3000}; HELDOUT=${HELDOUT:-300}
FONT=${FONT:-/usr/share/fonts/truetype/ocr-a/OCRA.ttf}
BEST=${TESSDATA_PREFIX:?set TESSDATA_PREFIX to the tessdata_best dir}
mkdir -p "$W" "$RES/logs" "$RES/raw"
cd "$W"

{ echo "tesseract: $(command -v tesseract)"; tesseract --version 2>&1 | head -1
  echo "lstmtraining: $(command -v lstmtraining)"; lstmtraining --version 2>&1 | head -2; } > "$RES/tools.txt"

[ -d tesstrain ] || git clone -q https://github.com/tesseract-ocr/tesstrain
git -C tesstrain log -1 --format='%H %cI %s' > "$RES/tesstrain-commit.txt"
python3 -m pip install -q -r tesstrain/requirements.txt 2>&1 | tail -2 || true
# langdata (radical-stroke.txt + script unicharsets) as the /train/ page says: make tesseract-langdata.
# Fallback (dev container only: its proxy blocks github.com/.../raw/ for wget) = same files via raw.githubusercontent.com
if ! (cd tesstrain && make tesseract-langdata) > "$RES/logs/tesseract-langdata.log" 2>&1; then
  echo "make tesseract-langdata failed; fetching the same files from raw.githubusercontent.com" | tee -a "$RES/logs/tesseract-langdata.log"
  mkdir -p tesstrain/data/langdata
  for f in radical-stroke.txt $(cd tesstrain && make -s -p -n help 2>/dev/null | sed -n 's/^TESSERACT_SCRIPTS := //p' | head -1 | tr ' ' '\n' | sed 's/$/.unicharset/'); do
    curl -fsSL -o "tesstrain/data/langdata/$f" "https://raw.githubusercontent.com/tesseract-ocr/langdata_lstm/main/$f"
  done
fi

# --- which variables does the Makefile really have? (the live /train/ page documents FINETUNE_TYPE, BATCH_SIZE)
python3 - "$W/tesstrain" "$RES/makefile-variables.json" <<'EOF'
import json, re, sys
mk = open(sys.argv[1] + "/Makefile").read(); rd = open(sys.argv[1] + "/README.md").read()
assigned = sorted(set(re.findall(r"^([A-Z][A-Z0-9_]+)\s*(?:\?|:)?=", mk, re.M)))
helped = sorted(set(re.findall(r'@echo "    ([A-Z][A-Z0-9_]+)\s', mk)))
readme = sorted(set(re.findall(r"^\s{4}([A-Z][A-Z0-9_]+)\s{2,}", rd, re.M)))
q = {v: {"in_makefile": bool(re.search(r"\b%s\b" % v, mk)), "in_readme": bool(re.search(r"\b%s\b" % v, rd))}
     for v in ("FINETUNE_TYPE", "BATCH_SIZE", "START_MODEL", "TESSDATA", "MAX_ITERATIONS", "EPOCHS", "LEARNING_RATE",
               "NET_SPEC", "RATIO_TRAIN", "TARGET_ERROR_RATE", "PSM", "TESSDATA_REPO")}
json.dump({"assigned_in_makefile": assigned, "listed_by_make_help": helped, "listed_in_readme": readme,
           "checked": q}, open(sys.argv[2], "w"), indent=2)
print(json.dumps(q, indent=1))
EOF

# --- ground truth (synthetic OCR-A lines; public-domain text)
[ -d gt-train ] || python3 "$HERE/make_lines.py" gt-train --font "$FONT" --split train --seed 1 --prefix tr
[ -d gt-heldout ] || python3 "$HERE/make_lines.py" gt-heldout --font "$FONT" --split heldout --n "$HELDOUT" --seed 2 --prefix ho
cp gt-train/tr-00000.png "$RES/raw/sample-train-line.png"; cp gt-train/tr-00000.gt.txt "$RES/raw/sample-train-line.gt.txt"

# deterministic shuffle of training lines
python3 -c "import glob,random; f=sorted(glob.glob('gt-train/*.png')); random.Random(42).shuffle(f); open('order.txt','w').write('\n'.join(f))"

evaluate() {  # evaluate MODELDIR LANG LABEL -> appends to heldout.jsonl
  python3 "$HERE/eval_heldout.py" "$W/gt-heldout" "$1" "$2" "$3" >> "$RES/heldout.jsonl"
}
rm -f "$RES/heldout.jsonl" "$RES/training_time.jsonl"
evaluate /opt/tessdata/tessdata_best eng "base eng tessdata_best"
evaluate /opt/tessdata/tessdata_fast eng "base eng tessdata_fast"

for N in $SIZES; do
  M=ocra$N
  D=tesstrain/data/$M-ground-truth
  rm -rf "$D" "tesstrain/data/$M" "tesstrain/data/$M.traineddata"; mkdir -p "$D"
  head -n "$N" order.txt | while read -r f; do cp "$f" "${f%.png}.gt.txt" "$D/"; done
  # the make command exactly as run (TARGET_ERROR_RATE lowered so every size gets the same iteration budget)
  CMD="make training MODEL_NAME=$M START_MODEL=eng TESSDATA=$BEST MAX_ITERATIONS=$ITER TARGET_ERROR_RATE=0.0001"
  echo "$CMD" > "$RES/logs/$M.command.txt"
  t0=$(date +%s.%N)
  (cd tesstrain && $CMD) > "$RES/logs/$M.make.log" 2>&1 || { echo "make training failed for $M"; tail -40 "$RES/logs/$M.make.log"; exit 1; }
  t1=$(date +%s.%N)
  cp "tesstrain/data/$M/training.log" "$RES/logs/$M.training.log" 2>/dev/null || true
  (cd tesstrain && make traineddata MODEL_NAME=$M START_MODEL=eng TESSDATA=$BEST) > "$RES/logs/$M.traineddata.log" 2>&1
  python3 - "$N" "$t0" "$t1" "$ITER" "$RES/logs/$M.training.log" >> "$RES/training_time.jsonl" <<'EOF'
import json, re, sys; n, t0, t1, it, log = sys.argv[1:]
txt = open(log).read()
last = re.findall(r"At iteration (\d+)/(\d+)/(\d+)", txt)
fin = re.findall(r"Finished! .*", txt)
print(json.dumps({"lines": int(n), "max_iterations": int(it), "wall_s_make_training": round(float(t1) - float(t0), 1),
                  "last_iteration_learning_training_sample": [int(x) for x in last[-1]] if last else None,
                  "finished_line": fin[-1] if fin else None}))
EOF
  # final model + every checkpoint written as 'best' (CER vs iteration)
  mkdir -p "final-$M"; cp "tesstrain/data/$M.traineddata" "final-$M/$M.traineddata"
  evaluate "$W/final-$M" "$M" "fine-tuned $N lines, final model (data/$M.traineddata)"
  for td in tesstrain/data/$M/tessdata_best/*.traineddata; do
    lang=$(basename "$td" .traineddata); evaluate "$W/tesstrain/data/$M/tessdata_best" "$lang" "checkpoint $N lines"
  done
  # lstmeval on the held-out lines, as the /train/ page shows it (lstmf for held-out lines)
  if [ ! -s heldout-lstmf.list ]; then
    for p in gt-heldout/*.png; do
      b=${p%.png}
      [ -f "$b.box" ] || python3 tesstrain/generate_line_box.py -i "$p" -t "$b.gt.txt" > "$b.box"
      [ -f "$b.lstmf" ] || tesseract "$p" "$b" --psm 13 lstm.train >/dev/null 2>&1
      echo "$W/$b.lstmf"
    done > heldout-lstmf.list
  fi
  lstmeval --model "$W/final-$M/$M.traineddata" --eval_listfile heldout-lstmf.list > "$RES/logs/$M.lstmeval-heldout.log" 2>&1 || true
  tail -3 "$RES/logs/$M.lstmeval-heldout.log"
done
echo done
