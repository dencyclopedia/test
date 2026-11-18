"""Build errors.json: each real error (captured verbatim by run_errors.sh / bench/pdf / bench/train / bench/bindings)
with the command, cause and the capture of the fix that worked.
usage: python3 catalog.py OUT.json CAPTURES.jsonl [MORE.jsonl ...]
Only the cause/fix wording below is hand-written; messages and exit codes come from the capture files."""
import json, sys

# id -> (title, cause, fix capture id or None, fix text)
META = {
    "pytesseract-not-found": ("pytesseract.TesseractNotFoundError", "the tesseract binary is not on PATH (pytesseract only wraps the CLI)", "pytesseract-not-found-fix", "install the engine, or set pytesseract.pytesseract.tesseract_cmd to its full path"),
    "lang-missing-554": ("Failed loading language 'xyz' / Error opening data file", "no <lang>.traineddata in the tessdata directory (5.5.4)", "lang-missing-fix-tessdata-dir", "install the language pack or point --tessdata-dir / TESSDATA_PREFIX at a directory that has it"),
    "lang-missing-fra-onlyeng": ("Error opening data file .../fra.traineddata", "TESSDATA_PREFIX directory holds only eng", "lang-missing-fix-tessdata-dir", "add fra.traineddata or use a tessdata directory that has it"),
    "lang-missing-apt-534": ("Error opening data file /usr/share/tesseract-ocr/5/tessdata/fra.traineddata (apt 5.3.4)", "Ubuntu's tesseract-ocr installs only eng + osd", None, "sudo apt install tesseract-ocr-fra"),
    "lang-plus-one-missing": ("-l eng+fra with fra missing: error printed, exit code 0", "Tesseract loads the languages it can and carries on", None, "check stderr, not only the exit code; install the missing pack"),
    "pytesseract-lang-missing": ("pytesseract.TesseractError: (1, 'Error opening data file ...')", "same missing traineddata, surfaced as a Python exception", None, "as above"),
    "tessdata-prefix-parent": ("Please make sure the TESSDATA_PREFIX environment variable is set to your \"tessdata\" directory.", "TESSDATA_PREFIX points at the parent of the directory holding *.traineddata", "tessdata-prefix-fix", "TESSDATA_PREFIX must be the directory that directly contains eng.traineddata"),
    "tessdata-prefix-nonexistent": ("Warning: TESSDATA_PREFIX ... does not exist, ignore it", "typo / wrong path; 5.5.4 falls back to its compiled-in default", "tessdata-prefix-fix", "fix the path"),
    "tessdata-dir-trailing-file": ("Error opening data file .../eng.traineddata/eng.traineddata", "--tessdata-dir was given the .traineddata file instead of its directory", "tessdata-prefix-fix", "pass the directory"),
    "format-svg": ("Image file <svg ...> cannot be read!", "Leptonica cannot read SVG; Tesseract then treats the file as an image LIST and tries to open its first line as a file name", None, "rasterise first (e.g. cairosvg / rsvg-convert to PNG)"),
    "format-text-as-png": ("Image file <first line of the file> cannot be read!", "not an image (wrong extension / truncated download); read as an image list", None, "check the file with `file`; re-download / convert"),
    "format-missing-file": ("Error in fopenReadStream: file not found", "path does not exist", None, "fix the path"),
    "format-webp": ("(no error) WebP is read", "Leptonica built with libwebp", None, "-"),
    "format-bmp": ("(no error) BMP is read", "", None, "-"),
    "pytesseract-svg": ("PIL.UnidentifiedImageError: cannot identify image file", "Pillow cannot open SVG either", None, "rasterise first"),
    "estimating-resolution": ("Estimating resolution as N", "the image has no DPI metadata; Tesseract estimates it from text size (a warning, not an error)", "estimating-resolution-fix-dpi", "--dpi 300 (or save the image with DPI metadata)"),
    "empty-page": ("Empty page!!", "no text found (blank image, or text too faint/small)", None, "check the image; preprocess; try another --psm"),
    "empty-page-psm7": ("blank image with --psm 7", "", None, "-"),
    "too-small-to-scale": ("Image too small to scale!! / Line cannot be recognized!!", "the image (2x2 px) is smaller than the network input", None, "upscale; text should be ~20-30 px x-height"),
    "vbar-psm7": ("Bottom=0, top=40, base=0, x=0 / Total count=0 / Min=0.00 Really=0 ... (statistics dump)", "a 3x40 px solid bar with --psm 7: Tesseract 5.5.4 prints an internal statistics dump to stderr instead of a message", None, "crop real text; ignore the dump"),
    "too-small-crop": ("tiny crop of one word", "", "too-small-crop-fix-upscale", "upscale 4x with Lanczos"),
    "oem0-tessdata-fast": ("--oem 0 with tessdata_fast", "tessdata_fast models are LSTM-only: no legacy engine data", "oem0-tessdata-standard", "use --oem 1/3, or the tessdata (standard) models which still include legacy data"),
    "oem0-tessdata-best": ("--oem 0 with tessdata_best", "tessdata_best models are LSTM-only too", "oem0-tessdata-standard", "as above"),
    "oem2-tessdata-fast": ("--oem 2 with tessdata_fast", "OEM 2 (legacy + LSTM) needs legacy data", None, "use --oem 1/3"),
    "psm-invalid": ("--psm 14", "valid PSM values are 0-13", None, "use 0-13"),
    "psm-old-syntax": ("-psm 7 (single dash)", "Tesseract 3.x syntax; 4.0+ needs --psm", None, "--psm 7"),
    "pdf-config-missing": ("read_params_file: Can't open pdf (exit code 0, only .txt written)", "the tessdata dir has no configs/ (a bare tessdata_fast checkout used via --tessdata-dir)", None, "copy/symlink configs/ (and pdf.ttf) from the installed share/tessdata into that dir, or use -c tessedit_create_pdf=1"),
    "textonly-pdf-as-config": ("read_params_file: Can't open textonly_pdf (exit code 0, only .txt written)", "textonly_pdf is a parameter, not a config file", "textonly-pdf-as-parameter", "tesseract in out -c textonly_pdf=1 pdf"),
    "pytesseract-timeout": ("RuntimeError: Tesseract process timeout", "timeout= elapsed; pytesseract kills the tesseract process", None, "raise timeout / shrink the image"),
    "opencv-threshold-colour": ("cv2.error ... (-215:Assertion failed) ... in function 'threshold'", "Otsu thresholding needs an 8-bit single-channel image; cv2.imread gives BGR", "opencv-threshold-colour-fix", "cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) first"),
    "tesseract-pdf-input": ("Error in pixReadStream: Pdf reading is not supported", "Leptonica/Tesseract cannot read PDF", None, "rasterise (pdftoppm) or use OCRmyPDF"),
    "pdf2image-no-poppler": ("pdf2image.exceptions.PDFInfoNotInstalledError: Unable to get page count. Is poppler installed and in PATH?", "pdfinfo/pdftoppm (poppler-utils) missing", None, "apt install poppler-utils (Windows: poppler_path=)"),
    "node-pdftoppm-enoent": ("Error: spawn pdftoppm ENOENT (unhandled 'error' event, Node process crashes)", "node-pdftoppm spawns `pdftoppm` from PATH and has no 'error' handler", "node-pdftoppm-fix", "install poppler-utils"),
    "node-poppler-missing": ("node-poppler: Unable to find linux Poppler binaries", "node-poppler looks for poppler-utils with `which`", None, "install poppler-utils or pass binPath to new Poppler()"),
    "node-pdftoppm-fix": ("node-pdftoppm with poppler-utils on PATH", "", None, "-"),
    "tess4j-5.16-leptonica-1.82": ("java.lang.UnsatisfiedLinkError: Error looking up function 'pixAddMultipleBlackWhiteBorders'", "Tess4J 5.15.0+ (lept4j 1.21.x) calls Leptonica >= 1.83 functions; Ubuntu 24.04 ships Leptonica 1.82", "tess4j-5.14-fix", "use Tess4J 5.14.0 with Ubuntu 24.04's libraries, or install a newer Leptonica"),
    # bench/pdf captures
    "tesseract-reads-pdf-554": ("Error in pixReadStream: Pdf reading is not supported", "Tesseract 5.5.4 cannot read PDF", None, "rasterise (pdftoppm) or OCRmyPDF"),
    "tesseract-reads-pdf-apt": ("Error in pixReadStream: Pdf reading is not supported (apt 5.3.4)", "same", None, "same"),
    "ocrmypdf-prior-ocr": ("PriorOcrFoundError: page 1 already has text!", "input already has a text layer", "ocrmypdf-prior-ocr-fix-skip-text", "--skip-text, --redo-ocr or --force-ocr"),
    "ocrmypdf-encrypted": ("EncryptedPdfError: Input PDF is encrypted.", "password-protected input", "encrypted-fix-qpdf-decrypt", "qpdf --password=... --decrypt in.pdf out.pdf"),
    "pdftoppm-encrypted": ("Command Line Error: Incorrect password", "encrypted PDF without -upw", "pdftoppm-encrypted-fix", "pdftoppm -upw <password>"),
    "pdf2image-encrypted": ("pdf2image.exceptions.PDFPageCountError: Unable to get page count. Command Line Error: Incorrect password", "encrypted PDF", None, "convert_from_path(..., userpw='...')"),
    "ocrmypdf-no-tesseract": ("OCRmyPDF without tesseract on PATH", "", None, "install tesseract"),
    "ocrmypdf-no-gs-no-poppler": ("OCRmyPDF 17 with no Ghostscript and no poppler on PATH", "neither is required any more", None, "-"),
    # bench/train captures
    "make-dry-run-finetune-batch": ("FINETUNE_TYPE=2 BATCH_SIZE=4: make -n output IDENTICAL to a run without them", "tesstrain's Makefile has no FINETUNE_TYPE or BATCH_SIZE variable; make silently accepts unknown variables", None, "remove them; use START_MODEL / LEARNING_RATE / MAX_ITERATIONS / EPOCHS / NET_SPEC"),
    "text2image-wrong-font": ("Could not find font named 'My Custom Font'. Pango suggested font 'DejaVu Sans'. Please correct --font arg.", "--font must be the Pango name of an installed font", "text2image-list-fonts", "text2image --list_available_fonts --fonts_dir DIR, then use the exact name (e.g. 'OCRA Medium')"),
    "lang-not-installed": ("Failed loading language 'ocra100'", "the trained model is not in the tessdata dir in use", "lang-installed-tessdata-dir", "copy it there or pass --tessdata-dir"),
    "start-model-missing": ("make training with START_MODEL not in TESSDATA", "tesstrain does not download the start model for `make training`", None, "put eng.traineddata (tessdata_best) in TESSDATA"),
    "start-model-fast": ("fine-tuning from tessdata_fast", "integer (fast) models cannot be trained", None, "use tessdata_best"),
    "ground-truth-missing": ("found no data/<MODEL>-ground-truth/*.gt.txt", "MODEL_NAME does not match the ground-truth folder name", None, "data/<MODEL_NAME>-ground-truth/"),
}


