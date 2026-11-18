# Tesseract 5.5.4 vs EasyOCR vs PaddleOCR (CPU)

Accuracy on a shared subset of the corpus, plus speed and install footprint measured on a GitHub Actions runner.

## Method
- Subset (`subset.py`, 56 synthetic images): 6 clean pages (300 DPI, 12 pt; DejaVu Serif, Carlito, DejaVu Sans Mono),
  16 degraded pages (2 bases x blur sigma 2, noise sigma 30, JPEG q30, skew 3 deg, 75% lighting gradient, low contrast,
  phone photo 1 and 2), all 16 receipts (10 clean, 4 faded, 2 phone photos), 10 UI screenshots (5 UIs x light/dark, 1x),
  and 2 UDHR pages each for deu, rus, chi_sim, ara.
- Tesseract 5.5.4, tessdata (standard) `ced78752`, `--oem 1 --psm 3 -l <lang>` (`run.py tesseract`).
- EasyOCR 1.7.2 with CPU-only torch 2.15.0+cpu, `Reader([lang] (+ 'en' for non-English), gpu=False)`,
  `readtext(detail=1, paragraph=False)` (`run_easyocr.py`).
- PaddleOCR 3.7.0 / paddlepaddle 3.3.1 (CPU), default models for each language, downloaded from Hugging Face
  (`PADDLE_PDX_MODEL_SOURCE=huggingface`): English used PP-OCRv6_medium_det + PP-OCRv6_medium_rec; Russian and
  Arabic used PP-OCRv5_server_det + eslav/arabic PP-OCRv5_mobile_rec. Document orientation, unwarping and text-line
  orientation off; `enable_mkldnn=False` (see findings) (`run_paddleocr.py`).
- EasyOCR and PaddleOCR return boxes, not page text. Page text is rebuilt by `subset.lines_from_boxes`: boxes whose
  vertical centres are within half a box height form a line, lines top to bottom, boxes left to right (right to left
  for Arabic). This favours row-by-row reading (receipts, tables) and fails on skewed pages (see limits).
