// Cookies, storage and network requests of the live tesseractocr.org, captured with Playwright Chromium.
// usage: node bench/privacy/capture.js <outdir>     (HTTPS_PROXY is used when set)
// Two passes in fresh profiles: (1) no consent answer, (2) after clicking the consent banner's accept button.
const { chromium } = require('playwright');
const fs = require('fs');
const out = process.argv[2] || 'bench/privacy/results';
const PAGES = ['https://tesseractocr.org/', 'https://tesseractocr.org/install/', 'https://tesseractocr.org/privacy/'];
(async () => {
  const opts = process.env.HTTPS_PROXY ? { proxy: { server: process.env.HTTPS_PROXY } } : {};
  const b = await chromium.launch(opts);
  const meta = { date_utc: new Date().toISOString(), browser: 'Chromium ' + b.version(), viewport: '1440x900', locale: 'en-US', pages: PAGES, ua: null };
  for (const pass of ['no-consent', 'accept']) {
    const ctx = await b.newContext({ viewport: { width: 1440, height: 900 }, locale: 'en-US' });
    const reqs = [];
    ctx.on('request', r => reqs.push({ page: null, url: r.url(), type: r.resourceType(), method: r.method() }));
    const p = await ctx.newPage();
    meta.ua = await p.evaluate(() => navigator.userAgent);
    let accepted = null;
    for (const u of PAGES) {
      const start = reqs.length;
      await p.goto(u, { waitUntil: 'load', timeout: 60000 }).catch(e => reqs.push({ page: u, url: 'ERROR ' + e.message, type: 'error' }));
      await p.waitForTimeout(6000);
      if (pass === 'accept' && accepted === null) {
        accepted = false;
        for (const f of p.frames()) {
          for (const sel of ['button:has-text("Accept")', 'button:has-text("Agree")', 'button:has-text("Consent")', '#ez-accept-all', '.fc-cta-consent']) {
            const el = await f.$(sel).catch(() => null);
            if (el && await el.isVisible().catch(() => false)) { await el.click().catch(() => {}); accepted = sel + ' in ' + (f.url() || 'main'); break; }
          }
          if (accepted) break;
        }
        await p.waitForTimeout(6000);
      }
      for (let y = 0; y < 6000; y += 600) { await p.mouse.wheel(0, 600); await p.waitForTimeout(250); }
      await p.waitForTimeout(4000);
      for (let i = start; i < reqs.length; i++) if (!reqs[i].page) reqs[i].page = u;
    }
    const cookies = await ctx.cookies();
    const storage = await p.evaluate(() => ({ localStorage: Object.keys(localStorage), sessionStorage: Object.keys(sessionStorage) }));
    fs.writeFileSync(`${out}/${pass}-requests.json`, JSON.stringify(reqs, null, 1));
    fs.writeFileSync(`${out}/${pass}-cookies.json`, JSON.stringify(cookies.map(c => ({ name: c.name, domain: c.domain, path: c.path, expires: c.expires, httpOnly: c.httpOnly, secure: c.secure, sameSite: c.sameSite })), null, 1));
    fs.writeFileSync(`${out}/${pass}-storage.json`, JSON.stringify(storage, null, 1));
    meta[pass] = { requests: reqs.length, cookies: cookies.length, accepted };
    await ctx.close();
  }
  fs.writeFileSync(`${out}/meta.json`, JSON.stringify(meta, null, 1));
  console.log(JSON.stringify(meta));
  await b.close();
})();
