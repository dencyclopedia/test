# Same 10 images through 9 Tesseract bindings

- **Run:** GitHub Actions `ubuntu-24.04`, AMD EPYC 7763, 4 vCPU — run
  [44311512745](https://github.com/dencyclopedia/test/actions/runs/44311512745) (`results/meta.json`). An earlier run on
  an Intel Xeon 6975P-C runner ([44258321224](https://github.com/dencyclopedia/test/actions/runs/44258321224)) gave the
  same identity results; its timings differ (different CPU) and are not used here.
- **Engine:** Tesseract 5.5.4 built from the tag (`../train/build-tesseract.sh`), system Leptonica 1.82.0,
  `eng` from tessdata_fast (pinned). `OMP_THREAD_LIMIT=1` everywhere.
- **Images (synthetic):** `make_images.py` — 10 × 2481×1170 px, 300 DPI, Liberation Serif 11 pt with seeded scan
  noise (*Pride and Prejudice*, public domain) + `tiny.png` (one word, 420×90 px) for per-call overhead.
- **Protocol** (every harness): init once, 1 warm-up, 20 calls on `tiny.png` (per-call overhead), one pass whose
  text is compared, then 5 timed passes over the 10 images (images/s = 10 / median pass). Peak RSS = GNU
  `time -v` max RSS of the harness process (for CLI/pytesseract: the largest single process). Identity = exact
  bytes vs `tesseract img stdout` with the same model and PSM; "normalised" = after `tools/metrics.normalize`.
- Harnesses: `python/harness.py` (CLI via subprocess, pytesseract, tesserocr), `cpp/harness.cpp` (TessBaseAPI),
  `go/main.go` (gosseract v2.4.1), `java/` (Tess4J, Maven), `dotnet/` (NuGet Tesseract 5.2.0, .NET 8),
  `node/harness.js` (tesseract.js 7.0.0). Driver: `run_bindings.py`; tables: `summarize.py`.

## Results (`results/bindings.json`)

| Binding | PSM | Engine (as reported) | Init s | Per-call ms (tiny img, median) | Images/s (10 imgs) | Peak RSS MB | CER | Identical to CLI (bytes / normalised) |
|---|---|---|---|---|---|---|---|---|
| tesseract-cli | default | tesseract 5.5.4 | – | 101.37 | 1.719 | 49.9 | 0.861 % | (reference) |
| pytesseract | default | 5.5.4 | – | 102.5 | 1.251 | 49.9 | 1.069 % | 8/10 / 8/10 |
| tesserocr-wheel | default | tesseract 5.5.4 / leptonica-1.87.0 | 0.0783 | 5.59 | 2.419 | 59.3 | 0.861 % | 10/10 / 10/10 |
| cpp-tessbaseapi | default | 5.5.4 | 0.0804 | 6.15 | 2.286 | 50.7 | 1.594 % | 0/10 / 0/10 |
| gosseract | default | 5.5.4 | 0.0918 | 6.34 | 2.277 | 52.8 | 1.594 % | 0/10 / 0/10 |
| tess4j | default | system libtesseract via JNA | 0.3229 | 74.8 | 1.89 | 219.0 | 1.594 % | 0/10 / 0/10 |
| dotnet-tesseract | default | 5.5.4 | 0.1692 | 7.0 | 2.082 | 91.2 | 0.861 % | 10/10 / 10/10 |
| tesseractjs-localmodel | default | 7.0.0 | 0.2524 | 9.55 | 1.728 | 210.8 | 1.707 % | 0/10 / 0/10 |
| tesseractjs-cdnmodel | default | 7.0.0 | 0.3768 | 13.6 | 1.21 | 217.7 | 1.893 % | 0/10 / 0/10 |
| tesserocr-source-5.5.4 | default | tesseract 5.5.4 / leptonica-1.82.0 | 0.0781 | 6.74 | 2.11 | 66.6 | 0.861 % | 10/10 / 10/10 |
| tesseract-cli-tjsmodel | default | tesseract 5.5.4 | – | 106.13 | 1.413 | 52.8 | 0.622 % | 0/10 / 0/10 |
| tesseract-cli | 3 | tesseract 5.5.4 | – | 97.7 | 1.744 | 50.0 | 0.861 % | (reference) |
| pytesseract | 3 | 5.5.4 | – | 97.76 | 1.259 | 49.9 | 1.069 % | 8/10 / 8/10 |
| tesserocr-wheel | 3 | tesseract 5.5.4 / leptonica-1.87.0 | 0.0762 | 5.62 | 2.441 | 59.4 | 0.861 % | 10/10 / 10/10 |
| cpp-tessbaseapi | 3 | 5.5.4 | 0.0775 | 6.73 | 2.106 | 52.0 | 0.861 % | 10/10 / 10/10 |
| gosseract | 3 | 5.5.4 | 0.0868 | 6.19 | 2.297 | 67.1 | 1.594 % | 0/10 / 0/10 |
| tess4j | 3 | system libtesseract via JNA | 0.3292 | 76.48 | 1.823 | 221.5 | 1.069 % | 8/10 / 8/10 |
| dotnet-tesseract | 3 | 5.5.4 | 0.1554 | 6.83 | 2.089 | 91.9 | 0.861 % | 10/10 / 10/10 |
| tesseractjs-localmodel | 3 | 7.0.0 | 0.2469 | 10.49 | 1.604 | 242.6 | 0.821 % | 6/10 / 6/10 |
| tesseractjs-cdnmodel | 3 | 7.0.0 | 0.3701 | 14.5 | 1.148 | 244.5 | 0.598 % | 7/10 / 7/10 |
| tesserocr-source-5.5.4 | 3 | tesseract 5.5.4 / leptonica-1.82.0 | 0.0777 | 6.72 | 2.112 | 66.7 | 0.861 % | 10/10 / 10/10 |
| tesseract-cli-tjsmodel | 3 | tesseract 5.5.4 | – | 105.61 | 1.409 | 52.8 | 0.622 % | 0/10 / 0/10 |
| gosseract | 3var | 5.5.4 | 0.088 | 6.88 | 2.108 | 53.4 | 0.861 % | 0/10 / 10/10 |

`default` = each binding's own default page-segmentation mode; `3` = PSM 3 set explicitly. `tesseract-cli-tjsmodel` = the
CLI run with tesseract.js's CDN model, the reference for `tesseractjs-cdnmodel`.

## Key findings

- **Per-call overhead:** CLI wrappers pay a process start + model load on every call: **~100 ms** per call on a
  one-word image (CLI 101 ms, pytesseract 103 ms). In-process bindings that keep the engine: **5.6–7.0 ms**
  (tesserocr, C++, gosseract, .NET); tesseract.js 9.6 ms (local model) / 13.6 ms (CDN model).
  **Tess4J 75 ms** — `Tesseract.doOCR(File)` initialises and frees the engine on every call.
- **Throughput (10 images, 1 thread):** tesserocr 2.42 img/s, C++ 2.29, gosseract 2.28, .NET 2.08, Tess4J 1.89,
  CLI 1.72, tesseract.js 1.73 (local fast model) / 1.21 (CDN model), pytesseract **1.25**.
- **Peak RSS:** CLI/pytesseract ~50 MB, C++ 51 MB, gosseract 53 MB, tesserocr 59–67 MB, .NET 91 MB,
  **Tess4J 219 MB, tesseract.js 211–245 MB**.
- **Not every binding gives the CLI's text.**
  - The C++ API's default page-segmentation mode is **PSM 6** (single block), not the CLI's 3. C++ TessBaseAPI,
    gosseract and Tess4J therefore differ from the CLI on 10/10 images by default (CER 1.594 % vs 0.861 %).
    With PSM 3 set, C++ is byte-identical (10/10).
  - **gosseract: `SetPageSegMode()` before the first `Text()` is silently lost** (gosseract initialises lazily and
    `Init` resets it): still 0/10 with PSM 3. Setting it with `SetVariable("tessedit_pageseg_mode", "3")` works:
    identical after normalisation 10/10 (bytes differ only because gosseract trims the trailing newline).
  - **pytesseract** (PIL image in) and **Tess4J** (BufferedImage) lose the PNG's 300-DPI tag, so Tesseract
    estimates the resolution: 8/10 identical, CER 1.069 % vs 0.861 % (same in both PSM settings for pytesseract).
  - tesserocr (wheel, which bundles 5.5.4 with **Leptonica 1.87.0**), tesserocr built from source against
    5.5.4 + Leptonica 1.82, and **.NET** (default `Auto` = PSM 3) were byte-identical, 10/10.
  - **tesseract.js 7.0.0** runs a WebAssembly build reported as `5.1.0-288-g2a9c1` (string in
    `tesseract-core-simd-lstm.wasm`), not 5.5.4: with the same fast model and PSM 3, 6/10 identical; with its
    default CDN model (`@tesseract.js-data/eng/4.0.0_best_int`) vs the CLI with that same file, 7/10.
    Its default PSM gives different text again (0/10).
- **.NET on Linux:** the NuGet package (5.2.0, 2022) ships only Windows DLLs (`leptonica-1.82.0.dll`,
  `tesseract50.dll`). Without the fix it throws `System.DllNotFoundException: Failed to find library
  "libleptonica-1.82.0.so" for platform x64.` (`results/build/dotnet-before-symlinks.log`). The symlink fix from the
  /csharp/ page (`libleptonica-1.82.0.so → liblept.so.5`, `libtesseract50.so → libtesseract.so.5`, `libdl.so`)
  worked — here pointing at **libtesseract 5.5.4**, and `engine.Version` reports `5.5.4`.
- **Tess4J:** the newest release, **5.16.0, fails on Ubuntu 24.04**: `java.lang.UnsatisfiedLinkError: Error looking up
  function 'pixAddMultipleBlackWhiteBorders': /lib/x86_64-linux-gnu/liblept.so.5: undefined symbol: ...`
  (`results/build/tess4j-5.16.0-run.log`); 5.15.0 fails the same way (dev container); **5.14.0 works** and is the
  version measured. The 5.16.0 jars bundle only Windows DLLs (`libtesseract551.dll`, `libleptonica1850.dll`).

## Versions matrix (`results/versions.json`, from the registry APIs)

| Package | Registry | Latest | Released | Licence |
|---|---|---|---|---|
| tesseract (C++ engine, TessBaseAPI) | GitHub releases | 5.5.4 | 2026-10-28 | Apache-2.0 |
| pytesseract | PyPI | 0.3.13 | 2024-08-16 | Apache License 2.0 |
| tesserocr | PyPI | 2.13.0 | 2026-11-12 | MIT |
| tesseract.js | npm | 7.0.0 | 2025-12-15 | Apache-2.0 |
| tesseract.js-core | npm | 6.1.2 | 2025-12-15 | Apache-2.0 |
| tess4j | Maven Central | 5.16.0 | 2025-06-08 | Apache License 2.0 |
| gosseract | Go module proxy | v2.4.1 | 2023-09-06 | MIT |
| Tesseract (.NET NuGet) | NuGet | 5.2.0 | 2022-11-30 | Apache-2.0 |
| ocrmypdf | PyPI | 17.14.2 | 2026-11-16 | MPL-2.0 |

| Binding | Tesseract it uses | Notes |
|---|---|---|
| pytesseract 0.3.13 | the installed CLI (5.5.4 here) | CLI wrapper |
| tesserocr 2.13.0 (PyPI wheel) | **bundled 5.5.4 + Leptonica 1.87.0** | manylinux wheel; source build links the system lib |
| tesseract.js 7.0.0 (+ core 7.0.0) | **WASM `5.1.0-288-g2a9c1`** | npm `latest` tag of tesseract.js-core is 6.1.2, but tesseract.js 7.0.0 installs core 7.0.0; model from jsDelivr |
| Tess4J 5.14.0 (5.16.0 latest) | system libtesseract via JNA (5.5.4 here) | the 5.16.0 jars bundle only Windows DLLs (`libtesseract551.dll`, `libleptonica1850.dll`) |
| gosseract v2.4.1 | system libtesseract via cgo (5.5.4) | |
| Tesseract .NET 5.2.0 | Windows DLLs `tesseract50` / Leptonica 1.82.0; on Linux whatever the symlinks point at | |
| TessBaseAPI | 5.5.4 | |

## Claims on the live /libraries/ page

| Claim | Result |
|---|---|
| Native bindings avoid per-call process startup / are faster | **Confirmed**: ~6 ms vs ~100 ms per call; 2.1–2.4 vs 1.7 img/s (CLI) and 1.25 (pytesseract) |
| Tess4J is an in-process speed option | **Partly refuted**: `doOCR` re-initialises per call (75 ms); 219 MB RSS |
| .NET: "package (5.2.0) only bundles Windows DLLs", `DllNotFoundException ... libleptonica-1.82.0.so`, symlink fix | **Confirmed** verbatim; fix works |
| Only tesseract.js bundles its own engine | **Not quite**: the tesserocr wheel also bundles Tesseract 5.5.4 (+ Leptonica 1.87) |
| The same image gives the same text in every language | **Refuted** with defaults: PSM defaults and lost DPI change the output (above) |