def main():
    out, *files = sys.argv[1:]
    caps = {}
    for f in files:
        for line in open(f):
            r = json.loads(line); r["source_file"] = f; caps[r["id"]] = r
    fix_ids = {m[2] for m in META.values() if m[2]}
    rows = []
    for cid, r in caps.items():
        title, cause, fix_id, fix = META.get(cid, (cid, "", None, ""))
        fx = caps.get(fix_id) if fix_id else None
        kind = "fix-or-check" if (cid in fix_ids or not META.get(cid, ("", ""))[1]) else "error"
        rows.append({"id": cid, "kind": kind, "title": title, "command": r["command"], "env_changed": r["env_changed"],
                     "exit_code": r["exit_code"], "stderr": r["stderr"], "stdout": r["stdout"][-1500:],
                     "cause": cause, "fix": fix,
                     "fix_capture": ({"id": fix_id, "command": fx["command"], "exit_code": fx["exit_code"],
                                      "stdout": fx["stdout"][-800:], "stderr": fx["stderr"][-800:]} if fx else None),
                     "captured_utc": r["captured_utc"], "source": r["source_file"]})
    json.dump(rows, open(out, "w"), indent=2, ensure_ascii=False)
    print(len(rows), "entries")


if __name__ == "__main__":
    main()
