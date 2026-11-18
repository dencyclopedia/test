#!/usr/bin/env node
// Line and word confidences that tesseract.js 5.1.1 returns for the Arabic test page, with
// preserve_interword_spaces 0 and 1 (PSM 3, ara 4.0.0_best_int). Explains the two Arabic bugs of the tool.
// Usage: SITE=http://127.0.0.1:8791 node bench/ocr-online/results-2026-11-18-rtl-fix/ara_lines.js
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const SITE = process.env.SITE || 'http://127.0.0.1:8791';
const REPO = path.resolve(__dirname, '..', '..', '..');
const IMG = 'multilingual/ara_p1_noto-naskh-arabic.png';
(async () => {
  const b = await chromium.launch(); const ctx = await b.newContext();
  await ctx.route('**/*', (r) => (/gatekeeper|ezoic|ezojs|googletag|open\.video/.test(r.request().url()) ? r.abort() : r.continue()));
  await ctx.route('**/__corpus/**', (r) => r.fulfill({ body: fs.readFileSync(path.join(REPO, 'corpus', IMG)), contentType: 'image/png' }));
  const p = await ctx.newPage();
  await p.goto(SITE + '/ocr-online/');
  await p.addScriptTag({ url: 'https://cdn.jsdelivr.net/npm/tesseract.js@5.1.1/dist/tesseract.min.js' });
  const runs = await p.evaluate(async () => {
    const w = await Tesseract.createWorker('ara', 1);
    const res = [];
    for (const pis of ['0', '1']) {
      await w.setParameters({ tessedit_pageseg_mode: '3', preserve_interword_spaces: pis });
      const r = await w.recognize('/__corpus/x.png', {}, { text: true, blocks: true });
      const lines = [];
      r.data.blocks.forEach((bl) => bl.paragraphs.forEach((pp) => pp.lines.forEach((l) => lines.push({
        line_confidence: +l.confidence.toFixed(2), word_confidences: l.words.map((x) => +x.confidence.toFixed(2)), text: l.text.trim() }))));
      res.push({ preserve_interword_spaces: pis, page_confidence: r.data.confidence, lines });
    }
    await w.terminate();
    return res;
  });
  await b.close();
  fs.writeFileSync(path.join(__dirname, 'ara_lines.json'), JSON.stringify({ image: IMG, tesseract_js: '5.1.1', runs }, null, 1) + '\n');
  console.log(runs.map((r) => r.preserve_interword_spaces + ': ' + r.lines.map((l) => Math.round(l.line_confidence)).join(',')).join('\n'));
})();
