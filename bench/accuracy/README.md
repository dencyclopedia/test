# Accuracy by DPI, font and degradation; Tesseract 5.3.4 vs 5.5.4

How resolution, font and common scan/photo problems change Tesseract's error rate, and whether upgrading from
Ubuntu 24.04's packaged 5.3.4 to 5.5.4 changes the text you get.

## Method
- Images: `corpus/` sets `clean` (189) and `degraded` (80); all synthetic, see `corpus/README.md`.
  - clean: 3 Project Gutenberg passages (Austen, Doyle, Carroll; ~1,100-1,300 characters each) rendered in
    12 pt in 6 fonts (DejaVu Serif, Caladea, Carlito, Inter, DejaVu Sans Mono, Courier 10 Pitch) and in 8 pt in
    3 fonts (DejaVu Serif, Carlito, DejaVu Sans Mono), each at 70, 100, 150, 200, 300, 400 and 600 DPI.
  - degraded: 4 half pages at 300 DPI (one font each), 19 single degradations + the undegraded original.
- Runs (all `--oem 1 --psm 3 -l eng`, `OMP_THREAD_LIMIT=1`):
  - `554-standard`: Tesseract 5.5.4 (built from the upstream tag), tessdata (standard) `ced78752`
  - `534-standard`: Ubuntu 24.04's `tesseract-ocr` 5.3.4-1build5, **same model files**
  - `534-apt`: 5.3.4 with Ubuntu's own `tesseract-ocr-eng` 1:4.1.0-2 model ("what apt gives you")
- CER/WER from `tools/metrics.py`. Tables show the mean of per-image CER.
- Timing (seconds per page) comes only from GitHub Actions (`timing.py`, workflow `bench-accuracy-timing`), never from
  the development container.

```sh
python3 bench/accuracy/run.py                     # accuracy, any machine
python3 bench/accuracy/timing.py <outdir> 5        # timing, run by .github/workflows/bench-accuracy-timing.yml
```
Outputs: `results/per_image.csv`, `results/summary_*.csv`, `results/version_identical_output.csv`,
`results/raw/<run>/<image id>.txt` (every OCR output), `results/meta.json`;
timing: `results/timing/timing-dpi.csv`, `results/timing/timing-models.csv`, `results/timing/meta.json`.

## Results: DPI (Tesseract 5.5.4, tessdata standard, mean CER)

| DPI | 12 pt (18 pages) | 8 pt (9 pages) |
|---|---|---|
| 70 | 1.53% | 56.51% |
| 100 | 0.19% | 3.87% |
| 150 | 0.09% | 0.11% |
| 200 | 0.08% | 0.05% |
| 300 | 0.07% | 0.03% |
| 400 | 0.07% | 0.04% |
| 600 | 0.14% | 0.04% |

## Results: degradations (Tesseract 5.5.4, tessdata standard, 4 pages per level, mean CER)

| level | CER | level | CER |
|---|---|---|---|
| none | 0.17% | skew 1 deg | 0.17% |
| blur sigma 1 / 2 / 3 px | 0.13% / 0.09% / 0.09% | skew 3 deg | 0.51% |
| noise sigma 15 / 30 | 0.17% / 0.17% | skew 5 deg | 19.89% |
| noise sigma 50 | 5.14% | lighting gradient 50% | 0.17% |
| JPEG q90 / 70 / 50 / 30 | 0.17% each | lighting gradient 75% | 23.71% |
| low contrast (ink 100 / 150, paper 190) | 0.17% / 0.17% | phone photo level 1 / 2 | 0.09% / 0.82% |

## Results: timing on GitHub Actions (run 44258805184)
Runner: `ubuntu-24.04` (image 20261111.127.1), Intel Xeon 6975P-C, 4 cores. Median of 5 runs after 1 warm-up, whole CLI
call (start + model load + OCR), `OMP_THREAD_LIMIT=1`. Mean of the per-page medians:

| DPI | 70 | 100 | 150 | 200 | 300 | 400 | 600 |
|---|---|---|---|---|---|---|---|
| s/page (3 pages, DejaVu Serif 12 pt, standard) | 0.47 | 0.55 | 0.78 | 0.84 | 0.98 | 1.15 | 1.59 |

| model (300 DPI, 9 pages) | fast | standard | best |
|---|---|---|---|
| s/page | 0.74 | 0.99 | 2.13 |

## Key findings
- Below 150 DPI accuracy collapses for small text: 8 pt text had 56.51% CER at 70 DPI and 3.87% at 100 DPI, but 0.11%
  at 150 DPI and 0.03% at 300 DPI (Tesseract 5.5.4, tessdata standard, 9 pages per DPI). 12 pt text held up better:
  1.53% at 70 DPI, 0.19% at 100 DPI, 0.07% at 300 DPI (18 pages per DPI).
- More DPI is not always better: 12 pt pages at 600 DPI had 0.14% CER, twice the 0.07% at 300 and 400 DPI.
- At 70 DPI the 8 pt sans-serif pages (Carlito) were nearly unreadable: 83.4% CER, against 49.4% for DejaVu Serif and
  36.7% for DejaVu Sans Mono.
- Sans-serif fonts were the only clean 12 pt pages at 150-400 DPI that kept errors (0.19-0.25% CER vs 0.00% for the
  serif and monospace pages at 200-400 DPI). The main error: capital `I` read as `|` (e.g. "and I have" -> "and | have").
- Curly quotes are a recurring error: `”` came out as `"` in several pages; LAB rules count that as an error.
- Blur (sigma up to 3 px at 300 DPI), JPEG down to quality 30, Gaussian noise up to sigma 30 and low contrast did not
  change the CER of these pages (0.09-0.17% vs 0.17% for the originals).
- Heavy noise (sigma 50) raised CER to 5.14%; a 5 degree skew to 19.89% (one page, Carlito, 76.2%: Tesseract's layout
  analysis cut the lines into fragments; the other three pages stayed at 0.8-1.7%); a 3 degree skew cost only 0.51%.
- A strong lighting gradient (75% darker in the bottom-right corner) was the worst single degradation: 23.71% CER.
  Tesseract dropped the ends of lines in the dark corner. A 50% gradient did no harm (0.17%).
- The simulated phone photos (perspective, vignette, blur, noise, JPEG) were read well: 0.09% (level 1) and 0.82% (level 2).
- Upgrading 5.3.4 -> 5.5.4 with the same tessdata (standard) model changed the output text of 65 of 269 images, but not
  the error rate in a meaningful way: mean CER 3.09% vs 3.09% on the clean set and 2.62% vs 2.62% on the degraded set.
- The apt combination (5.3.4 + Ubuntu's 4.1.0 eng model) had a mean CER of 2.06% on the clean set vs 3.09% for 5.5.4 +
  tessdata standard, driven by the 70 DPI / 8 pt pages (36.8% vs 56.5%); from 150 DPI up all three runs were within
  0.12 percentage points of each other.
- Speed (Actions, ubuntu-24.04): 0.98 s per 300 DPI page with the standard model; 1.59 s at 600 DPI; tessdata_best took
  2.13 s per page vs 0.74 s for tessdata_fast, with no English accuracy gain on these pages (see bench/models).

## Limits
- Rendered pages are idealised; real scans add paper texture, bleed-through and mixed degradations.
- 3 passages per DPI cell; the CER differences between 0.0x% values are a handful of characters.
