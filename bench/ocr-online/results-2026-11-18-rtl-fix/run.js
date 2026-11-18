#!/usr/bin/env node
// Drive the real in-browser OCR tool of tesseractocr.org (ocr-online/index.html + assets/ocr-tool.js) with
// Playwright/Chromium on corpus images, and capture its output text and raw screenshots.
//
// Usage:
//   (cd <site checkout> && python3 -m http.server 8765 --bind 127.0.0.1) &
//   SITE=http://127.0.0.1:8765 node bench/ocr-online/results-2026-11-18-rtl-fix/run.js
// Third-party ad, analytics and consent scripts on the page are blocked (route.abort) so no ad/analytics
// requests are made and no consent banner covers the tool; the tool's own script and its CDN dependencies
// (tesseract.js + language models from cdn.jsdelivr.net) load normally.
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const SITE = process.env.SITE || 'http://127.0.0.1:8765';
const HERE = path.resolve(__dirname, '..');  // this file lives in a results-* folder
const REPO = path.resolve(HERE, '..', '..');
const RES = __dirname;
const SHOTS = path.join(RES, 'screenshots');
const RAW = path.join(RES, 'raw', 'browser');
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
const SHOT_FOR = new Set(['receipt', 'page', 'screenshot-dark', 'sideways-90']);

(async () => {
  fs.mkdirSync(SHOTS, { recursive: true });
  fs.mkdirSync(RAW, { recursive: true });
  const manifest = JSON.parse(fs.readFileSync(path.join(REPO, 'corpus', 'manifest.json'), 'utf8')).images;
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const blocked = new Set(), models = new Set(), scripts = new Set(), failed = [];
  await ctx.route('**/*', (route) => {
    const u = route.request().url();
    if (BLOCK.test(u)) { blocked.add(new URL(u).host); return route.abort(); }
    if (/traineddata/.test(u)) models.add(u);
    if (/tesseract/.test(u) && /\.js$/.test(u)) scripts.add(u);
    return route.continue();
  });
  ctx.on('requestfailed', (r) => { if (!BLOCK.test(r.url())) failed.push(r.url() + ' ' + (r.failure() || {}).errorText); });
  const page = await ctx.newPage();
  const consoleLog = [];
  page.on('console', (m) => consoleLog.push(m.type() + ': ' + m.text()));
  await page.goto(SITE + '/ocr-online/', { waitUntil: 'domcontentloaded' });
  await page.locator('#ocr-tool').scrollIntoViewIfNeeded();
  await page.screenshot({ path: path.join(SHOTS, 'ocr-online-01-empty.png') });

  const results = [];
  let n = 2;
  for (const [label, id] of IMAGES) {
    const e = manifest.find((x) => x.id === id);
    if (!e) throw new Error('not in manifest: ' + id);
    const lang = e.lang;
    await page.goto(SITE + '/ocr-online/', { waitUntil: 'domcontentloaded' });
    await page.selectOption('#language-select', lang);
    await page.setInputFiles('#file-input', path.join(REPO, 'corpus', e.image));
    await page.waitForSelector('#extract-btn:not([disabled])');
    const shoot = SHOT_FOR.has(label);
    if (shoot) {
      await page.locator('#ocr-tool').scrollIntoViewIfNeeded();
      await page.screenshot({ path: path.join(SHOTS, `ocr-online-${String(n++).padStart(2, '0')}-file-selected-${label}.png`) });
    }
    const t0 = Date.now();
    await page.click('#extract-btn');
    if (shoot) {
      try {
        await page.waitForFunction(() => {
          const p = document.getElementById('progress-percent');
          return p && !document.getElementById('progress-container').hidden && parseInt(p.textContent, 10) > 10;
        }, null, { timeout: 120000 });
        await page.screenshot({ path: path.join(SHOTS, `ocr-online-${String(n++).padStart(2, '0')}-processing-${label}.png`) });
      } catch (err) { /* finished before we could catch the progress bar */ }
    }
    let status = 'ok';
    try {
      await page.waitForFunction(() => {
        const s = document.getElementById('result-stats'), m = document.getElementById('tool-message');
        const btn = document.getElementById('extract-btn');
        return (s && !s.hidden) || (m && !m.hidden && /error/.test(m.className)) || (btn && !btn.disabled && document.getElementById('output-text').value);
      }, null, { timeout: 600000, polling: 500 });
    } catch (err) { status = 'timeout'; }
    const ms = Date.now() - t0;
    const out = await page.$eval('#output-text', (el) => el.value);
    const msg = await page.$eval('#tool-message', (el) => (el.hidden ? '' : el.textContent));
    const conf = await page.$eval('#confidence-badge', (el) => (el.hidden ? '' : el.textContent)).catch(() => '');
    if (msg && /error/i.test(await page.$eval('#tool-message', (el) => el.className))) status = 'error';
    fs.mkdirSync(path.dirname(path.join(RAW, id)), { recursive: true });
    fs.writeFileSync(path.join(RAW, id + '.txt'), out);
    if (shoot) {
      await page.locator('#output-text').scrollIntoViewIfNeeded();
      await page.screenshot({ path: path.join(SHOTS, `ocr-online-${String(n++).padStart(2, '0')}-result-${label}.png`) });
    }
    results.push({ label, id, lang, status, message: msg, confidence_badge: conf, wall_ms_dev_container: ms });
    console.log(label, status, ms + 'ms', out.length + ' chars');
  }
  const tjsVersion = await page.evaluate(() => (window.Tesseract && window.Tesseract.version) || null).catch(() => null);
  await browser.close();
  fs.writeFileSync(path.join(RES, 'browser_runs.json'), JSON.stringify({
    site: SITE, tool_files: ['ocr-online/index.html', 'assets/ocr-tool.js'], chromium: browser.version(),
    playwright: require('playwright/package.json').version, tesseract_js_reported_version: tjsVersion,
    settings: 'defaults: Layout mode PSM 3, Enhance contrast off, language = image language, second language none',
    blocked_third_party_hosts: [...blocked].sort(), model_urls: [...models].sort(), script_urls: [...scripts].sort(),
    failed_requests: failed, console: consoleLog.slice(0, 200), runs: results,
  }, null, 1) + '\n');
})();
