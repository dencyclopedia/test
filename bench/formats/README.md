# Output formats of the tesseract CLI, with real files and sizes

One synthetic receipt (`corpus/receipt/receipt01_dejavu-mono.png`, 945 x 1222 px, 300 DPI) through every output
format, plus the CLI help texts. Output files only; no timings (development container).

```sh
bash bench/formats/run.sh
```
- Tesseract 5.5.4 (`/opt/tess554/bin/tesseract`), tessdata (standard) `ced78752`, `-l eng --oem 1 --psm 6`, `OMP_THREAD_LIMIT=1`.
- The format names (`hocr`, `pdf`, ...) are config files in `<tessdata>/configs/`; the script builds a tessdata dir with the
  models plus the `configs/` folder of the 5.5.4 install.
- Results: `results/out/` (every file), `results/sizes.csv`, `results/commands.txt` (commands, stderr, exit codes),
  `results/help-extra.txt`, `help-psm.txt`, `help-oem.txt`, `list-langs.txt`, `print-parameters.txt`, `pdf-inspect.txt`.

## Findings
- Sizes: txt 354 B, tsv 3,471 B, box 5,798 B, PAGE XML 9,037 B, hOCR 10,030 B, ALTO 11,121 B, PDF 46,422 B,
  `-c textonly_pdf=1 pdf` 3,701 B (no image inside: `pdfimages -list` lists none).
- `tesseract in out textonly_pdf` prints `read_params_file: Can't open textonly_pdf`, exits 0 and writes only out.txt.
- With `--tessdata-dir` pointing at a bare tessdata checkout (no `configs/`), `... out hocr` prints
  `read_params_file: Can't open hocr`, exits 0 and writes only out.txt.
- `--print-parameters` lists 631 parameters in 5.5.4.
