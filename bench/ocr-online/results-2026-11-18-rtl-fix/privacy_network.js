#!/usr/bin/env node
// Privacy + offline check of the online OCR tool: records every network request the page makes while the tool
// reads a corpus image (Playwright network log, request method and body size), then switches the browser context
// offline and reads a second image with the same language.
// Usage: (cd <site checkout> && python3 -m http.server 8791 --bind 127.0.0.1) &
//        SITE=http://127.0.0.1:8791 node bench/ocr-online/results-2026-11-18-rtl-fix/privacy_network.js
// Ad, consent and analytics scripts are blocked (route.abort) as in run.js; they are listed as blocked.
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const SITE = process.env.SITE || 'http://127.0.0.1:8791';
const REPO = path.resolve(__dirname, '..', '..', '..');
const BLOCK = /(gatekeeperconsent|ezojs|ezoic|googletagmanager|google-analytics|doubleclick|googlesyndication|adsbygoogle|open\.video)/;
const IMG1 = 'receipt/receipt01_dejavu-mono.png', IMG2 = 'clean/austen_dejavu-serif_300.png';
async function ocr(page, img) {
  await page.setInputFiles('#file-input', path.join(REPO, 'corpus', img));
  await page.waitForSelector('#extract-btn:not([disabled])');
  await page.click('#extract-btn');
  await page.waitForFunction(() => !document.getElementById('result-stats').hidden || /error/.test(document.getElementById('tool-message').className), null, { timeout: 300000 });
  return page.evaluate(() => ({ chars: document.getElementById('output-text').value.length,
    message: document.getElementById('tool-message').hidden ? '' : document.getElementById('tool-message').textContent,
    confidence: document.getElementById('confidence-badge').textContent }));
}
(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const blocked = new Set();
  await ctx.route('**/*', (r) => { const u = r.request().url(); if (BLOCK.test(u)) { blocked.add(new URL(u).host); return r.abort(); } return r.continue(); });
  const page = await ctx.newPage();
  await page.goto(SITE + '/ocr-online/', { waitUntil: 'load' });
  const log = [];
  let phase = 'ocr-online';
  page.on('request', (req) => {
    if (BLOCK.test(req.url())) return;
    const u = new URL(req.url());
    const body = req.postDataBuffer();
    log.push({ phase, method: req.method(), host: u.host, path: u.pathname, type: req.resourceType(), body_bytes: body ? body.length : 0 });
  });
  const fileBytes = fs.statSync(path.join(REPO, 'corpus', IMG1)).size;
  const first = await ocr(page, IMG1);
  await ctx.setOffline(true);
  phase = 'offline';
  await page.click('#clear-btn');
  const second = await ocr(page, IMG2);
  await browser.close();
  const out = {
    date_utc: new Date().toISOString(), site: SITE, page: '/ocr-online/', chromium: browser.version(),
    playwright: require('playwright/package.json').version, blocked_third_party_hosts: [...blocked].sort(),
    image: IMG1, image_bytes: fileBytes, first_run: first,
    requests_during_ocr: log.filter((r) => r.phase === 'ocr-online'),
    requests_with_body: log.filter((r) => r.body_bytes > 0).length,
    non_get_requests: log.filter((r) => r.method !== 'GET').length,
    offline_second_image: IMG2, offline_second_run: second, requests_while_offline: log.filter((r) => r.phase === 'offline'),
  };
  fs.writeFileSync(path.join(__dirname, 'privacy_network.json'), JSON.stringify(out, null, 1) + '\n');
  console.log(JSON.stringify(out, null, 1));
})();
