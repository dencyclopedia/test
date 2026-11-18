# macOS install captures

Workflows: [`install-macos.yml`](../../.github/workflows/install-macos.yml) (Homebrew + Terminal.app screenshots, script [`scripts/mac.sh`](scripts/mac.sh)),
[`install-macports.yml`](../../.github/workflows/install-macports.yml) ([`scripts/macports.sh`](scripts/macports.sh)) and
[`install-macos-intel.yml`](../../.github/workflows/install-macos-intel.yml) (Intel source build without a time cap).

The commands that matter ran **inside Terminal.app**: each step is a `.command` file opened with `open -a Terminal`; its output is also `tee`d to a `.log`
next to the screenshot. Screenshots are `screencapture -l<window id>` (window only, with shadow removed) plus `screencapture -x` of the whole screen
(`*-desktop.png`). Prompts are the real zsh prompt (`user@hostname`; the hostname is the runner VM's).

## Machines

| Folder | Runner label | Exact machine |
|---|---|---|
| `brew-macos-latest/` | `macos-latest` | macOS 26.7.2 (25G332), **arm64**, "Apple M1 (Virtual)", 3 cores, runner image macos26 20261102.0473.1, Homebrew 7.0.11 |
| `brew-macos-15-intel/`, `brew-macos-15-intel-full/` | `macos-15-intel` | macOS 15.7.9 (24G830), **x86_64**, Intel Core i7-8700B, 4 cores, runner image macos15 20260824.0482.1, Homebrew 6.0.18 |
| (none) | `macos-13` | **No result.** The jobs for this label stayed "queued" with no runner assigned for over an hour (runs 44255392057 and 44255599287); the label appears to be retired. |
| `macports/` | `macos-latest` | macOS 26.7.2 (25G332) arm64 |

## Homebrew on Apple Silicon (`brew-macos-latest/`)

| Step | Result |
|---|---|
| `brew info tesseract` before | stable 5.5.4, bottle for `arm64_tahoe`; 10 direct dependencies, **38 recursive** (`brew-deps.txt`, `brew-deps-tree.txt`) |
| Already on the runner image | **30 of the 38** dependencies (cairo, glib, harfbuzz, icu4c@79, …) — a clean Mac has to download more, so expect a longer install there |
| `brew update` (excluded from the install time) | 9 s |
| `time brew install tesseract` (in Terminal) | **28.345 s total** (21.98 s user, 7.95 s system); installed 8 dependencies (openjpeg, leptonica, libb2, libarchive, fribidi, libdatrie, libthai, pango) + tesseract, all from bottles |
| Size | `/opt/homebrew/Cellar/tesseract` = 25M (`du -sh`; brew's own line: 74 files, 26.1MB); free disk space dropped by 288,976 KiB, which includes Homebrew's download cache and the 8 dependencies |
| `tesseract --version` | 5.5.4, leptonica-1.87.0, "Found NEON" |
| `tesseract --list-langs` | `/opt/homebrew/share/tessdata/` (2): eng, osd |
| PATH | `which tesseract` = `/opt/homebrew/bin/tesseract`, nothing to set (brew's bin is already on PATH on the runner) |
| OCR of `samples/receipt.png` | correct text (`macos-terminal-03-ocr-receipt.png`) |
| `-l fra` before languages | `Error opening data file /opt/homebrew/share/tessdata/fra.traineddata` … (`-04-error-missing-language`) |
| `time brew install tesseract-lang` | **15.410 s total**; `Cellar/tesseract-lang` = 654M; `--list-langs` then shows **162** languages; `-l eng+fra` works (`-05`, `-06`) |
| pytesseract with a PATH lacking `/opt/homebrew/bin` | `TesseractNotFoundError` (`-07-error-pytesseract-not-found`); with the normal PATH the same script prints the receipt text |

Screenshots: `macos-terminal-01-brew-install-tesseract` … `-07-error-pytesseract-not-found` (7 window shots + 7 full-screen shots).

## Homebrew on Intel (`brew-macos-15-intel/`, `brew-macos-15-intel-full/`)

`brew info tesseract` on this runner (before `brew update`): stable **5.5.3**, bottle listed only for `sonoma`. `brew update` took 345 s.
`brew install tesseract` then **compiled dependencies from source** (readline, sqlite, xz, lz4, python@3.15, icu4c@79 "built in 4 minutes 22 seconds",
cairo, gobject-introspection, …). The Terminal capture stops waiting after 30 minutes; at that point it was still compiling (`macos-terminal-01-brew-install-tesseract.png`), so the
following windows show `command not found: tesseract`. The Intel-only workflow lets the build run to the end; its result is in `brew-macos-15-intel-full/` (see below).

INTEL_FULL_RESULT

## MacPorts (`macports/`)

MacPorts is not preinstalled on the runner. `scripts/macports.sh` installed the official `MacPorts-2.12.7-26-Tahoe.pkg` (from the macports-base GitHub
release) with `sudo installer` (35 s), `sudo port -N selfupdate` (18 s), then:

| Step | Result |
|---|---|
| `port info tesseract` | tesseract @5.5.3; 100 port names match `tesseract-*` (language sub-ports + `tesseract-training`) |
| `sudo port -N install tesseract` | **35 s**, binary archives from packages.macports.org; 34 ports installed in total |
| `/opt/local` size | 425M (`du -sh`, includes MacPorts base and the ports tree) |
| `tesseract --version` | 5.5.3, leptonica-1.87.0 |
| `--list-langs` right after | `/opt/local/share/tessdata/` **(0)**, OCR fails with `Error opening data file /opt/local/share/tessdata/eng.traineddata` |
| `sudo port -N install tesseract-eng` | 7 s (tesseract-eng @4.1.0); afterwards eng is listed and the receipt OCR works |

MacPorts was run from the shell script, not in Terminal.app, so there are no MacPorts screenshots.
