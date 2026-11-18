#!/usr/bin/env node
// Capture the 'screenshot' set: real Chromium screenshots (Playwright) of small local HTML UIs written
// for this corpus, in light and dark mode, at device scale factor 1 and 2.
// Ground truth = document.body.innerText of the rendered page (only visible text is used: no
// placeholders, no icons, no CSS-generated content, no hidden elements, no text-transform).
// Usage: node corpus/gen/screenshots.js     (then re-run build_corpus.py to add them to the manifest)
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const CORPUS = path.resolve(__dirname, '..');
const OUT = path.join(CORPUS, 'screenshot');

const css = `
:root{--bg:#ffffff;--panel:#f4f5f7;--fg:#1d2330;--muted:#5b6475;--line:#d9dde4;--accent:#2457c5;--accentfg:#fff}
@media (prefers-color-scheme: dark){:root{--bg:#15181e;--panel:#1f232b;--fg:#e6e9ef;--muted:#9aa3b2;--line:#323844;--accent:#6c9cff;--accentfg:#0d1117}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.5 Inter, sans-serif}
header{padding:14px 24px;border-bottom:1px solid var(--line);font-weight:600;font-size:16px}
.wrap{display:flex}
nav{width:200px;padding:16px;background:var(--panel);border-right:1px solid var(--line)}
nav div{padding:6px 8px;color:var(--muted)}
nav div.on{color:var(--fg);font-weight:600}
main{flex:1;padding:20px 28px;max-width:760px}
h1{font-size:20px;margin:0 0 12px}
h2{font-size:15px;margin:18px 0 6px}
p{margin:4px 0;color:var(--muted)}
.row{display:flex;justify-content:space-between;align-items:center;padding:10px 0;border-bottom:1px solid var(--line)}
.btn{display:inline-block;padding:7px 14px;border-radius:6px;background:var(--accent);color:var(--accentfg);font-weight:600;margin-right:8px}
.btn.alt{background:var(--panel);color:var(--fg);border:1px solid var(--line)}
table{border-collapse:collapse;width:100%}
td,th{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line)}
th{color:var(--muted);font-weight:600}
.cards{display:flex;gap:14px;margin-bottom:18px}
.card{flex:1;padding:14px;border:1px solid var(--line);border-radius:8px;background:var(--panel)}
.card b{display:block;font-size:22px}
.msg{margin:10px 0;padding:10px 12px;border-radius:8px;background:var(--panel);max-width:560px}
.msg .who{font-weight:600}
.msg .when{color:var(--muted);font-size:12px}
.term{font:13px/1.55 'JetBrains Mono', monospace;background:var(--panel);padding:16px 20px;margin:20px;border-radius:8px;white-space:pre}
`;

