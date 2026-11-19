# Checks for tesseractocr.org/about/: release dates and "does Tesseract phone home?"

```sh
sudo bash bench/about/run.sh   # unshare -n needs root
```
1. **Release history**: `results/tags.tsv` = every tag of github.com/tesseract-ocr/tesseract with its date
   (annotated tags: tagger date; lightweight tags: commit date), from a `--filter=tree:0` clone. No API.
2. **Offline OCR** (development container, Tesseract 5.5.4, Ubuntu 24.04.5, strace 6.8):
   - `results/offline-run.txt`: `unshare -n` (no network: loopback only, DNS fails) then OCR of a receipt: exit 0, full text.
   - `results/strace-network.txt`: `strace -f -e trace=network` of a normal run: **empty** (0 network syscalls).
   - `results/strace-files-opened.txt`: the 26 files the run opened (libraries, eng.traineddata, image, output).
   - `results/strace-summary.txt`: syscall counts.

Limits: Linux CLI build only; Windows/macOS builds and wrappers were not traced.
