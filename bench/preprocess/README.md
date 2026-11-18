# Preprocessing before pytesseract, and what word confidence is good for

Two questions: which common OpenCV / scikit-image steps actually help Tesseract on which kind of damage, and is
`image_to_data`'s word confidence a usable signal for "this word is probably wrong"?

## Part 1: preprocessing pipelines (`run.py`)

### Method
- Engine: pytesseract 0.3.13 -> Tesseract 5.5.4, tessdata (standard) eng, `--oem 1 --psm 3`, `OMP_THREAD_LIMIT=1`.
- Images (synthetic, `corpus/manifest.json`), 104: the 80 `degraded` pages (4 bases x 20 levels), the 18 clean 12 pt pages
  at 150 DPI (`lowres150`), 4 faded-thermal receipts and 2 simulated phone photos of receipts.
- Each pipeline starts from `cv2.imread(path, cv2.IMREAD_COLOR)` and hands a numpy array to `pytesseract.image_to_string`:
  `raw` (as loaded), `gray`, `upscale2x` (cubic), `otsu`, `adaptive` (Gaussian, block 31, C 15), `sauvola`
  (scikit-image, window 25, k 0.2), `deskew` (angle from `minAreaRect` of the dark pixels), `denoise`
  (`fastNlMeansDenoising`, h 15), `median3`, `denoise+otsu`, `deskew+otsu`, `upscale2x+otsu`, `full` (denoise -> deskew -> otsu).
  Parameters are fixed, not tuned per image.
- CER from `tools/metrics.py`; mean per category / level.

```sh
python3 bench/preprocess/run.py
```
Outputs: `results/summary.csv` (category x pipeline, with `delta_vs_raw`), `results/summary_by_level.csv`,
`results/per_image.csv`, `results/raw/<pipeline>/<image id>.txt`.

### Results: mean CER by degradation level (4 pages per level)

| level | raw | upscale2x | otsu | adaptive | sauvola | deskew | denoise | median3 | full |
|---|---|---|---|---|---|---|---|---|---|
| none | 0.17% | 0.13% | 0.17% | 0.17% | 0.13% | 0.17% | 0.17% | 0.17% | 0.17% |
| lighting gradient 75% | 23.71% | 60.07% | 23.83% | **0.17%** | **0.17%** | 23.71% | 23.71% | 24.00% | 23.88% |
| noise sigma 30 | 0.17% | 0.13% | 0.13% | 95.94% | 23.45% | 0.17% | 0.13% | 0.17% | 0.17% |
| noise sigma 50 | 5.56% | 10.50% | 4.66% | 100.00% | 100.00% | 5.56% | 1.52% | **0.13%** | 0.97% |
| skew 3 deg | 0.47% | 1.27% | 0.47% | 0.64% | 0.39% | **0.13%** | 0.47% | 0.52% | 0.13% |
| skew 5 deg | 1.05% | 2.03% | 1.23% | 1.33% | 1.58% | **0.09%** | 1.01% | 1.06% | 0.09% |
| low contrast (ink 150 / paper 190) | 0.17% | 0.13% | 0.17% | 0.17% | 107.99% | 0.17% | 0.13% | 0.13% | 0.63% |
| blur sigma 3 | 0.09% | 0.09% | 0.26% | 0.09% | 5.45% | 0.09% | 0.13% | 0.09% | 0.66% |
| JPEG q30 | 0.17% | 0.13% | 0.17% | 0.13% | 0.13% | 0.17% | 0.17% | 0.17% | 0.21% |
| phone photo level 2 | 0.82% | 2.46% | 0.95% | 14.42% | **0.05%** | 0.82% | 0.14% | 0.18% | 0.22% |

Receipts and low resolution (mean CER):

| category | n | raw | sauvola | denoise+otsu | upscale2x | median3 |
|---|---|---|---|---|---|---|
| faded thermal receipts | 4 | 26.11% | **1.87%** | 8.49% | 26.81% | 11.48% |
| receipt phone photos | 2 | 19.71% | **4.32%** | 19.85% | 19.34% | 19.60% |
| clean pages at 150 DPI | 18 | 0.09% | 0.07% | 0.09% | 0.06% | 1.09% |

### Which step helps which degradation
| degradation | helped | hurt |
|---|---|---|
| uneven lighting (strong) | adaptive threshold, Sauvola (23.71% -> 0.17%) | 2x upscale (-> 60.07%) |
| heavy noise | median 3x3 (5.56% -> 0.13%), NL-means denoise (1.52%) | adaptive (100%), Sauvola (100%), 2x upscale (10.50%) |
| skew | deskew (1.05% -> 0.09% at 5 deg) | 2x upscale |
| phone photo | Sauvola (0.82% -> 0.05%), denoise (0.14%) | adaptive (14.42%), 2x upscale (2.46%) |
| faded receipts | Sauvola (26.11% -> 1.87%), denoise+Otsu (8.49%) | adaptive (95.39%) |
| low contrast, blur, JPEG | nothing needed (already 0.09-0.17%) | Sauvola on low contrast (107.99%) and blur (5.45%) |
| 150 DPI clean pages | 2x upscale, marginal (0.09% -> 0.06%) | median 3x3 (1.09%) |