const pages = {
  settings: `<header>Acme Notes</header><div class="wrap"><nav><div>General</div><div class="on">Notifications</div><div>Account</div><div>Privacy</div><div>Billing</div></nav>
<main><h1>Notification settings</h1><p>Choose how and when you want to be notified.</p>
<div class="row"><div><b>Email digest</b><p>A summary of activity, sent every Monday at 9:00.</p></div><div>On</div></div>
<div class="row"><div><b>Mentions</b><p>Notify me when someone mentions me in a note.</p></div><div>On</div></div>
<div class="row"><div><b>Shared folders</b><p>Notify me when a shared folder changes.</p></div><div>Off</div></div>
<div class="row"><div><b>Quiet hours</b><p>From 22:00 to 07:30 in your local time zone.</p></div><div>Edit</div></div>
<p style="margin-top:18px"><span class="btn">Save changes</span><span class="btn alt">Cancel</span></p></main></div>`,
  dashboard: `<header>Store overview - November 2026</header><main style="max-width:none"><div class="cards">
<div class="card">Orders<b>1,284</b>+6.2% vs October</div><div class="card">Returns<b>37</b>2.9% of orders</div>
<div class="card">Average basket<b>$48.60</b>-1.4% vs October</div></div>
<h2>Recent orders</h2><table><tr><th>Order</th><th>Customer</th><th>Date</th><th>Status</th><th>Total</th></tr>
<tr><td>#10482</td><td>Sample Customer A</td><td>2026-11-17</td><td>Shipped</td><td>$129.00</td></tr>
<tr><td>#10481</td><td>Sample Customer B</td><td>2026-11-17</td><td>Processing</td><td>$54.25</td></tr>
<tr><td>#10480</td><td>Sample Customer C</td><td>2026-11-16</td><td>Refunded</td><td>$18.99</td></tr>
<tr><td>#10479</td><td>Sample Customer D</td><td>2026-11-16</td><td>Shipped</td><td>$302.40</td></tr></table></main>`,
  chat: `<header>#release-planning</header><main>
<div class="msg"><div class="who">Dana <span class="when">09:12</span></div>Build 5.5.4 passed all tests on Linux and macOS.</div>
<div class="msg"><div class="who">Priya <span class="when">09:15</span></div>Windows is still running. I will post the results here.</div>
<div class="msg"><div class="who">Marco <span class="when">09:31</span></div>Can we freeze the docs by Thursday? The changelog needs two more entries.</div>
<div class="msg"><div class="who">Dana <span class="when">09:33</span></div>Yes. Thursday 17:00 works for me.</div></main>`,
  inbox: `<header>Inbox (3 unread)</header><main style="max-width:900px"><table>
<tr><td><b>Billing Team</b></td><td>Your invoice INV-2026-0418 is ready</td><td>Nov 17</td></tr>
<tr><td><b>Alex Morgan</b></td><td>Re: quarterly report draft, comments inside</td><td>Nov 16</td></tr>
<tr><td>Travel Desk</td><td>Booking confirmed: Lisbon, 3 to 6 December</td><td>Nov 15</td></tr>
<tr><td>Security Notice</td><td>New sign-in from Firefox on Windows</td><td>Nov 14</td></tr>
<tr><td><b>Sam Lee</b></td><td>Lunch on Friday?</td><td>Nov 12</td></tr></table></main>`,
  terminal: `<div class="term">$ tesseract --version
tesseract 5.5.4
 leptonica-1.82.0
$ tesseract page.png out -l eng --psm 3
Estimating resolution as 300
$ wc -w out.txt
212 out.txt
$ ls -l *.png
-rw-r--r-- 1 user user 482113 Nov 18 09:42 page.png
-rw-r--r-- 1 user user  91024 Nov 18 09:44 receipt.png</div>`,
};

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch();
  const entries = [];
  for (const [name, body] of Object.entries(pages)) {
    for (const scheme of ['light', 'dark']) {
      for (const dsf of [1, 2]) {
        const ctx = await browser.newContext({ viewport: { width: 1000, height: 600 }, deviceScaleFactor: dsf, colorScheme: scheme });
        const page = await ctx.newPage();
        await page.setContent(`<!doctype html><html><head><meta charset="utf-8"><style>${css}</style></head><body>${body}</body></html>`);
        await page.evaluate(() => document.fonts.ready);
        const text = await page.evaluate(() => document.body.innerText);
        const id = `screenshot/${name}_${scheme}_${dsf}x`;
        await page.screenshot({ path: path.join(CORPUS, id + '.png'), fullPage: true });
        fs.writeFileSync(path.join(CORPUS, id + '.gt.txt'), text.trim() + '\n');
        const size = await page.evaluate(() => [document.documentElement.scrollWidth, document.documentElement.scrollHeight]);
        entries.push({
          id, image: id + '.png', gt: id + '.gt.txt', width: size[0] * dsf, height: size[1] * dsf, dpi: null,
          set: 'screenshot', subset: name, lang: 'eng', theme: scheme, device_scale_factor: dsf,
          source: 'local HTML written for this corpus (corpus/gen/screenshots.js)', font: name === 'terminal' ? 'JetBrains Mono' : 'Inter',
          css_px_font_size: name === 'terminal' ? 13 : 14, degradation: null, synthetic: true,
          capture: `Playwright ${require('playwright/package.json').version} Chromium ${browser.version()}`,
          note: 'real browser screenshot of a synthetic UI; ground truth = document.body.innerText',
        });
        await ctx.close();
      }
    }
  }
  await browser.close();
  fs.writeFileSync(path.join(__dirname, 'screenshots.json'), JSON.stringify(entries, null, 1) + '\n');
  console.log(entries.length, 'screenshots');
})();
