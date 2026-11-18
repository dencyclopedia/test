# Python OCR throughput: per call vs multiprocessing vs tesserocr vs one multi-page call

- **Run:** GitHub Actions `ubuntu-24.04`, AMD EPYC 7763, 4 vCPU — run
  [44311512745](https://github.com/dencyclopedia/test/actions/runs/44311512745) (`results/meta.json`, `results/throughput.json`).
- Tesseract 5.5.4 (built from tag), `eng` tessdata_fast, pytesseract 0.3.13, tesserocr 2.13.0 (PyPI wheel).
- **Input (synthetic):** the 10 images of `bench/bindings/make_images.py` (2481×1170 px, 300 DPI) repeated 3× = **30 images**
  per run. Median of 5 runs after 1 warm-up; min/max in the JSON. Pool start-up is inside the timing.
- `python3 run_throughput.py IMGDIR results/throughput.json --runs 5` (`OMP_THREAD_LIMIT=1` unless the row says unset;
  every strategy gets a 600 s budget).

## Results

| Strategy (30 images) | images/s | median s | CER (first 10) |
|---|---|---|---|
| pytesseract per call (loop) | 1.255 | 23.9 | 1.069 % |
| pytesseract + `multiprocessing.Pool(1)` | 1.255 | 23.9 | 1.069 % |
| pytesseract + `Pool(2)` | 2.362 | 12.7 | 1.069 % |
| pytesseract + `Pool(4)` | 3.338 | 9.0 | 1.069 % |
| tesserocr, one `PyTessBaseAPI` reused | 2.411 | 12.4 | 0.861 % |
| **tesserocr, `Pool(4)`, one API per worker** | **6.039** | 5.0 | 0.861 % |
| pytesseract on one multi-page TIFF (one call) | 2.167 | 13.8 | 0.861 % |
| tesseract CLI on one multi-page TIFF | 2.165 | 13.9 | 0.861 % |
| tesseract CLI on an image list | 2.088 | 14.4 | 0.861 % |
| pytesseract per call, `OMP_THREAD_LIMIT` unset | 1.235 | 24.3 | 1.069 % |
| pytesseract + `Pool(4)`, `OMP_THREAD_LIMIT` unset | **did not finish** | stopped at the 600 s budget, no timed run completed | – |

## Key findings

- A per-call pytesseract loop managed **1.26 images/s**; reusing one tesserocr API **2.41** (1.9×); a Pool(4) of
  pytesseract **3.34** (2.7×); **tesserocr with one API per worker in a Pool(4): 6.04 images/s (4.8×)**.
- One multi-page TIFF in a single call (2.17/s) beat the per-call loop by 1.7× — the saving is the per-call process
  start and model load (~100 ms per call, see `../bindings`).
- **Pool(4) with `OMP_THREAD_LIMIT` unset did not finish 30 images in 600 s**, while the same pool with
  `OMP_THREAD_LIMIT=1` did 30 images in 9.0 s: four tesseract processes each starting one OpenMP thread per core
  oversubscribe the 4 vCPUs badly. A single sequential process was unaffected (1.235 vs 1.255 img/s).
- pytesseract's per-call path (PIL image → temporary file) loses the 300-DPI tag, which changed the text on 2 of 10
  images (CER 1.069 % vs 0.861 %); passing the TIFF path directly did not.
- Forking a `multiprocessing` pool *after* the parent process had used tesserocr hung the first Actions run
  (fork after OpenMP initialisation); the tesserocr pool uses the `spawn` start method.

## Claims on the live /python/ page

| Claim | Result |
|---|---|
| pytesseract spawns a process per call — slow in loops | **Confirmed**: 1.26 img/s; ~100 ms overhead per call |
| Batch into a multi-page TIFF: one process for many pages | **Confirmed**: 2.17 img/s (1.7×) |
| multiprocessing uses all cores | **Confirmed** with `OMP_THREAD_LIMIT=1` (3.34 img/s with 4 workers); **without it, Pool(4) did not finish** |
| tesserocr for high-volume in-process | **Confirmed**: 2.41 img/s single process, 6.04 img/s with Pool(4) |
