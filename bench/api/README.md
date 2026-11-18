# OCR as an HTTP API: the /api/ page's FastAPI service under load, Docker image sizes, cold start

- **Run:** GitHub Actions `ubuntu-24.04`, Intel Xeon 6975P-C, 4 vCPU, Docker 28.0.4 — run
  [44309687300](https://github.com/dencyclopedia/test/actions/runs/44309687300) (`results/meta.json`). The run before it
  ([44303395441](https://github.com/dencyclopedia/test/actions/runs/44303395441), same CPU) gave the same pass/fail
  pattern, but latencies varied between the two runs (e.g. host pool 4, A4, closed-loop p50 3.98 s there vs 8.52 s
  here; Docker page image A4 burst max 4.12 s there vs 4.71 s here) — single runs, read latencies as approximate.
- **Service:** `app.py` = the page's "production Python service" verbatim, except the pool size comes from
  `POOL_WORKERS` (page: 4) and the language list from `OCR_LANGS`. One uvicorn worker. On the host it runs Tesseract
  5.5.4 (built from tag, eng tessdata_fast); in Docker it runs the page's Dockerfile **verbatim** (`docker/Dockerfile.page`,
  python:3.12-slim → Debian's **tesseract 5.5.0**, Leptonica 1.84.1).
- **Load client:** `loadtest.py` (httpx, same runner). *burst* = 8 simultaneous requests, repeated 5× after a warm-up;
  *closed* = 8 concurrent clients until N requests are done (A4: 24, receipt: 80).
- **Images (synthetic):** A4 page, 2481×3507 px, 300 DPI PNG (4.9 MB, Liberation Serif 11 pt + scan noise);
  till receipt 600×800 px, 200 DPI (`results/raw/receipt.png`).
- `PY=venv/bin/python bash run_api.sh WORK results`

## The page's claim, re-tested: 8 concurrent requests, 4 cores, pool 4, with and without `OMP_THREAD_LIMIT=1`

The page's own Docker image, `ENV OMP_THREAD_LIMIT=1` line present vs removed (`results/docker_claim.jsonl`):

| Image | 8 × A4 page | 8 × receipt |
|---|---|---|
| page Dockerfile (`OMP_THREAD_LIMIT=1`) | 40/40 HTTP 200; p50 3.5 s, slowest **4.7 s** | 40/40 200; p50 0.47 s, slowest 0.63 s |
| same without the ENV line | **40/40 HTTP 504 after ~30.2 s** | **40/40 HTTP 504 after ~30.0 s** |

- **Confirmed:** without `OMP_THREAD_LIMIT=1`, every one of 8 concurrent requests failed with 504 at the 30 s
  `wait_for` limit — for the A4 page *and* for the small receipt.
- **Not confirmed:** "with `OMP_THREAD_LIMIT=1` all 8 returned in under a second". For an A4 300-DPI page the 8
  responses took up to 4.7 s (p50 3.5 s); under a second only for the receipt.

## Load matrix on the host (Tesseract 5.5.4) — `results/host_matrix.jsonl`

| Pool | `OMP_THREAD_LIMIT` | Image | Burst of 8: result, p50 / max | Closed loop: RPS, p50 / p95 |
|---|---|---|---|---|
| 1 | unset | A4 | 40×200, 7.6 / 13.4 s | 0.60 RPS, 13.2 / 13.3 s |
| 1 | 1 | A4 | 40×200, 7.4 / 13.2 s | 0.62 RPS, 13.0 / 13.0 s |
| 2 | unset | A4 | **40×504** at 30.2 s | 0 RPS (24×504) |
| 2 | 1 | A4 | 40×200, 5.0 / 13.4 s | 1.20 RPS, 6.6 / 6.7 s |
| 4 | unset | A4 | **40×504** at 30.3 s | 0 RPS (24×504) |
| 4 | 1 | A4 | 40×200, 14.0 / 20.8 s | 0.82 RPS, 8.5 / 15.0 s |
| 1 | unset | receipt | 40×200, 0.98 / 1.76 s | 4.59 RPS, 1.73 / 1.83 s |
| 1 | 1 | receipt | 40×200, 0.95 / 1.69 s | 4.71 RPS, 1.70 / 1.71 s |
| 2 | unset | receipt | **40×504** at 30.0 s | 0 RPS (80×504) |
| 2 | 1 | receipt | 40×200, 0.55 / 0.87 s | 9.25 RPS, 0.86 / 0.87 s |
| 4 | unset | receipt | **40×504** at 30.1 s | 0 RPS (80×504) |
| 4 | 1 | receipt | 40×200, 0.48 / 0.64 s | **12.67 RPS**, 0.63 / 0.64 s |

- With **more than one OCR process and `OMP_THREAD_LIMIT` unset, nothing succeeded**: every request hit the 30 s
  timeout (pool 2 and pool 4, both images). A single process was not affected (pool 1: same speed either way).
- With `OMP_THREAD_LIMIT=1`, receipts scaled with the pool: 4.71 → 9.25 → 12.67 RPS for pool 1 → 2 → 4.
- A4 pages on the host peaked at pool 2 (1.20 RPS); pool 4 was slower here (0.82 RPS, p95 15 s), while the
  page's Docker image with pool 4 served 8 A4 pages in ≤4.7 s. We did not isolate why the host pool-4 A4 case was
  slow (the load client shares the 4 vCPUs; engine 5.5.4 vs 5.5.0); treat that row with caution.

## Docker image sizes and cold start — `results/image_matrix.jsonl`, `results/page_image_sizes.jsonl`

Every image contains the same API (`app.py`, fastapi, uvicorn, python-multipart, pytesseract, pillow).
"distro" = the distribution's language packages; "fast"/"best" = pinned tessdata_fast / tessdata_best files ADDed
(the distro copy removed in the same layer). Cold start = `docker run -d` → first HTTP 200 from `POST /ocr`
(receipt), median of 5 after 1 warm-up, image already local.

| Base | Tesseract | Models | eng | eng+deu | Cold start (eng) |
|---|---|---|---|---|---|
| python:3.12-slim | 5.5.0 | distro | 268.0 MB | 269.5 MB | 0.65 s |
| python:3.12-slim | 5.5.0 | fast | 268.0 MB | 269.5 MB | 0.65 s |
| python:3.12-slim | 5.5.0 | best | 279.3 MB | 287.9 MB | 0.97 s |
| debian:12-slim | 5.3.0 | distro | 274.3 MB | 275.8 MB | 0.60 s |
| debian:12-slim | 5.3.0 | fast | 274.3 MB | 275.8 MB | 0.59 s |
| debian:12-slim | 5.3.0 | best | 285.6 MB | 294.2 MB | 0.91 s |
| alpine:3.22 | 5.5.0 | distro | 156.1 MB | 171.5 MB | 0.89 s |
| alpine:3.22 | 5.5.0 | fast | **136.7 MB** | 138.3 MB | 0.78 s |
| alpine:3.22 | 5.5.0 | best | 148.0 MB | 156.7 MB | **2.46 s** |

- The page's Dockerfile, verbatim, built to **269.5 MB** (the page says 396 MB); with `libgl1 libglib2.0-0` added,
  **474.0 MB** (page: 670 MB). The image tag `python:3.12-slim` now gives Debian trixie with Tesseract 5.5.0.
- **Debian's `tesseract-ocr-eng` is the tessdata_fast file** (4,113,088 bytes, same as pinned tessdata_fast), so
  "distro" = "fast" there; **Alpine's `tesseract-ocr-data-eng` is the standard tessdata model** (23,466,654 bytes,
  with legacy engine data), which is why Alpine distro > Alpine fast.
- Debian-based images always also carry `osd.traineddata` (10.6 MB) because `tesseract-ocr` depends on it.
- Adding German costs 1.5 MB (fast) or 8.6 MB (best). tessdata_best adds ~11 MB for eng and slows cold start
  (0.97 vs 0.65 s on python:3.12-slim; 2.46 vs 0.78 s on Alpine).

## curl transcript — `results/curl-transcript.txt`, `results/response.json`

Real requests against the page's image: `POST /ocr?lang=eng` → 200 with `{"text": …, "lang": "eng"}`; `lang=fra`
→ 400 `{"detail":"Unsupported language"}`; an 11 MB upload → `413 Request Entity Too Large`
`{"detail":"File too large"}`; **a non-image upload → `500 Internal Server Error`** (`PIL.UnidentifiedImageError` in
`results/raw/curl-server.log`): the page's code does not catch decode errors, although the page's security section
says to "decode in a try/except".

## Claims on the live /api/ page

| Claim | Result |
|---|---|
| 8 concurrent A4 requests on 4 cores all fail with 504 after 25–30 s without `OMP_THREAD_LIMIT=1` | **Confirmed** (all 40 → 504 at ~30 s; receipts too) |
| with `OMP_THREAD_LIMIT=1` all 8 returned in under a second | **Refuted for A4** (up to 4.7 s); true for a receipt (≤0.63 s) |
| a 396 MB image | **269.5 MB** measured for the page's Dockerfile today |
| OpenCV libs grew it from 396 MB to 670 MB | **269.5 → 474.0 MB** measured |
| Tesseract images are large, so cold starts are slow | Cold start 0.6–1.0 s (2.5 s Alpine + best) once the image is pulled; pull time not measured |
| decode in a try/except | the page's own code doesn't: bad upload → 500 |
