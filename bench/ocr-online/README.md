# The site's online OCR tool (tesseract.js in the browser) vs native Tesseract 5.5.4

What the in-browser tool at `/ocr-online/` actually returns on 16 corpus images, and how that compares with the
native Tesseract 5.5.4 CLI on the same files.

## Method
- Tool under test: the site's own `ocr-online/index.html` + `assets/ocr-tool.js`, served locally from a checkout of
  the site (`python3 -m http.server 8791`), driven by Playwright 1.63.0 / Chromium 157 (`run.js`).
  The tool loads tesseract.js 5.1.1 (`tesseract.js-core` v5.1.1, `tesseract-core-simd-lstm` build) and the
  `@tesseract.js-data/<lang>/4.0.0_best_int` models from cdn.jsdelivr.net. All CDN downloads worked; nothing was blocked.
  The wasm binary of that core build carries the version string `5.1.0-280-ge20b`, i.e. a Tesseract development
  snapshot after 5.1.0, not 5.5.4 (see `results/meta.json`).
- Tool settings: defaults (Layout mode PSM 3, Enhance contrast off, second language none); the language select is set
  to the image's language. The tool's own steps run as on the live site: upscaling of narrow images, lighting
  flattening, dark-mode inversion, an orientation retry when confidence < 50, a second inverted pass for dark panels,
  dropping of near-zero-confidence lines, and `preserve_interword_spaces=1`.
- Third-party ad, analytics and consent scripts on the page (gatekeeperconsent, ezoic/ezojs, googletagmanager) were
  blocked with `route.abort()` so the benchmark made no ad/analytics requests and no consent banner covered the tool.
- Native comparison (`score.py`): `/opt/tess554/bin/tesseract <image> stdout --tessdata-dir <tessdata|tessdata_best> -l <lang> --oem 1 --psm 3`
  on the original image file, with no preprocessing and no orientation detection.
- Metrics: CER/WER from `tools/metrics.py`; `word_recall_unordered` (share of ground-truth words found anywhere in the
  output) is reported as well because screenshots and receipts have no single reading order.
- Wall times in `browser_runs.json` are from the shared development container and are **not** publishable.

```sh
(cd <site checkout> && python3 -m http.server 8791 --bind 127.0.0.1) &
SITE=http://127.0.0.1:8791 node bench/ocr-online/run.js
python3 bench/ocr-online/score.py
```

## Results (`results/comparison.csv`, 16 images, one run each)

| image | tool (browser) CER | native 5.5.4 standard CER | native 5.5.4 best CER |
|---|---|---|---|
| receipt (clean, mono) | 0.00% | 0.28% | 0.28% |
| receipt, faded thermal | 1.08% | 1.63% | 0.27% |
| receipt, simulated phone photo | 26.56% | 20.09% | 19.86% |
| book page, 300 DPI | 0.00% | 0.00% | 0.00% |
| book page, 150 DPI | 0.18% | 0.18% | 0.18% |
| simulated phone photo, level 1 | 0.36% | 0.36% | 0.36% |
| simulated phone photo, level 2 | 0.00% | 0.39% | 0.77% |
| page skewed 5 degrees | 0.17% | 0.84% | 0.84% |
| sideways page (90 degrees) | 0.00% | 84.93% | 84.57% |
| upside-down page (180 degrees) | 0.00% | 84.42% | 84.23% |
| two-column page | 0.00% | 0.00% | 0.00% |
| UI screenshot, dark mode | 7.49% | 8.01% | 8.01% |
| UI screenshot (dashboard), light mode | 61.52% | 61.52% | 61.52% |
| Russian page | 0.35% | 0.35% | 0.35% |
| Simplified Chinese page | 5.08% | 88.81% | 72.88% |
| Arabic page | 16.00% | 2.12% | 1.38% |

Screenshots of the tool (raw, uncropped viewport 1280x900): `results/screenshots/` (empty, file selected,
processing, result for a receipt, a book page, a sideways page and a dark-mode screenshot).
Raw outputs: `results/raw/browser/`, `results/raw/native-5.5.4-standard/`, `results/raw/native-5.5.4-best/`.

## Key findings
- On clean pages, the 150 DPI page, the two-column page and the Russian page the browser tool gave exactly the same
  CER as native Tesseract 5.5.4 (0.00%, 0.18%, 0.00%, 0.35%), even though its engine is an older Tesseract snapshot
  (`5.1.0-280-ge20b`) with `best_int` models.
- The tool's orientation retry works: sideways (90 degrees) and upside-down pages came out at 0.00% CER in the browser,
  while plain `tesseract --psm 3` produced 84.9% and 84.4% CER (it does not rotate pages unless OSD is used, e.g. `--psm 1`).
- Chinese: 5.08% CER in the browser vs 88.81% native. Most of the native "error" is spaces: native Tesseract put a
  space between every Chinese character, the tool's `preserve_interword_spaces=1` did not. See bench/languages for the
  same effect measured on all CJK pages.
- Arabic is worse in the browser: 16.00% CER vs 2.12% native. One full line of the preamble is missing from the tool's
  output (the tool drops lines with confidence < 30 when other lines are confident; that is the likely cause, not
  verified line by line) and many words are glued together (e.g. `لحقوقالإنسان`, `فيالعالم`).
  Word recall: 67.4% in the browser vs 95.6% native.
- The light-mode dashboard screenshot: 61.52% CER both in the browser and natively, yet 100% (browser) and 98.2%
  (native) of the words were found. Tesseract read the KPI cards and the table column by column, so the text is
  complete but in a different order from the page's reading order; CER punishes that.
- The simulated phone photo of a receipt was the hardest image: 26.56% CER in the browser, 20.09% native.

## Limits
- 16 images, one run each, all synthetic (see `corpus/manifest.json`); not a ranking of browser vs native in general.
- Results depend on the CDN versions the page pins (tesseract.js 5.1.1, `4.0.0_best_int` models) at the time of the run.