### Key findings
- No single pipeline wins: every step that rescued one kind of damage wrecked another. Sauvola took faded receipts
  from 26.11% to 1.87% CER but made low-contrast pages unreadable (107.99%); adaptive thresholding fixed the 75%
  lighting gradient (23.71% -> 0.17%) but destroyed noisy pages (95.94% at noise sigma 30).
- Global Otsu changed little (within 0.9 percentage points of raw on every level): Tesseract already
  binarises internally with Otsu by default.
- Deskewing fixed skew: 5 degree pages went from 1.05% to 0.09% CER.
- A 3x3 median filter was the best fix for heavy Gaussian noise (5.56% -> 0.13%), better than NL-means denoising (1.52%).
- 2x upscaling of 300 DPI images hurt more often than it helped (lighting gradient 60.07%, noise sigma 50 10.50%);
  on 150 DPI pages it gave a marginal gain (0.09% -> 0.06%).
- The "full" chain (denoise -> deskew -> Otsu) was never the best and was worse than raw on low-contrast and
  blurred pages (e.g. blur 0.09% -> 0.66%).
- Surprise: the DPI header matters. pytesseract hands Tesseract a temporary PNG without a resolution, so Tesseract
  estimates one. On the 5 degree skew pages the CLI with the file's correct 300 DPI header gave 19.89% CER
  (bench/accuracy) but pytesseract `raw` gave 1.05%. On the Carlito page alone: 76.2% CER with the 300 DPI header;
  removing the header (Tesseract then printed "Estimating resolution as 412") gave a clean read. Checked with
  `tesseract <png with / without dpi> stdout --oem 1 --psm 3` on `corpus/degraded/doyle_carlito_skew5.png`.

## Part 2: word confidence (`confidence.py`)

### Method
- `pytesseract.image_to_data` (Tesseract 5.5.4, standard eng, OEM 1, PSM 3, no preprocessing) on 285 images: the
  clean (189), degraded (80) and receipt (16) sets. 52,063 words with `conf >= 0`.
- Alignment: ground truth and OCR text are normalised as in `tools/metrics.py` and split on spaces; OCR words keep the
  `image_to_data` order. `difflib.SequenceMatcher(autojunk=False)` aligns the two word sequences; an OCR word is
  **correct** if it falls inside a matching block (exactly equal to the aligned ground-truth word, case and
  punctuation included), otherwise **incorrect**. Words that were read correctly but output in a different order (receipt
  prices) can count as incorrect, so the error share is an upper bound.
- For each threshold t: keep words with conf >= t, then report the share of kept words that are correct (precision),
  the share of all correct words kept, and the share of all incorrect words removed.

Outputs: `results/confidence_words.csv` (every word), `results/confidence_hist.csv` (5-point bins),
`results/confidence_thresholds.csv`, `results/raw/tsv/<image id>.tsv`, `results/meta_confidence.json`.

### Results
49,904 words correct, 2,159 incorrect. Median confidence: 96.3 for correct words, 55.7 for incorrect ones.

| keep words with conf >= | correct words kept | wrong words removed | kept words that are correct |
|---|---|---|---|
| 0 (keep all) | 100.0% | 0.0% | 95.85% |
| 50 | 99.49% | 44.1% | 97.62% |
| 60 | 99.11% | 54.4% | 98.04% |
| 70 | 98.50% | 63.8% | 98.43% |
| 80 | 97.41% | 74.8% | 98.89% |
| 90 | 94.24% | 85.3% | 99.33% |
| 95 | 83.90% | 92.1% | 99.59% |

### Key findings
- Confidence separates right from wrong words reasonably well: 41,870 of 49,904 correct words (83.9%) scored 95 or
  more, while the incorrect words were spread over the whole range (172 of 2,159 below 5).
- The threshold with the best balance (maximum of mean of "correct kept" and "wrong removed") was **90**: it flags
  85.3% of the wrong words while flagging 5.8% of the correct ones.
- If losing correct words is costly (e.g. you only want to highlight words for review), 60-70 is the practical range:
  it keeps 98.5-99.1% of correct words and still catches 54-64% of the wrong ones.
- Even at conf >= 95, 171 wrong words remained (8% of all wrong words): high confidence is not a guarantee.

## Limits
Synthetic pages, one degradation at a time; fixed preprocessing parameters (tuned parameters may change the ranking).
