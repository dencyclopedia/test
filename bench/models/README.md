# tessdata_fast vs tessdata (standard) vs tessdata_best, and OEM 0/1/2/3

Does the bigger model read better, and does the legacy engine still help? Tesseract 5.5.4, accuracy only
(speed per model is measured on GitHub Actions: `bench/accuracy/results/timing/timing-models.csv`).

## Method
- Engine: Tesseract 5.5.4 built from source (`/opt/tess554/bin/tesseract`), Leptonica 1.82.
- Models, pinned: tessdata_fast `87416418`, tessdata `ced78752`, tessdata_best `e12c65a9` (full hashes in `results/meta.json`).
- Images (from `corpus/manifest.json`, all synthetic):
  - `eng-clean`: 18 clean pages, 12 pt, 300 DPI, 6 fonts x 3 passages
  - `eng-degraded`: 32 pages, 4 bases x 8 levels (none, blur sigma 2, noise sigma 30, JPEG q50, skew 3 deg, 75% lighting gradient, low contrast ink 150/paper 190, phone photo level 1)
  - `eng-receipt`: 10 clean receipts
  - other languages: 2 UDHR pages each for deu, fra, rus, chi_sim, ara, hin
- Command: `tesseract <image> stdout --tessdata-dir <model dir> -l <lang> --oem <0|1|2|3> --psm 3`, `OMP_THREAD_LIMIT=1`.
  fast/best with `--oem 0` were tried on the clean pages only, to record the error.
- CER/WER: `tools/metrics.py`. Means are per-image means.

```sh
python3 bench/models/run.py
```
Outputs: `results/summary.csv`, `results/per_image.csv`, `results/raw/<model>-oem<N>/...` (every output text).

## Results (mean CER, OEM 1, PSM 3)

| group | n | fast | standard | best |
|---|---|---|---|---|
| eng clean pages | 18 | 0.07% | 0.07% | 0.07% |
| eng degraded pages | 32 | 3.06% | 3.14% | 3.13% |
| eng receipts | 10 | 17.78% | 18.27% | 18.28% |
| deu | 2 | 0.00% | 0.00% | 0.00% |
| fra | 2 | 0.36% | 0.39% | 0.27% |
| rus | 2 | 0.18% | 0.18% | 0.18% |
| hin | 2 | 0.66% | 0.65% | 0.65% |
| ara | 2 | 2.57% | 2.69% | 1.98% |
| chi_sim | 2 | 3.69% | 91.82% | 72.65% |

OEM with tessdata (standard), mean CER:

| group | OEM 0 legacy | OEM 1 LSTM | OEM 2 legacy+LSTM | OEM 3 default |
|---|---|---|---|---|
| eng clean | 0.41% | 0.07% | 0.09% | 0.09% |
| eng degraded | 3.44% | 3.14% | 3.14% | 3.14% |
| eng receipts | 19.62% | 18.27% | 18.30% | 18.30% |
| rus | 3.45% | 0.18% | 0.87% | 0.87% |
| fra | 0.87% | 0.39% | 0.39% | 0.39% |
| ara, hin | error | 2.69%, 0.65% | error | 2.69%, 0.65% |

## Key findings
- On English, the three model sets were practically tied: clean pages 0.07% CER for fast, standard and best; degraded
  pages 3.06% (fast), 3.14% (standard), 3.13% (best); receipts 17.78%, 18.27%, 18.28% (Tesseract 5.5.4, OEM 1, PSM 3).
  On this corpus, tessdata_best did not buy English accuracy.
- tessdata_best helped Arabic (1.98% vs 2.57% fast and 2.69% standard) and French slightly (0.27% vs 0.36% / 0.39%).
- Chinese (chi_sim): 3.69% CER with fast but 91.82% with standard and 72.65% with best. Standard and best put a space
  between most Chinese characters; fast did not. See bench/languages (CER with whitespace removed, and
  `-c preserve_interword_spaces=1`) for how much of this is spacing.
- The legacy engine (OEM 0) was worse than LSTM everywhere it ran: English clean 0.41% vs 0.07%, Russian 3.45% vs 0.18%.
- OEM 3 ("default") with tessdata (standard) gave byte-identical output to OEM 2 (legacy+LSTM) on all 60 English
  images, not to OEM 1: with the standard models, leaving out `--oem` runs the combined engine. Combined mode was
  slightly worse than LSTM-only on English (0.09% vs 0.07% on clean pages) and on Russian (0.87% vs 0.18%).
- Legacy data is missing from tessdata_fast and tessdata_best entirely, and from tessdata (standard) for ara and hin:
  `--oem 0` / `--oem 2` there fails with "Error: Tesseract (legacy) engine requested, but components are not present in ...".
- Receipts are hard for every model (about 18% CER), mostly because PSM 3 reads the right-aligned price column as a
  separate block, so prices come out away from their item names (see bench/psm for PSM 4/6 on receipts).
- A 75% lighting gradient defeated all models equally (23.7% CER for fast, standard and best).

## Limits
Synthetic, rendered pages; 2 pages per non-English language; one run per image (output is deterministic).
