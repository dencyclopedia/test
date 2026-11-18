// tesseract.js harness (Node). Common protocol (see ../README.md):
//   node harness.js TESSDATA|default LANG PSM PASSES TINY IMG...
// TESSDATA=default -> tesseract.js downloads its own model from the jsDelivr CDN (what most users get).
const { createWorker } = require('tesseract.js');
const fs = require('fs');
const os = require('os');
const path = require('path');

(async () => {
  const [td, lang, psm, passesS, tiny, ...imgs] = process.argv.slice(2);
  const passes = parseInt(passesS, 10);
  const opts = { cachePath: fs.mkdtempSync(path.join(os.tmpdir(), 'tjs-')) };
  if (td !== 'default') { opts.langPath = td; opts.gzip = false; }
  const t0 = performance.now();
  const worker = await createWorker(lang, 1, opts);
  if (psm !== 'default') await worker.setParameters({ tessedit_pageseg_mode: psm });
  const init = (performance.now() - t0) / 1000;
  const ocr = async (p) => (await worker.recognize(p)).data.text;
  await ocr(tiny);
  const tinyS = [];
  for (let i = 0; i < 20; i++) { const t = performance.now(); await ocr(tiny); tinyS.push((performance.now() - t) / 1000); }
  const texts = [];
  for (const p of imgs) texts.push(await ocr(p));
  const passS = [];
  for (let k = 0; k < passes; k++) {
    const row = [];
    for (const p of imgs) { const t = performance.now(); await ocr(p); row.push((performance.now() - t) / 1000); }
    passS.push(row);
  }
  const pkg = require('tesseract.js/package.json');
  const core = require('tesseract.js-core/package.json');
  const cached = fs.readdirSync(opts.cachePath);
  console.log(JSON.stringify({
    binding: td === 'default' ? 'tesseract.js (CDN model)' : 'tesseract.js (local model)',
    info: { 'tesseract.js': pkg.version, 'tesseract.js-core': core.version, oem: 1,
            model: td === 'default' ? `@tesseract.js-data/${lang}/4.0.0_best_int (jsDelivr)` : td,
            cache_files: cached },
    init_s: init, tiny_s: tinyS, pass_s: passS, texts }));
  await worker.terminate();
})();
