# Per-language accuracy: 14 languages x tessdata_fast / tessdata / tessdata_best

## Method
- Images: corpus `multilingual` set, 2 pages per language from the Universal Declaration of Human Rights (UDHR, public
  domain, see `corpus/SOURCES.md`), 12 pt at 300 DPI, synthetic. Fonts that cover each script: DejaVu Serif (eng deu fra
  spa por ita rus vie uzb), Noto Sans SC (chi_sim), IPAGothic (jpn), Noto Sans KR (kor), Noto Naskh Arabic (ara),
  Noto Sans Devanagari (hin). About 650 characters per page (about 290-400 for Chinese/Japanese/Korean).
- Engine: Tesseract 5.5.4, `--oem 1 --psm 3 -l <lang>`, `OMP_THREAD_LIMIT=1`, models pinned as in `results/meta.json`.
- Four runs: fast, standard, best, and standard with `-c preserve_interword_spaces=1` (the setting the site's
  online tool uses).
- Metrics: CER/WER (`tools/metrics.py`); plus `cer_nospace` = CER after deleting all whitespace from both texts,
  because Tesseract often inserts spaces between CJK characters (plain CER counts each as an error). WER is not
  meaningful for Chinese/Japanese (no spaces in the ground truth).

```sh
python3 bench/languages/run.py
```
Outputs: `results/summary.csv`, `results/per_image.csv`, `results/raw/<run>/multilingual/*.txt`.

## Results (mean CER of 2 pages; in brackets: CER with whitespace removed)

| lang | fast | standard | best | standard + preserve_interword_spaces=1 |
|---|---|---|---|---|
| eng | 0.00% | 0.00% | 0.00% | 0.00% |
| deu | 0.00% | 0.00% | 0.00% | 0.00% |
| ita | 0.00% | 0.00% | 0.00% | 0.00% |
| por | 0.00% | 0.00% | 0.00% | 0.00% |
| spa | 0.07% | 0.07% | 0.07% | 0.07% |
| vie | 0.07% | 0.00% | 0.00% | 0.00% |
| rus | 0.18% | 0.18% | 0.18% | 0.18% |
| fra | 0.36% | 0.39% | 0.27% | 0.39% |
| hin | 0.66% | 0.65% | 0.65% | 0.65% |
| uzb | 0.80% | 0.80% | 0.86% | 0.80% |
| ara | 2.57% (2.75%) | 2.69% (2.90%) | 1.98% (1.49%) | 4.13% (2.90%) |
| chi_sim | 3.69% (3.31%) | 91.82% (1.93%) | 72.65% (3.46%) | 2.18% (1.93%) |
| jpn | 13.04% (11.99%) | 93.23% (1.50%) | 71.97% (1.41%) | 1.70% (1.50%) |
| kor | 13.04% (12.38%) | 53.01% (26.80%) | 13.11% (12.02%) | 25.65% (26.80%) |

## Key findings
- Latin-script and Cyrillic pages were near perfect with every model: German, Italian, Portuguese and English 0.00% CER,
  Spanish 0.07%, Russian 0.18%, French 0.27-0.39% (Tesseract 5.5.4, 2 UDHR pages each).
- Chinese and Japanese with tessdata (standard): 91.82% and 93.23% CER, but only 1.93% and 1.50% once whitespace is
  ignored. The standard (and best) models put a space between almost every character. Adding
  `-c preserve_interword_spaces=1` removed those spaces: 2.18% (chi_sim) and 1.70% (jpn) CER. tessdata_fast did not
  insert the spaces (3.69% chi_sim) but read Japanese worse (11.99% CER even without whitespace).
- Korean was the weakest language: 13.04% CER with fast, 13.11% with best and 53.01% with standard. Standard added
  garbage lines (e.g. `하 스`, `르 Ｌ`, `ㅜ`) and split many words into single syllables; even ignoring whitespace it had
  26.80% CER. tessdata_fast or tessdata_best is the better choice for Korean here.
- Arabic: 1.98% CER with tessdata_best vs 2.57% fast and 2.69% standard. `preserve_interword_spaces=1` made Arabic
  worse (4.13% vs 2.69%).
- Uzbek (Latin): all 0.80% of errors were the modifier letters `ʼ` (U+02BC) and `ʻ` (U+02BB) read as an ASCII
  apostrophe `'` (12 of 12 differences with tessdata standard), i.e. o‘zbek-style spellings lose their proper letter.
- Hindi 0.65-0.66% and Vietnamese 0.00-0.07%: diacritics-heavy scripts were read well at 300 DPI in a clean font.

## Limits
Two clean pages per language, one font each; real documents in these scripts (mixed fonts, vertical Japanese,
handwriting) will do worse. The UDHR texts are well known and may resemble training data.
