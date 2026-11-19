#!/usr/bin/env node
// Time the site's in-browser OCR tool (tesseract.js) on the 16 corpus images used in bench/ocr-online.
// Runs on a GitHub Actions runner (see .github/workflows/bench-ocr-online-timing.yml); timings from the
// shared development container are not publishable (LAB.md).
//
// Per image: 1 cold run (first time this language is used: includes downloading the tesseract.js core
// and the language model from cdn.jsdelivr.net), then 1 warm-up and 5 timed warm runs (model cached by
// the browser). Each run reloads the page, so tool start-up is included. Time = click "Extract text"
// until the result is shown. Reported: median of the 5 warm runs, plus min, max and the cold run.
//
// Usage: SITE=http://127.0.0.1:8790 OUT=<dir> node bench/ocr-online/timing/timing.js
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const SITE = process.env.SITE || 'http://127.0.0.1:8790';
const REPO = path.resolve(__dirname, '..', '..', '..');
const OUT = process.env.OUT || path.join(__dirname, 'results');
const RUNS = 5;
const BLOCK = /(gatekeeperconsent|ezojs|ezoic|googletagmanager|google-analytics|doubleclick|googlesyndication|adsbygoogle)/;
const IMAGES = [
  ['receipt', 'receipt/receipt01_dejavu-mono'],
  ['receipt-faded', 'receipt/receipt02_courier10_faded'],
  ['receipt-phone', 'receipt/receipt05_carlito_phone1'],
  ['page', 'clean/austen_dejavu-serif_300'],
  ['page-lowres-150dpi', 'clean/doyle_carlito_150'],
  ['phone-sim', 'degraded/doyle_carlito_phone1'],
  ['phone-sim-strong', 'degraded/austen_dejavu-serif_phone2'],
  ['skew-5deg', 'degraded/carroll_inter_skew5'],
  ['sideways-90', 'layout/rotated90_doyle_caladea'],
  ['upside-down-180', 'layout/rotated180_austen_carlito'],
  ['two-column', 'layout/twocolumn01_dejavu-serif'],
  ['screenshot-dark', 'screenshot/settings_dark_1x'],
  ['screenshot-light', 'screenshot/dashboard_light_1x'],
  ['non-latin-rus', 'multilingual/rus_p1_dejavu-serif'],
  ['non-latin-chi_sim', 'multilingual/chi_sim_p1_noto-sans-sc'],
  ['non-latin-ara', 'multilingual/ara_p1_noto-naskh-arabic'],
];
const median = (a) => { const s = [...a].sort((x, y) => x - y); return s[Math.floor(s.length / 2)]; };

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const manifest = JSON.parse(fs.readFileSync(path.join(REPO, 'corpus', 'manifest.json'), 'utf8')).images;
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  await ctx.route('**/*', (r) => (BLOCK.test(r.request().url()) ? r.abort() : r.continue()));
  const page = await ctx.newPage();

  async function once(file, lang) {
    await page.goto(SITE + '/ocr-online/', { waitUntil: 'domcontentloaded' });
    await page.selectOption('#language-select', lang);
    await page.setInputFiles('#file-input', file);
    await page.waitForSelector('#extract-btn:not([disabled])');
    const t0 = Date.now();
    await page.click('#extract-btn');
    let status = 'ok';
    try {
      await page.waitForFunction(() => {
        const s = document.getElementById('result-stats'), m = document.getElementById('tool-message');
        const btn = document.getElementById('extract-btn');
        return (s && !s.hidden) || (m && !m.hidden && /error/.test(m.className)) ||
          (btn && !btn.disabled && document.getElementById('output-text').value);
      }, null, { timeout: 600000, polling: 100 });
    } catch (e) { status = 'timeout'; }
    const ms = Date.now() - t0;
    const chars = await page.$eval('#output-text', (el) => el.value.length);
    return { ms, status, chars };
  }

  const seenLang = new Set();
  const rows = [];
  for (const [label, id] of IMAGES) {
    const e = manifest.find((x) => x.id === id);
    if (!e) throw new Error('not in manifest: ' + id);
    const file = path.join(REPO, 'corpus', e.image);
    let cold = null;
    if (!seenLang.has(e.lang)) { cold = await once(file, e.lang); seenLang.add(e.lang); }
    await once(file, e.lang); // warm-up
    const runs = [];
    for (let i = 0; i < RUNS; i++) runs.push(await once(file, e.lang));
    const ms = runs.map((r) => r.ms);
    const row = {
      label, id, lang: e.lang, runs: RUNS, median_s: +(median(ms) / 1000).toFixed(2),
      min_s: +(Math.min(...ms) / 1000).toFixed(2), max_s: +(Math.max(...ms) / 1000).toFixed(2),
      cold_first_use_s: cold ? +(cold.ms / 1000).toFixed(2) : '',
      statuses: [...new Set(runs.map((r) => r.status))].join('|'), output_chars: runs[0].chars,
    };
    rows.push(row);
    console.log(JSON.stringify(row));
  }
  const tjs = await page.evaluate(() => (window.Tesseract && window.Tesseract.version) || null).catch(() => null);
  const hdr = Object.keys(rows[0]);
  fs.writeFileSync(path.join(OUT, 'timing.csv'), [hdr.join(','), ...rows.map((r) => hdr.map((k) => r[k]).join(','))].join('\n') + '\n');
  const meta = JSON.parse(process.env.META_JSON || '{}');
  Object.assign(meta, {
    chromium: browser.version(), playwright: require('playwright/package.json').version,
    tesseract_js_reported_version: tjs, site_commit: fs.readFileSync(path.join(__dirname, 'site-snapshot', 'SITE_COMMIT'), 'utf8').trim(),
    method: 'per image: cold run on first use of a language, 1 warm-up, then 5 timed runs with a page reload each; time = click to result shown',
    settings: 'tool defaults (PSM 3, Enhance off), language = image language', date: new Date().toISOString(),
  });
  await browser.close();
  fs.writeFileSync(path.join(OUT, 'meta.json'), JSON.stringify(meta, null, 1) + '\n');
})();