- Metrics: CER/WER (`tools/metrics.py`) and `word_recall_unordered` (order-independent share of ground-truth words found).
- Speed and footprint: `.github/workflows/bench-engines-timing.yml` (`timing.py`, `footprint.sh`) on `ubuntu-24.04`,
  run [44257198509](https://github.com/dencyclopedia/test/actions/runs/44257198509): Intel Xeon 6975P-C, 4 cores,
  Python 3.12. Median of 5 runs after 1 warm-up per image; model loaded once (EasyOCR/PaddleOCR), Tesseract timed as
  the whole CLI call with `OMP_THREAD_LIMIT=1`.

```sh
python3 bench/engines/run.py tesseract
<easyocr venv>/bin/python bench/engines/run_easyocr.py
PADDLE_PDX_MODEL_SOURCE=huggingface <paddle venv>/bin/python bench/engines/run_paddleocr.py
python3 bench/engines/run.py score
```
Outputs: `results/summary.csv`, `results/per_image.csv`, `results/raw/<engine>/...`; timing and footprint in
`results/timing/` (`timing-engines.csv`, `install-size.csv`, `meta.json`, pip logs).

## Accuracy (mean CER; word recall in brackets)

| set | n | Tesseract 5.5.4 | EasyOCR 1.7.2 | PaddleOCR 3.7.0 |
|---|---|---|---|---|
| clean pages | 6 | **0.04%** (99.8%) | 2.49% (89.1%) | 0.63% (96.7%) |
| degraded pages | 16 | 3.26% (95.5%) | 7.31% (90.9%) | **0.39%** (98.0%) |
| receipts | 16 | 20.41% (83.3%) | 6.17% (78.3%) | **1.18%** (98.9%) |
| UI screenshots | 10 | 23.43% (90.7%) | 12.24% (80.6%) | **5.98%** (99.7%) |
| German | 2 | **0.00%** | 0.57% | **0.00%** |
| Russian | 2 | **0.18%** | 0.78% | 0.57% |
| Chinese (Simplified) | 2 | 91.82% | 5.12% | **1.91%** |
| Arabic | 2 | 2.69% | **2.20%** | 2.55% |

## Speed (GitHub Actions, seconds per image, median)

| image | Tesseract (CLI, 1 thread) | EasyOCR 1 thread | EasyOCR all cores | PaddleOCR 1 thread | PaddleOCR all cores |
|---|---|---|---|---|---|
| 300 DPI page (3 pages) | 0.83-1.10 | 22.8-39.8 | 13.6-23.1 | 31.9-47.8 | 25.3-38.8 |
| receipt (2) | 0.36-0.37 | 7.7-8.9 | 4.2-4.8 | 10.2-12.1 | 8.7-10.4 |
| screenshot 1000x600 (2) | 0.25-0.37 | 3.9-4.0 | 2.1-2.2 | 6.6-7.3 | 5.5-6.2 |
| model load (once) | in each call | 3.1 s | 3.2 s | 1.8 s | 1.7 s |

## Install footprint (GitHub Actions, bytes measured with `du -sb` / `stat`)

| item | size |
|---|---|
| Tesseract 5.5.4 built from source, `/opt/tess554` (binary, shared + static libs, headers) | 265.6 MB |
| eng.traineddata: fast / standard / best | 4.1 / 23.5 / 15.4 MB |
| `pip download easyocr` default on Linux (pulls CUDA builds of torch + nvidia wheels) | 3,151 MB |
| EasyOCR with CPU-only torch: site-packages growth | 1,405 MB |
| EasyOCR English models (`~/.EasyOCR/model`) | 98.3 MB |
| paddlepaddle (CPU) + paddleocr: site-packages growth | 1,329 MB |
| PaddleOCR English models (`~/.paddlex/official_models`) | 139.2 MB |

## Key findings
- On clean pages Tesseract was the most accurate: 0.04% CER vs 0.63% PaddleOCR and 2.49% EasyOCR (6 pages, 300 DPI).
- PaddleOCR was the most robust: 0.39% CER on every degradation level, including the 75% lighting gradient where
  Tesseract fell to 24.61% (Tesseract was 0.18-0.37% on the other levels).
- On receipts and UI screenshots PaddleOCR led (1.18% and 5.98% CER) and Tesseract trailed (20.41% and 23.43%), but much
  of Tesseract's gap is reading order: with PSM 3 it outputs price columns and table columns as separate blocks. Its word
  recall (83.3% receipts, 90.7% screenshots) was higher than EasyOCR's (78.3%, 80.6%); with `--psm 6` Tesseract got
  0.19% CER on clean receipts (bench/psm).
- Chinese: PaddleOCR 1.91%, EasyOCR 5.12%, Tesseract 91.82%, the last mostly from spaces between characters (1.93%
  with whitespace ignored; see bench/languages).
- Speed: Tesseract read a 300 DPI page in 0.83-1.10 s on one core; EasyOCR needed 13.6-23.1 s and PaddleOCR 25.3-38.8 s
  using all 4 cores, i.e. roughly 15-35x slower.
- Size: a default `pip install easyocr` on Linux downloads 3.15 GB (CUDA torch). With CPU-only torch EasyOCR still adds
  1.40 GB, PaddleOCR 1.33 GB, plus 98 MB / 139 MB of English models; Tesseract's English model is 4-23 MB.
- Problems met: with paddlepaddle 3.3.1 the default oneDNN path failed on our CPU ("ConvertPirAttribute2RuntimeAttribute
  not support"); `enable_mkldnn=False` fixed it. In the 16 GB dev container, PaddleOCR's PP-OCRv5_server_det tried to
  allocate 20-23 GB on the Arabic and Russian pages and failed (MemoryError) even with `text_det_limit_side_len=2560`;
  those 4 pages were run with `text_det_limit_type="max", text_det_limit_side_len=960` (all other images use defaults).
- EasyOCR's skewed-page result (45.6% CER at 3 degrees) is mostly our box-to-line reconstruction putting words from
  neighbouring lines together, plus misreadings; treat EasyOCR's degraded number with that in mind.

## Limits
56 synthetic images; no GPU; engine defaults, no tuning. Box-to-text reconstruction for EasyOCR/PaddleOCR is our own
heuristic. Dev-container runs are accuracy only; all speed numbers come from the Actions run above.
