# Lab conventions (read before adding anything)

This repo is public. It holds the reproducible tests behind the measured numbers on tesseractocr.org.

## Honesty rules (non-negotiable)
- Never invent, round up or "estimate" a number that is published as measured. Every number must come from a script in this repo and a raw result file.
- If a test fails, a tool won't install, or a result looks bad for Tesseract, record it as it is.
- Synthetic or simulated images are labelled `synthetic` in their metadata, and in captions later. Third-party images keep their source and licence in `SOURCES.md` next to them. Only public domain, CC0 or CC-BY is allowed.
- Never describe a machine as something it isn't. GitHub's Windows runner is "Windows Server 2025 (build 26100)", not Windows 11.
- No traffic, revenue or SEO data goes in this repo.

## Where things run
- **Accuracy** (CER/WER, output text): any machine, since it's deterministic for a given engine version and model. It may run in the development container.
- **Speed, memory and timing:** only published from GitHub Actions runners (`ubuntu-24.04`, `windows-latest`, `macos-latest`). Each runner's CPU model and core count goes into the run's `meta.json`. Development-container timings are for debugging only.

## Engine and models
- Default engine: **Tesseract 5.5.4** (upstream release 2026-10-28). On Actions it is built from tag `5.5.4`; the build script is in `tools/`.
- Ubuntu 24.04's packaged 5.3.4 is used only where "the version apt gives you" is the point of the test.
- Models: `tessdata_fast`, `tessdata` (standard) and `tessdata_best`, pinned by commit hash. Record the hash in `meta.json`.

## Layout
```
corpus/                shared test images + ground truth (generated, or third-party with SOURCES.md)
bench/<topic>/         one folder per test: run script, README.md (method + key findings), results/
  results/meta.json    engine version, models + hashes, OS, CPU, cores, date, command lines, git sha
  results/*.csv|json   raw numbers; charts are drawn from these and nothing else
  results/raw/         raw outputs (txt, tsv, hocr, logs) where useful
install/<os>/          install captures: logs, screenshots (raw, unbranded), checksums
tools/                 shared helpers (metrics, rendering, engine build, image pipeline)
.github/workflows/     the Actions runs that produce published numbers
```

## Metrics
- **CER** = Levenshtein(char) / len(ground truth). **WER** = Levenshtein(words) / words in ground truth.
- Before comparing: Unicode NFC, collapse runs of whitespace to one space, strip leading and trailing whitespace. Case and punctuation are kept.
- Implementation: `tools/metrics.py` (shared; don't fork it).
- Timing: median of 5 runs after 1 warm-up. Report min and max too. `OMP_THREAD_LIMIT=1` unless the test is about threads.

## Raw captures and screenshots
- Raw screenshots are PNGs, unbranded and uncropped. Branding and resizing come later from `tools/images/`, so the originals always stay here.
- Name files after what they show: `windows-installer-03-select-components.png`.

## Git
- Work on branch `claude/upbeat-volta-fdndl6`. Commit only your own folders. Run `git pull --rebase` before `git push`, and retry on conflict.
- Don't commit big binaries (>20 MB) or downloaded third-party tools/models. Write scripts that fetch them.
