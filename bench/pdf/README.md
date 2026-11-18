# OCR for scanned PDFs: OCRmyPDF vs the Tesseract CLI vs pdf2image + pytesseract vs pdfsandwich

- **Run:** GitHub Actions `ubuntu-24.04`, Intel Xeon 6975P-C, 4 vCPU — run
  [44258321538](https://github.com/dencyclopedia/test/actions/runs/44258321538) (`results/meta.json`).
  Errors and the time breakdown: `bench-pdf-extra` (see below).
- **Engine:** Tesseract 5.5.4 built from the upstream tag, `eng` from tessdata_fast (pinned commit),
  `OMP_THREAD_LIMIT=1` for every command. OCRmyPDF still OCRs pages in parallel with its default `-j` (all 4 cores).
- **Tools** (`results/tool-versions.txt`): OCRmyPDF 17.14.2 (pikepdf 10.18.2, fpdf2 2.9.0, pypdfium2 5.15.2),
  poppler-utils 24.02.0, Ghostscript 10.02.1, qpdf 11.9.0, pngquant 2.18.0, jbig2enc 0.28 (apt `jbig2`),
  pdfsandwich 0.1.7, unpaper 7.0.0, ImageMagick 6.9.12-98, pdf2image 1.17.0, pytesseract 0.3.13, pypdf 7.1.0.
  None of these were preinstalled on the runner image.
- **Input (synthetic):** `make_pdf.py` renders *Pride and Prejudice* ch. 1–12 (public domain, `text/SOURCES.md`)
  in Liberation Serif 11 pt on 20 A4 pages at 300 DPI, adds seeded scan degradation (±0.6° skew, blur, paper tone,
  noise, specks), saves grayscale JPEG q75 and wraps them with img2pdf into an image-only PDF: **20,565,842 bytes**.
  Ground truth = the rendered lines; ground-truth word boxes are kept for the alignment check.
- **Measures:** wall time = median of 5 runs after 1 warm-up (min/max in the JSON); output size; text-layer
  CER/WER from `pdftotext -layout` against the ground truth (`tools/metrics.py`); text-layer alignment = each
  text-layer word (pdfplumber) matched to its ground-truth word, median distance between box centres in PDF points
  and box IoU (pages 1–3, 1,307 words).

## Methods (20 pages)

| Method | Time (median) | Output | × input | Text-layer CER | WER | Centre error | Page size |
|---|---|---|---|---|---|---|---|
| `ocrmypdf in.pdf out.pdf` (default `-j` = 4) | **22.2 s** | 20.5 MB | 0.995 | 0.135 % | 0.81 % | 2.08 pt | A4 |
| `ocrmypdf -j 1` | 60.0 s | 20.5 MB | 0.995 | 0.135 % | 0.81 % | 2.08 pt | A4 |
| `pdftoppm -png` → `tesseract list.txt out pdf` | 286.5 s | **109.3 MB** | 5.315 | 0.140 % | 0.69 % | 0.71 pt | A4 |
| `pdftoppm -jpeg` → `tesseract list.txt out pdf` | 42.8 s | 19.7 MB | 0.956 | 0.143 % | 0.72 % | 0.70 pt | A4 |
| `-c textonly_pdf=1` text layer + `qpdf --overlay` onto the original | 285.4 s | 20.7 MB | 1.006 | 0.140 % | 0.69 % | 0.70 pt | A4 |
| pdf2image + pytesseract + pypdf (the /pdf/ page's code) | 47.6 s | 25.5 MB | 1.242 | **0.605 %** | 5.04 % | — | **2551.89 × 3608.23 pt** |
| same + `config="--dpi 300"` | 48.7 s | 25.5 MB | 1.241 | 0.140 % | 0.69 % | 0.71 pt | A4 |
| `pdfsandwich -lang eng` | 44.5 s | **1.2 MB** | 0.060 | **0.079 %** | 0.54 % | 0.85 pt | A4 |

(`results/methods.json`; text extracted per method in `results/raw/`; page 1 with the hidden text layer drawn in
red over the page and ground-truth boxes in green: `results/overlay/<method>-page01-text-layer.png`.)

Findings:

- **The /pdf/ page's Python code (Method D) produces 35 × 50-inch pages.** `pdf2image` returns PIL images with no
  DPI, pytesseract hands them to Tesseract, which assumes 70 DPI for the PDF page size (2481 px × 72/70 =
  2551.89 pt). The same missing DPI also made recognition worse (CER 0.605 % vs 0.140 %). One argument fixes both:
  `image_to_pdf_or_hocr(page, extension="pdf", config="--dpi 300")`.
- **OCRmyPDF was the fastest** (22.2 s for 20 pages, using all 4 cores); with `-j 1` it took 60.0 s. It kept the
  original JPEGs (output 0.995 × input).
- **Feeding Tesseract PNGs made the PDF 5.3× bigger** (109 MB): Tesseract embeds the PNG pages losslessly.
  Rasterising to JPEG instead gave 0.956 × input. (Why the PNG paths also took ~286 s instead of ~43 s is
  measured separately in `results/breakdown.json`, see below.)
- **pdfsandwich made the smallest file (1.2 MB, 6 % of the input) because it replaces the page images**: its
  verbose log shows `convert … -type Bilevel` and the output images are CCITT bi-level — the grey scan is gone.
  Its CER was the lowest (0.079 %), helped by unpaper's cleaning. It ran the 5.5.4 `tesseract` found on PATH.
- **Text-layer alignment:** every method except Method D placed words within ~0.7–2.1 pt (0.25–0.74 mm) of the
  ground-truth centres. OCRmyPDF's renderer uses line-height boxes, so its IoU is lower (0.57 median vs 0.74) while
  positions are still right; see the overlay PNGs.
- `--optimize` levels (`results/optimize.json`, single 20-page file, median of 5):

  | `ocrmypdf --optimize` | Output | × input | Time |
  |---|---|---|---|
  | 0 | 20.7 MB | 1.006 | 21.8 s |
  | 1 (default) | 20.5 MB | 0.995 | 22.2 s |
  | 2 | 19.6 MB | 0.951 | 22.5 s |
  | 3 | **7.8 MB** | **0.381** | 22.1 s |

  With pngquant and jbig2 installed, `-O 2` saved 4.9 % and `-O 3` 61.9 % on this grey JPEG scan; CER unchanged
  (0.135 %) at every level. What happens without pngquant/jbig2: `results/errors/ocrmypdf-no-gs-optimize*.txt`.

## DPI

Re-rasterising the 300-DPI scan with `pdftoppm -r N` (first 5 pages, `results/dpi_rasterize.json`):

| `-r` | OCR+PDF time per page | CER | Output PDF (5 pages) |
|---|---|---|---|
| 150 | 1.16 s | 0.092 % | 8.8 MB |
| 200 | 1.41 s | 0.156 % | 15.0 MB |
| 300 | 1.99 s | 0.156 % | 26.9 MB |
| 400 | 2.72 s | 0.191 % | 40.5 MB |
| 600 | 4.63 s | 0.219 % | 66.4 MB |

Up-sampling a 300-DPI scan to 400/600 bought nothing but time and size.

Pages *scanned* natively at each resolution (4 pages, 11 pt body text and 7 pt small print, `results/dpi_native.json`):

| Scan DPI | CER 11 pt | CER 7 pt | s/page 11 pt | s/page 7 pt |
|---|---|---|---|---|
| 150 | 0.236 % | **1.179 %** | 0.84 | 1.57 |
| 200 | 0.148 % | 0.148 % | 0.95 | 1.91 |
| 300 | **0.128 %** | 0.136 % | 1.28 | 2.46 |
| 400 | 0.256 % | 0.163 % | 1.73 | 3.00 |
| 600 | 0.591 % | 0.241 % | 2.90 | 4.32 |

- 150 DPI hurt small print (7 pt: 1.18 % CER) but barely hurt 11 pt text. 300 DPI was best for both.
- **600 DPI was worse than 300 DPI** for both sizes here (11 pt: 0.591 % vs 0.128 %) and 2.3× slower — the page's
  “600 DPI for small fonts” is not supported by this test (Tesseract's LSTM works best around 20–30 px x-height;
  11 pt at 600 DPI is ~42 px).

## Errors (verbatim)

See `results/errors/` (captured on Actions by `capture_errors.sh`) and `../errors/README.md`.
- `tesseract file.pdf out` (5.5.4 and apt 5.3.4): `Error in pixReadStream: Pdf reading is not supported` /
  `Error in pixRead: pix not read` / `Error during processing.`
- `tesseract scan.png out textonly_pdf` (as on the page): `read_params_file: Can't open textonly_pdf`, exit code 0,
  only `out.txt` is written. The working form is `tesseract scan.png out -c textonly_pdf=1 pdf`.
- OCRmyPDF on its own output: `PriorOcrFoundError: page 1 already has text! - aborting (use --force-ocr or --mode force to force OCR; see also help for --skip-text, --redo-ocr, and --mode)` (exit 6).
- Encrypted input: `EncryptedPdfError: Input PDF is encrypted. The encryption must be removed to perform OCR.` (exit 8);
  pdftoppm: `Command Line Error: Incorrect password`; fix `qpdf --password=… --decrypt`.
- pdf2image without poppler: `pdf2image.exceptions.PDFInfoNotInstalledError: Unable to get page count. Is poppler installed and in PATH?`
- `spawn pdftoppm ENOENT` comes from the npm package **node-pdftoppm** (2.0.1), which spawns `pdftoppm` from PATH;
  reproduced in `../errors/`.
- **OCRmyPDF 17.14.2 needs neither Ghostscript nor poppler**: with a PATH holding only `tesseract` and the venv,
  `ocrmypdf in.pdf out.pdf` succeeded and wrote PDF/A-2b (`Speculative PDF/A conversion succeeded - skipping Ghostscript`).

## Claims on the live /pdf/ page

| Claim | Result |
|---|---|
| `tesseract scan.png out textonly_pdf` | **Wrong**: no PDF; use `-c textonly_pdf=1 pdf` |
| OCRmyPDF “requires Ghostscript and the poppler tools” | **Out of date** for OCRmyPDF 17: runs with neither (Ghostscript optional for PDF/A fallback) |
| Method D Python code | **Produces wrongly sized pages** (70-DPI assumption); add `--dpi 300` |
| 300 DPI is the standard balance | Confirmed (best CER here) |
| 600 DPI for small fonts | **Not supported**: 7 pt at 600 DPI 0.241 % vs 0.136 % at 300 DPI |
| below 200 DPI accuracy drops sharply | For 7 pt yes (1.18 % at 150 DPI); for 11 pt only slightly (0.24 %) |
| `--optimize` shrinks the file | Confirmed for `-O 3` (−62 %); `-O 1`/`-O 2` −0.5 %/−4.9 % on this scan |
