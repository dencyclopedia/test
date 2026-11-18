# Linux install captures

**What ran:** a GitHub Actions `ubuntu-24.04` runner (Intel Xeon Platinum 8370C, 4 cores; runner image `ubuntu24 20261111.370.1`, Docker 28.0.4), run
[44255392087](https://github.com/dencyclopedia/test/actions/runs/44255392087), 2026-11-18. Each distribution was installed in a **fresh official Docker container**
(`docker run --rm`), as root, so there is no `sudo` in the transcripts. A container is not a full desktop install: base images are minimal, so the dependency list
is longer than on a typical desktop, and times include downloads from the distribution mirrors as seen from an Azure data centre.

- Workflow: [`.github/workflows/install-linux.yml`](../../.github/workflows/install-linux.yml)
- Host-side runner: [`run-distro.sh`](run-distro.sh), in-container script: [`in-container.sh`](in-container.sh), recorder: [`../scripts/castrec.py`](../scripts/castrec.py)
- Table generator: [`summarize.py`](summarize.py) -> [`results/summary.tsv`](results/summary.tsv)

## Files per distribution (`results/<flavour>/`)

| File | What it is |
|---|---|
| `session.cast` | The whole terminal session as an [asciicast v2](https://docs.asciinema.org/manual/asciicast/v2/) file: a JSON header, then `[seconds, "o", text]` events, recorded from a pseudo-terminal (120x36). Replay with asciinema-player. |
| `session.log` | The same output as plain text (ANSI colours kept). |
| `steps.tsv` | Wall time (s, 10 ms resolution from `/proc/uptime`) and exit code of every command. |
| `notes.txt` | `du -skx /` before and after (after the package cache was cleaned). |
| `host.txt` | `docker pull` time, image id, digest, image size. |
| `os-release.txt`, `meta.json` | Exact OS inside the container; runner CPU/cores/image. |

## Results

Command in all apt-based images: `apt-get update && apt-get install -y tesseract-ocr`. Others as listed.

| Container (exact OS) | Install command | Tesseract | Leptonica | install cmd (s) | index refresh (s) | first OCR (s) | Package manager says (download / installed) | Root FS growth after cache clean | Languages after install |
|---|---|---|---|---|---|---|---|---|---|
| `ubuntu:22.04` (Ubuntu 22.04.5 LTS) | `apt-get install -y tesseract-ocr` | **4.1.1** | 1.82.0 | 12.41 | 4.08 | 0.22 | 27.2 MB / 85.9 MB | 164.5 MiB | eng, osd |
| `ubuntu:24.04` (Ubuntu 24.04.5 LTS) | `apt-get install -y tesseract-ocr` | 5.3.4 | 1.82.0 | 8.38 | 4.07 | 0.26 | 32.3 MB / 96.3 MB | 149.9 MiB | eng, osd |
| `ubuntu:24.04` + PPA `alex-p/tesseract-ocr5` | `add-apt-repository -y ppa:alex-p/tesseract-ocr5` then `apt-get install -y tesseract-ocr` | 5.5.1 | 1.82.0 | 5.59 | 3.14 | 0.18 | 15.4 MB / 41.9 MB (after `software-properties-common`, which took 14.20 s) | 266.8 MiB (incl. software-properties-common) | eng, osd |
| `debian:12` (bookworm) | `apt-get install -y tesseract-ocr` | 5.3.0 | 1.82.0 | 9.44 | 1.60 | 0.25 | 36.9 MB / 120 MB | 141.2 MiB | eng, osd |
| `debian:13` (trixie) | `apt-get install -y tesseract-ocr` | 5.5.0 | 1.84.1 | 10.44 | 1.31 | 0.29 | 37.4 MB / 126 MB | 149.4 MiB | eng, osd |
| `fedora:latest` (Fedora Linux 45) | `dnf install -y tesseract` | 5.5.4 | 1.87.0 | 5.37 (incl. metadata download) | – | 0.16 | 6 MiB / 14 MiB (13 packages) | 98.5 MiB (see note) | eng |
| `archlinux:latest` | `pacman -Sy` then `pacman -S --noconfirm --needed tesseract tesseract-data-eng` | 5.5.4 | 1.87.0 | 0.74 | 0.41 | 0.26 | 18.52 MiB / 61.18 MiB | 76.1 MiB | eng, osd |
| `alpine:latest` (Alpine 3.24) | `apk add tesseract-ocr` **then** `apk add tesseract-ocr-data-eng` | 5.5.2 | 1.87.0 | 0.93 + 0.48 | 0.41 | 0.38 | `OK: 44.8 MiB in 58 packages` -> `OK: 67.1 MiB in 59 packages` (whole system) | 63.6 MiB | **none** until `tesseract-ocr-data-eng` |
| `opensuse/tumbleweed:latest` | `zypper refresh` then `zypper install tesseract-ocr` | 5.5.4 | 1.87.0 | 3.35 | 8.09 | 0.19 | 24.1 MiB / 72.9 MiB | 146.4 MiB | eng (pulled in as `tesseract-ocr-traineddata-eng`) |
| `condaforge/miniforge3:latest` | `conda install -y -c conda-forge tesseract` | 5.5.4 | 1.87.0 | 10.69 | – | 0.25 | 178.1 MB download | 386.7 MiB (`/opt/conda` growth) | **125 languages** |

Times are single runs (not medians) and include mirror downloads; they show orders of magnitude, not a benchmark. The exact per-command numbers are in each
`steps.tsv`; the table is regenerated with `python3 install/linux/summarize.py`.

Notes, all visible in the transcripts:
- **Ubuntu 22.04 still ships Tesseract 4.1.1**, and its `--list-langs` prints `List of available languages (2):` without a path. Ubuntu 24.04 ships 5.3.4 (from `noble/universe`).
- **Alpine:** `apk add tesseract-ocr` installs no language data. `tesseract --list-langs` prints `(0)` and OCR fails with `Error opening data file /usr/share/tessdata/eng.traineddata`. Fix: `apk add tesseract-ocr-data-eng`.
- **Arch:** `pacman -S tesseract` alone needs a `tessdata` provider. With `--noconfirm`, `pacman -Sp` shows it would pick **`tesseract-data-afr`** (Afrikaans) plus `tesseract-data-osd`. Name the language package explicitly.
- **Fedora:** the base `tesseract` package pulls `tesseract-langpack-eng` (eng only, no osd). The root FS growth (98.5 MiB) is much larger than dnf's own 14 MiB because repository metadata stays on disk; `dnf clean all` was run.
- **conda-forge:** the `tesseract` package brings 125 languages (172.7 MB package), unlike every distro package.
- Extra sizes, from `apt-get install --assume-no` (nothing installed): `tesseract-ocr-all` = 160 packages, 686 MB on Ubuntu 22.04/24.04 and Debian 12/13 (download 281–315 MB).
  `libtesseract-dev`: Ubuntu 24.04 = 34.9 MB download / 117 MB; Debian 13 = 53.6 MB / 279 MB; Debian 12 = 6.75 MB / 25.2 MB; Ubuntu 22.04 = 3.7 MB / 16.0 MB. Fedora `tesseract-devel`: 7 MiB / 28 MiB.
- Language packages available (count from the package manager search in each transcript): apt 123 `tesseract-ocr-<lang>` packages (excl. `-all`, `-script-*`, `-osd`); Fedora 123 `tesseract-langpack-*`; Arch 129 `tesseract-data-*`; Alpine 67 `tesseract-ocr-data-*`; openSUSE 164 lines matching `tesseract-ocr-traineddata-*`.
- Each transcript ends with real error messages: `-l xyz`, `--tessdata-dir /nonexistent`, `TESSDATA_PREFIX=/tmp`, and a missing input file. See [`../ERRORS.md`](../ERRORS.md).

## Third-party Docker images (`results/docker-images/`)

Docker Hub search for `tesseract` (sorted by pulls) is in `hub-search.tsv`. There is **no Docker Official Image** for Tesseract (`is_official` is false for every hit).
The most-pulled hit, plus images that are commonly cited, were pulled and run (`images.tsv`, `versions.txt`):

| Image | Hub pulls | `latest` pushed | Compressed / uncompressed | Tesseract inside |
|---|---|---|---|---|
| `sleeck/tesseract` (most pulled; "jpg to pdf with flasgger") | 1,137,919 | 2021-07-06 | 642 MB / 1,360 MB | 4.0.0 (leptonica 1.76.0) |
| `jitesoft/tesseract-ocr` | 243,261 | 2026-11-12 | 130 MB / 267 MB | 5.5.4 (leptonica 1.87.0) |
| `minidocks/tesseract` | 207,327 | 2026-11-17 | 36 MB / 87.5 MB | 5.5.2 (leptonica 1.87.0) |
| `tesseractshadow/tesseract4re` | 160,542 | 2020-01-06 | 442 MB / 913 MB | 4.1.1-rc2-21-gf4ef (leptonica 1.78.0) |
| `franky1/tesseract` | 97,793 | 2026-11-16 | 182 MB / 493 MB | 5.5.4 (leptonica 1.82.0) |

`demisto/tesseract` (2nd by pulls) has no `latest` tag (`manifest unknown`), so it was not pulled. Pull counts are Docker Hub's numbers on 2026-11-18.

## WSL2

WSL2 **does** work on the `windows-latest` runner (WSL 3.0.3.0, kernel 6.18.54.1-microsoft-standard-WSL2). The Ubuntu 24.04 install inside WSL is captured under
[`../windows/wsl/`](../windows/wsl/).
