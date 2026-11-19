# Cookies, storage and requests on the live tesseractocr.org

```sh
node bench/privacy/capture.js bench/privacy/results   # Playwright Chromium; uses HTTPS_PROXY if set
python3 bench/privacy/summarize.py
```
- Visits `/`, `/install/` and `/privacy/` in one fresh profile (1440x900, en-US), waits, scrolls each page, then records every
  network request, every cookie (name, domain, expiry, flags; no values) and the localStorage/sessionStorage keys.
- Pass `no-consent`: no answer to any consent prompt. Pass `accept`: tries to click an accept button in the consent banner.
- Results: `results/meta.json`, `results/<pass>-requests.json`, `-cookies.json`, `-storage.json`, `-by-site.csv`.

## Findings (capture 2026-11-19 00:07 UTC, Chromium 157, from a data-centre connection)
- No consent banner appeared (the accept pass found no button), so both passes ran without any consent choice.
  Consent prompts depend on the visitor's region; this capture shows one region only.
- No consent: 2,881 requests to 176 sites (registrable domains), 394 cookies; 45 of them on tesseractocr.org itself, all set by
  the Ezoic, Google Analytics and ad-partner scripts (e.g. `ezoid`, `_ga`, `_ga_8CEH3DE1YK`, `__gads`, `__qca`, `cto_bundle`).
- Requests and cookies vary between runs (ad auctions); the accept pass gave 3,222 requests and 428 cookies.
- The site's own code stores one key, `theme` in localStorage, and only after the theme toggle is used.
