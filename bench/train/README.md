# Fine-tuning Tesseract 5.5.4 with tesstrain (OCR-A font)

A real `make training` fine-tune of `eng` (tessdata_best) on a font the stock model reads imperfectly, with a
held-out test set, a learning curve, verbatim logs, and a check of which tesstrain variables exist.

- **Run:** GitHub Actions `ubuntu-24.04` (Intel Xeon 6975P-C, 4 vCPU, 15 GiB) — run
  [44264145436](https://github.com/dencyclopedia/test/actions/runs/44264145436) (an earlier run,
  [44258321396](https://github.com/dencyclopedia/test/actions/runs/44258321396), gave identical CERs).
- **Engine + training tools:** Tesseract **5.5.4 built from the upstream tag** with `make training`
  (`build-tesseract.sh`; not the apt package). `lstmtraining --version` → `5.5.4` (`results/tools.txt`).
- **tesstrain:** `405346a3a67d8e4e049341d1da6a4b752e0b8351` (2025-04-18, `results/tesstrain-commit.txt`).
- **Start model:** `eng` from tessdata_best `e12c65a9…`.
- **Font:** OCR-A (`fonts-ocr-a`, John Sauter, **public domain**).
- **Data (synthetic):** one PNG per text line + `.gt.txt`, rendered by `make_lines.py` from *Pride and Prejudice*
  ch. 1–12 (public domain): first 80 % of paragraphs → 1,789 training lines; last 20 % → **300 held-out lines
  (12,594 characters)** the model never saw. 50 px text, light blur/noise/skew. OCR-A has no curly quotes, so
  “ ” were replaced by `"`. Sample: `results/raw/sample-train-line.png`.

## Method

```bash
bash build-tesseract.sh                       # 5.5.4 + training tools, pinned models
TESSDATA_PREFIX=/opt/tessdata/tessdata_best SIZES="100 300 1000" ITER=4000 \
  bash run_train.sh WORK results              # make training per size, evaluate every checkpoint
bash capture_errors.sh WORK results/errors
```

For each size N (100, 300, 1000 lines, a seeded random subset):

```bash
make training MODEL_NAME=ocraN START_MODEL=eng TESSDATA=/opt/tessdata/tessdata_best MAX_ITERATIONS=4000 TARGET_ERROR_RATE=0.0001
make traineddata MODEL_NAME=ocraN ...         # one .traineddata per 'best' checkpoint
```

Every model (stock eng best/fast, each checkpoint, the final model) is scored on the same 300 held-out lines with
`tesseract line.png - --psm 7` and `tools/metrics.py` (`eval_heldout.py`; CER = total edits / total GT chars).
`lstmeval` on the held-out lines is also recorded, as the /train/ page shows it.

## Key findings

| Model | Held-out CER | Held-out WER |
|---|---|---|
| stock `eng` tessdata_best | **1.874 %** | 10.11 % |
| stock `eng` tessdata_fast | 2.120 % | 10.73 % |
| fine-tuned, 100 lines | 0.071 % | 0.40 % |
| fine-tuned, 300 lines | **0.040 %** | 0.18 % |
| fine-tuned, 1000 lines | 0.064 % | 0.31 % |

(`results/heldout.jsonl`; per-checkpoint curve in `results/learning_curve.csv`.)

- **Training stopped early every time**: training BCER reached 0.000 and lstmtraining ended
  (`Finished! Selected model with minimal training error rate (BCER) = 0`) at iteration **1,100 / 1,600 / 2,700**
  for 100 / 300 / 1000 lines — not at MAX_ITERATIONS=4000 (`results/training_time.jsonl`).
- Wall time of `make training` (including .box/.lstmf generation): **119 s / 188 s / 355 s** on the 4-vCPU runner.
- **CER vs iterations** (100 lines): held-out CER 0.159 % after 100 iterations, 0.111 % at 300, 0.087 % at
  700, 0.071 % at 1,100. Most of the gain from 1.87 % happens in the first 100 iterations.
- **CER vs lines:** on this clean, single-font synthetic data, more lines did not help beyond 300
  (0.040 %) — 1000 lines ended at 0.064 %. The differences between sizes are a handful of characters out of 12,594;
  don't read a trend into them.
- `lstmeval` on the held-out lines reports higher numbers (BCER eval 0.118 % / 0.104 % / 0.141 %) than the CLI test:
  lstmeval works on the `--psm 13` line features without the dictionary step; the CLI number is what users see.
- The remaining errors are mostly `11` → `1l` (e.g. `Chapter 11` → `Chapter 1l`).
- Training log excerpt (100 lines):
  ```
  At iteration 15/100/100, mean rms=0.263%, delta=0.242%, BCER train=0.992%, BWER train=2.680%, skip ratio=0.000%, New best BCER = 0.992 Transitioned to stage 1 wrote best model:data/ocra100/checkpoints/ocra100_0.992_15_100.checkpoint wrote checkpoint.
  At iteration 15/1100/1100, mean rms=0.063%, delta=0.000%, BCER train=0.000%, BWER train=0.000%, skip ratio=0.000%, New best BCER = 0.000 wrote best model:data/ocra100/checkpoints/ocra100_0.000_15_1100.checkpoint wrote checkpoint.
  Finished! Selected model with minimal training error rate (BCER) = 0
  ```

## tesstrain variables (checked against the Makefile, `results/makefile-variables.json`)

- **`FINETUNE_TYPE` does not exist in the Makefile.** It is still listed in tesstrain's README
  (“Fine-tune Training Type - Impact, Plus, Layer or blank”), but nothing reads it. **`BATCH_SIZE` exists in
  neither.** `make -n training … FINETUNE_TYPE=2 BATCH_SIZE=4` prints exactly the same commands as without them
  (`results/errors/make-dry-run-finetune-batch.txt` → `IDENTICAL`): make accepts and ignores unknown variables.
- Real variables (`make help`): `TESSDATA`, `MODEL_NAME`, `DATA_DIR`, `LANGDATA_DIR`, `OUTPUT_DIR`,
  `GROUND_TRUTH_DIR`, `WORDLIST_FILE`, `NUMBERS_FILE`, `PUNC_FILE`, `START_MODEL`, `PROTO_MODEL`, `TESSDATA_REPO`,
  `MAX_ITERATIONS`, `EPOCHS`, `DEBUG_INTERVAL`, `LEARNING_RATE` (default 0.0001 with START_MODEL, else 0.002),
  `NET_SPEC`, `LANG_TYPE`, `PSM` (default 13), `RANDOM_SEED`, `RATIO_TRAIN` (0.90), `TARGET_ERROR_RATE` (0.01),
  `LOG_FILE`.

## Errors encountered (verbatim, `results/errors/`)

- START_MODEL missing from TESSDATA: `Failed to read /tmp/emptytd/eng.traineddata` /
  `make: *** [Makefile:207: data/eng/errmissing.lstm-unicharset] Error 1`. `make training` does **not** download
  the start model (there is a `$(TESSDATA)/%.traineddata` download rule, but `training` does not depend on it).
- Fine-tuning from tessdata_fast: `Error, data/eng/errfast.lstm is an integer (fast) model, cannot continue training`.
- Wrong ground-truth folder: `Makefile:221: *** found no data/nosuchmodel-ground-truth/*.gt.txt for data/nosuchmodel/all-gt.  Stop.`
- text2image with the page's `--font='My Custom Font'`: `Could not find font named 'My Custom Font'.` /
  `Pango suggested font 'DejaVu Sans'.` / `Please correct --font arg.` The OCR-A Pango name is `OCRA Medium`
  (`text2image --list_available_fonts`).
- Dev container only: `make tesseract-langdata` → `ERROR 403: Forbidden` from the sandbox proxy, and wget left
  an **empty** `radical-stroke.txt` behind that make then treats as present. On Actions the target works.

## Claims on the live /train/ page

| Claim | Result |
|---|---|
| `FINETUNE_TYPE` 0/1/2 selects fine-tune / cut top layer / scratch | **Refuted**: no such Makefile variable (ignored) |
| “Reduce `BATCH_SIZE`” for out-of-memory | **Refuted**: no such variable |
| `make training` downloads the start model into TESSDATA if missing | **Refuted** (error above) |
| fast models cannot be trained further | **Confirmed** (error above) |
| Ubuntu's tesseract-ocr package includes the training tools | **Confirmed** for Ubuntu 24.04 (5.3.4): `dpkg -S` → `tesseract-ocr: /usr/bin/lstmtraining`, `/usr/bin/text2image`, `/usr/bin/lstmeval` (dev container); this bench itself used 5.5.4 built from source |
| 100–500 lines validate the pipeline | consistent: 100 lines already gave 0.071 % held-out CER on this font |
