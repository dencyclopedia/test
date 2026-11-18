# Page segmentation modes: all 14 `--psm` values on five kinds of image

What each `--psm` actually returns, measured, with every raw output kept so the site can show it.

## Method
- Tesseract 5.5.4, tessdata (standard) eng `ced78752`, `--oem 1`, `OMP_THREAD_LIMIT=1`:
  `tesseract <image> stdout --tessdata-dir /opt/tessdata/tessdata -l eng --oem 1 --psm <0..13>`
- Samples (synthetic, `corpus/manifest.json`), 34 images:
  - `page`: 3 clean pages, DejaVu Serif 12 pt, 300 DPI
  - `receipt`: 4 clean receipts (80 mm, 300 DPI)
  - `line`: 8 single text lines; `word`: 10 single words (incl. `0x7FFF`, `$42.99`, `2026-11-18`)
  - `sparse`: 4 scattered labels (shipping label, product label, room sign, asset tag) + 5 light-mode UI screenshots
- Because `--psm 0` fails with `--oem 1`, it was also run without `--oem` (default) to record what OSD reports
  (`results/osd_default_oem.csv`, `results/raw/psm0-default-oem/`).
- Metrics: CER/WER (`tools/metrics.py`) and `word_recall_unordered` (share of ground-truth words found anywhere in the
  output; reading order ignored) because labels and screenshots have no single reading order.

```sh
python3 bench/psm/run.py
```
Outputs: `results/summary.csv` (per PSM x sample type), `results/per_image.csv`,
`results/raw/psm<N>/<image id>.txt` (stdout) and `.err` (stderr) for all 476 runs.

## Results (mean CER per sample type; "no text" = empty output on every image)

| PSM | page (3) | receipt (4) | line (8) | word (10) | sparse (9) |
|---|---|---|---|---|---|
| 0 OSD only | error* | error* | error* | error* | error* |
| 1 auto + OSD | 0.00% | 8.83% | 0.62% | 1.67% | 20.62% |
| 2 auto, no OCR | no text | no text | no text | no text | no text |
| 3 auto (default) | 0.00% | 8.83% | 0.62% | 1.67% | 20.62% |
| 4 single column | 0.00% | 0.24% | 0.62% | 1.67% | 6.05% |
| 5 vertical block | 81.82% | 126.19% | 165.61% | 210.47% | 91.33% |
| 6 single block | 0.00% | 0.19% | 0.62% | 1.67% | 4.96% |
| 7 single line | 99.95% | 100.00% | 0.62% | 1.67% | 95.44% |
| 8 single word | 99.94% | 99.63% | 2.27% | 5.24% | 99.62% |
| 9 word in a circle | 100.00% | 98.68% | 23.22% | 37.81% | 99.07% |
| 10 single character | 99.92% | 99.81% | 0.62% | 1.67% | 99.39% |
| 11 sparse text | 0.00% | 5.33% | 0.62% | 1.67% | 8.53% |
| 12 sparse + OSD | 0.00% | 6.53% | 0.62% | 1.67% | 8.53% |
| 13 raw line | 99.94% | 99.63% | 2.27% | 5.24% | 99.62% |

\* `--psm 0 --oem 1` exits with "Error, OSD requires a model for the legacy engine". CER above 100% means the output
was longer than the ground truth (mostly garbage characters).

## Key findings
- PSM 0 does not work together with `--oem 1`: "Error, OSD requires a model for the legacy engine". With the default
  OEM it prints orientation and script (e.g. "Orientation in degrees: 0 ... Script: Latin") and no text. On single
  words OSD gave up ("Too few characters. Skipping this page"), so it returned nothing for all 10 word images.
- PSM 2 printed only layout information to stderr ("Orientation: 0 | WritingDirection: 0 | TextlineOrder: 2 | Deskew angle ...")
  and no text for all 34 images.
- PSM 1 and PSM 3 gave identical CER on every sample type (the pages were upright, so OSD changed nothing).
- Receipts: PSM 6 (0.19% CER) and PSM 4 (0.24%) beat the default PSM 3 (8.83%). PSM 3 reads the right-aligned
  price column as a separate block, so prices end up away from their items.
- Labels and UI screenshots: PSM 6 had the lowest CER (4.96%), then PSM 4 (6.05%) and PSM 11 (8.53%), vs 20.62% for
  PSM 3. Word recall was about the same for all four (95.2-95.6%): the words were found, the difference is order.
  On the inbox screenshot PSM 3 gave 50.3% CER and PSM 6 0.0%.
- PSM 5 (vertical text) on horizontal text produced garbage: 82-210% CER, with single letters and symbols per line.
- PSM 7, 8, 10 and 13 on a full page returned empty or near-empty output (99.9% CER); PSM 7 returned nothing at all
  for 2 of 3 pages and all 4 receipts.
- PSM 10 ("single character") still read whole lines and words in 5.5.4: lines 0.62% and words 1.67% CER, the same as PSM 7.
- Single words: PSM 7, 10, 3 and 6 all gave 1.67% CER; PSM 8 gave 5.24% and PSM 9 37.81%. Word errors in the PSM 8
  output: `0x7FFF` -> `Ox7FFF`, `$42.99` -> `$4299`, and a stray `‘` before `Netherfield` and `Wonderland`.
- PSM 8 and PSM 13 gave identical results on every sample type here.

## Limits
34 rendered images; the screenshots are light-mode, 1x. Upright pages only (rotation is covered in bench/ocr-online).
