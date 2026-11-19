# Online OCR tool timing (GitHub Actions)

How long the site's in-browser OCR tool (tesseract.js) takes on the 16 corpus images from `bench/ocr-online`, measured on a
standard GitHub Actions `ubuntu-24.04` runner. Development-container timings are not published; see `LAB.md`.

- `site-snapshot/`: the tool page (`ocr-online/index.html`), `assets/ocr-tool.js` and the design assets. `SITE_COMMIT`
  records the site commit they were copied from.
- `timing.js`: for each image, one cold run the first time a language is used (this includes downloading the
  tesseract.js core and the language model from cdn.jsdelivr.net), one warm-up, then 5 timed runs. Every run reloads the page.
  Time is measured from clicking "Extract text" until the result is shown.
- Workflow: `.github/workflows/bench-ocr-online-timing.yml`. It serves the snapshot, runs `timing.js` and commits
  `results/timing.csv`, `results/meta.json` (CPU, cores, run id) and `results/log.txt`.

Reported: median of the 5 warm runs (seconds), plus min, max and the cold first-use time.
