#!/usr/bin/env node
// Raw captures for /ocr-online/ figures: the site's own tool (EN page) driven by Playwright/Chromium.
//  1. sideways test page -> result with the word-box overlay (tool section, 1440 px viewport, light theme)
//  2. Arabic test page -> output text with the tool before the RTL fix (ocr-tool.js at site commit 7a7a8fc,
//     saved as raw/ocr-online/ocr-tool.before-rtl-fix.js) and after it (the site's current assets/ocr-tool.js)
// Usage: (cd <site> && python3 -m http.server 8791 --bind 127.0.0.1) &  SITE=http://127.0.0.1:8791 node tools/images/figures/ocr_online_capture.js
// Ad/consent/analytics/video scripts are blocked; pixels are saved untouched to tools/images/raw/ocr-online/.
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');
const SITE = process.env.SITE || 'http://127.0.0.1:8791';
const REPO = path.resolve(__dirname, '..', '..', '..');
const RAW = path.join(REPO, 'tools', 'images', 'raw', 'ocr-online');
const BLOCK = /(gatekeeperconsent|ezojs|ezoic|googletagmanager|google-analytics|open\.video)/;
async function run(ctx, img, lang, beforeFix) {
  const page = await ctx.newPage();
  if (beforeFix) await page.route('**/assets/ocr-tool.js*', (r) => r.fulfill({ body: fs.readFileSync(path.join(RAW, 'ocr-tool.before-rtl-fix.js')), contentType: 'application/javascript' }));
  await page.goto(SITE + '/ocr-online/', { waitUntil: 'load' });
  await page.selectOption('#language-select', lang);
  await page.setInputFiles('#file-input', path.join(REPO, 'corpus', img));
  await page.click('#extract-btn');
  await page.waitForFunction(() => !document.getElementById('result-stats').hidden, null, { timeout: 300000 });
  await page.waitForTimeout(300);
  return page;
}
(async () => {
  const b = await chromium.launch();
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 }, colorScheme: 'light', deviceScaleFactor: 2 });
  await ctx.route('**/*', (r) => (BLOCK.test(r.request().url()) ? r.abort() : r.continue()));
  let p = await run(ctx, 'layout/rotated90_doyle_caladea.png', 'eng', false);
  await p.addStyleTag({ content: '.nav{display:none!important}' });
  await p.locator('#ocr-tool').screenshot({ path: path.join(RAW, 'tool-sideways-page-word-boxes.png') });
  await p.close();
  for (const [tag, before] of [['before', true], ['after', false]]) {
    p = await run(ctx, 'multilingual/ara_p1_noto-naskh-arabic.png', 'ara', before);
    await p.addStyleTag({ content: '#output-text{height:560px!important}.nav{display:none!important}' });
    await p.locator('.output-card').screenshot({ path: path.join(RAW, `arabic-output-${tag}-rtl-fix.png`) });
    fs.writeFileSync(path.join(RAW, `arabic-output-${tag}-rtl-fix.txt`), await p.$eval('#output-text', (e) => e.value));
    await p.close();
  }
  await b.close();
})();
