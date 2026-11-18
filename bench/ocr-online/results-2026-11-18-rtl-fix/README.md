# Re-run after the RTL fix (2026-11-18)

The first run (`../results/`) found the tool far worse than native Tesseract on Arabic (16.00% vs 2.12% CER, one
line missing, words glued). Cause, shown in `ara_lines.json` (tesseract.js 5.1.1, ara 4.0.0_best_int):
- `preserve_interword_spaces=1` (set by the tool for CJK) removes spaces between Arabic words; native 5.5.4 does the same
  (see bench/languages: ara 2.69% -> 4.13%).
- The tool dropped lines with Tesseract line confidence < 30. The missing line scored 27 because its first word scored 27;
  its other 15 words scored 89-93.

Fix in the site's `assets/ocr-tool.js`: the setting is 0 when the document or second language is RTL (ara fas heb urd yid
pus snd uig syr div), and a line is judged by the mean confidence of its words. Same 16 images, same settings:

| image | browser CER before | after | native 5.5.4 standard | native best |
|---|---|---|---|---|
| Arabic page | 16.00% | **1.25%** | 2.12% | 1.38% |
| the other 15 images | unchanged | identical output text | | |

Arabic word recall 67.4% -> 94.1%. Only one Arabic page was tested; Persian, Urdu and Hebrew are not measured.

Files: `run.js`, `score.py` (copies of the parent scripts writing here), `compare.py` -> `before_after.csv`,
`browser_runs.json`, `comparison.csv`, `raw/`, `ara_lines.js/json`, `privacy_network.js/json` (every request during an OCR
run: 4 GETs to cdn.jsdelivr.net, 0 with a body; then offline: second page read with 0 requests).
Wall times are from the shared development container (indicative only).
