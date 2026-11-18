# Error catalogue (real messages, captured verbatim)

Every message here was produced by running the command shown; nothing is retyped. `capture.py` runs one
command and stores stdout, stderr and the exit code byte-for-byte (`results/captures/<id>.txt`,
`results/captures/captures.jsonl`). `catalog.py` joins them with a short cause/fix note into
`results/errors.json` (all captures from here, `../train` and `../pdf`; `kind` = error or fix-or-check).

Where it ran: the development container (Ubuntu 24.04.5, Tesseract **5.5.4** built from the upstream tag,
plus Ubuntu's packaged **5.3.4** for the `*-apt-534` entries) — error text is deterministic, no timings here.
Training errors come from the GitHub Actions run of `bench/train` (`../train/results/errors/`), PDF errors from
`bench/pdf` (`../pdf/results/errors/`, captured on Actions).

## Reproduce

```bash
PY=/path/to/venv/bin/python   # pytesseract 0.3.13, pdf2image, pillow, opencv-python-headless
(cd node && npm install)       # node-pdftoppm 2.0.1, node-poppler 11.0.0
bash run_errors.sh results/captures
python3 catalog.py results/errors.json results/captures/captures.jsonl ../train/results/errors/captures.jsonl
```

## Key findings

| Situation | What Tesseract / the wrapper actually prints | Exit code |
|---|---|---|
| pytesseract, no `tesseract` on PATH | `pytesseract.pytesseract.TesseractNotFoundError: tesseract is not installed or it's not in your PATH. See README file for more information.` | 1 |
| `-l fra`, pack missing (5.5.4 and apt 5.3.4 print the same) | `Error opening data file /usr/share/tesseract-ocr/5/tessdata/fra.traineddata` / `Please make sure the TESSDATA_PREFIX environment variable is set to your "tessdata" directory.` / `Failed loading language 'fra'` / `Tesseract couldn't load any languages!` / `Could not initialize tesseract.` | 1 |
| `-l eng+fra`, only fra missing | the same three error lines, **then OCR runs with eng only** | **0** |
| `TESSDATA_PREFIX` = parent of the model dir | `Error opening data file /opt/tessdata/eng.traineddata` … | 1 |
| `TESSDATA_PREFIX` = path that does not exist | `Warning: TESSDATA_PREFIX /nonexistent/tessdata does not exist, ignore it` then falls back to the compiled-in dir | 1 |
| `--tessdata-dir .../eng.traineddata` (a file) | `Error opening data file .../eng.traineddata/eng.traineddata` | 1 |
| `--oem 0` (or `--oem 2`) with tessdata_fast **or tessdata_best** | `Error: Tesseract (legacy) engine requested, but components are not present in .../eng.traineddata!!` | 1 |
| `--oem 0` with tessdata (standard) | works | 0 |
| SVG, or a text file named `.png` | `Error in pixRead: image file not found: <svg xmlns=…` / `Image file <svg …> cannot be read!` — the unreadable file is treated as an **image list** and its first line used as a file name | 1 |
| PDF input | `Error in pixReadStream: Pdf reading is not supported` / `Error in pixRead: pix not read` / `Error during processing.` (5.5.4 and 5.3.4) | 1 |
| PNG without DPI | `Estimating resolution as 400` (warning; `--dpi 300` silences it) | 0 |
| `--psm 14` | `Invalid PSM value, please enter a symbolic PSM value or a number between 0-13` (on **stdout**) | 1 |
| `-psm 7` (3.x syntax) | `Error, unknown command line argument '-psm'` | 1 |
| `tesseract in out pdf` with a model dir that has no `configs/` | `read_params_file: Can't open pdf` — **exit 0, only out.txt is written** | 0 |
| `tesseract in out textonly_pdf` (as on the /pdf/ page) | `read_params_file: Can't open textonly_pdf` — exit 0, only .txt. Correct: `-c textonly_pdf=1 pdf` | 0 |
| pytesseract `timeout=` hit | `RuntimeError: Tesseract process timeout` | 1 |
| OpenCV Otsu on a BGR image (OpenCV 5.1.0) | `cv2.error: OpenCV(5.1.0) … error: (-2:Unspecified error) in function 'double cv::threshold(…)'` / `> THRESH_OTSU mode:` / `>     'src_type == CV_8UC1 \|\| src_type == CV_16UC1'` / `> where` / `>     'src_type' is 64 (CV_8UC3)` | 1 |
| pdf2image without poppler | `pdf2image.exceptions.PDFInfoNotInstalledError: Unable to get page count. Is poppler installed and in PATH?` | 1 |
| Node `node-pdftoppm` 2.0.1 without poppler-utils | `Error: spawn pdftoppm ENOENT` (errno -2, syscall `spawn pdftoppm`) — the callback is then called **a second time** with a result list; a stale `hello-*.ppm` already in the output dir is returned as if new | 0 (error only passed to the callback) |
| Node `node-poppler` 11.0.0 without poppler-utils | `Error: Unable to find linux Poppler binaries, please pass the path to the binaries' directory as an argument to the Poppler constructor.` | 1 |
| Tess4J 5.16.0 (latest) on Ubuntu 24.04 (Leptonica 1.82) | `java.lang.UnsatisfiedLinkError: Error looking up function 'pixAddMultipleBlackWhiteBorders': /lib/x86_64-linux-gnu/liblept.so.5: undefined symbol: pixAddMultipleBlackWhiteBorders` — 5.15.0 fails the same way, **5.14.0 works** | n/r |
| 3×40 px black bar, `--psm 7` | prints an internal statistics dump (`Bottom=0, top=40, base=0, x=0` / `Total count=0` / `Min=0.00 Really=0` …) | 0 |
| tesstrain `FINETUNE_TYPE=2 BATCH_SIZE=4` | `make -n` output **IDENTICAL** to the run without them: the Makefile has neither variable | 0 |
| tesstrain `START_MODEL=eng` not in `TESSDATA` | `Failed to read /tmp/emptytd/eng.traineddata` / `make: *** [Makefile:207: data/eng/errmissing.lstm-unicharset] Error 1` — `make training` does **not** download it | n/r |
| tesstrain from tessdata_fast | `Error, data/eng/errfast.lstm is an integer (fast) model, cannot continue training` | n/r |
| text2image `--font='My Custom Font'` | `Could not find font named 'My Custom Font'.` / `Pango suggested font 'DejaVu Sans'.` / `Please correct --font arg.` | n/r |

n/r = not recorded: the command was piped through `tail`/`grep`, so the captured exit code is the pipeline's (0).

## Not reproduced

- **`Empty page!!`** and **`Image too small to scale!!`**: with a blank 900×300 page, a 2×2 px image, specks,
  a rule line and a tiny crop, neither 5.5.4 nor apt 5.3.4 printed these lines with default settings (they
  silently return empty text). Both strings exist in 5.5.4's source (`src/textord/colfind.cpp:364`,
  `src/lstm/input.cpp:94`), so they can appear, but we could not trigger them with these inputs; they are
  not in the catalogue as captured messages.

## Claims on the live pages this checks

- /python/ error table, `(-215:Assertion failed) src.type() == CV_8UC1`: current OpenCV (5.1.0) prints a
  different message for this mistake: `(-2:Unspecified error) … THRESH_OTSU mode: 'src_type == CV_8UC1 || src_type == CV_16UC1' … 'src_type' is 64 (CV_8UC3)`.
- /python/ `Error opening data file …fra.traineddata` → confirmed verbatim; the full message is five lines (above).
- /pdf/ `tesseract scan.png out textonly_pdf` → does not create a PDF (`read_params_file: Can't open textonly_pdf`, exit 0).
- /train/ `FINETUNE_TYPE`, `BATCH_SIZE` → not tesstrain variables (silently ignored); `make training` does not
  download the start model.
