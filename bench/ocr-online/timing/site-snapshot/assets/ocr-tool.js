/*
 * Online OCR tool — shared by every /<locale>/ocr-online/ page.
 * Runs Tesseract (via tesseract.js / WebAssembly) entirely in the browser.
 * UI strings come from the page's <script type="application/json" id="ocr-i18n">.
 */
(function () {
    'use strict';

    var TESSERACT_JS = 'https://cdn.jsdelivr.net/npm/tesseract.js@5.1.1/dist/tesseract.min.js';
    var PDFJS = 'https://cdn.jsdelivr.net/npm/pdfjs-dist@4.10.38/build/pdf.min.mjs';
    var PDFJS_WORKER = 'https://cdn.jsdelivr.net/npm/pdfjs-dist@4.10.38/build/pdf.worker.min.mjs';
    var PDF_LIB = 'https://cdn.jsdelivr.net/npm/pdf-lib@1.17.1/dist/pdf-lib.min.js';

    var MAX_FILE_BYTES = 20 * 1024 * 1024;
    var MAX_PDF_PAGES = 20;
    var MIN_WIDTH = 1200;      // upscale small images: Tesseract wants ~300 DPI text
    var MAX_PIXELS = 16e6;     // downscale beyond this (iOS canvas limit) to keep memory and time sane
    var MAX_SIDE = 16000;      // tall phone screenshots stay full-width instead of shrinking
    var PDF_RENDER_WIDTH = 2000;
    var ROTATE_BELOW_CONF = 50; // a low-confidence result may be a sideways or upside-down page
    var PROBE_SIDE = 1600;      // rotation checks run on a smaller copy
    // Right-to-left scripts: preserve_interword_spaces=1 glues their words together (measured on
    // Arabic, in the browser and with native Tesseract 5.5.4), so it stays off for them.
    var RTL_LANG = /^(ara|fas|heb|urd|yid|pus|snd|uig|syr|div)$/;

    document.addEventListener('DOMContentLoaded', function () {
        var root = document.getElementById('ocr-tool');
        if (!root) return;

        var t = {};
        try { t = JSON.parse(document.getElementById('ocr-i18n').textContent); } catch (e) { /* fall back to keys */ }
        function msg(key, vars) {
            var s = t[key] || key;
            if (vars) Object.keys(vars).forEach(function (k) { s = s.split('{' + k + '}').join(vars[k]); });
            return s;
        }

        var $ = function (id) { return document.getElementById(id); };
        var dropzone = $('dropzone'), fileInput = $('file-input'), browseBtn = $('browse-btn');
        var prompt = $('dropzone-prompt'), previewBox = $('preview-container'), preview = $('image-preview');
        var fileMeta = $('file-meta'), clearBtn = $('clear-btn'), extractBtn = $('extract-btn');
        var langSelect = $('language-select'), lang2Select = $('language2-select'), modeSelect = $('ocr-mode-select');
        var enhanceBox = $('enhance-checkbox');
        var progressBox = $('progress-container'), statusText = $('status-text');
        var progressPct = $('progress-percent'), progressFill = $('progress-bar-fill'), toolMsg = $('tool-message');
        var output = $('output-text'), stats = $('result-stats'), wordsBadge = $('word-count-badge'), confBadge = $('confidence-badge');
        // Optional word-box overlay: only pages that include #ocr-boxes (the English page) get it.
        var boxes = $('ocr-boxes'), boxesToggle = $('ocr-boxes-toggle'), boxesLegend = $('ocr-boxes-legend');
        var cleanBtn = $('clean-text-btn'), copyBtn = $('copy-btn'), txtBtn = $('download-txt-btn'), pdfBtn = $('export-pdf-btn');

        // Arabic, Hebrew etc. results read right to left; dir=auto follows the first strong character.
        if (output && !output.getAttribute('dir')) output.setAttribute('dir', 'auto');

        var state = { file: null, previewUrl: null, pdfPages: null, worker: null, workerLangs: null, busy: false };

        // ---------- helpers ----------
        function loadScript(src) {
            return new Promise(function (resolve, reject) {
                var existing = document.querySelector('script[src="' + src + '"]');
                if (existing && existing.dataset.loaded) return resolve();
                var s = existing || document.createElement('script');
                s.addEventListener('load', function () { s.dataset.loaded = '1'; resolve(); });
                s.addEventListener('error', function () { reject(new Error('Failed to load ' + src)); });
                if (!existing) { s.src = src; s.async = true; document.head.appendChild(s); }
            });
        }
        function show(el, on) { if (el) el.hidden = !on; }
        function notify(text, kind) {
            toolMsg.textContent = text || '';
            toolMsg.className = 'tool-message' + (kind ? ' is-' + kind : '');
            show(toolMsg, !!text);
        }
        function setProgress(label, pct) {
            show(progressBox, true);
            statusText.textContent = label;
            var p = Math.max(0, Math.min(100, Math.round(pct || 0)));
            progressPct.textContent = p + '%';
            progressFill.style.width = p + '%';
        }
        function setOutputButtons(on) {
            [cleanBtn, copyBtn, txtBtn].forEach(function (b) { b.disabled = !on; });
            pdfBtn.disabled = !(on && state.pdfPages && state.pdfPages.length);
        }
        function countWords(text) {
            var s = text.trim();
            if (!s) return 0;
            // CJK / Thai have no spaces: count each ideograph or kana as a word-like unit.
            var cjk = (s.match(/[぀-ヿ㐀-鿿가-힯฀-๿]/g) || []).length;
            var rest = s.replace(/[぀-ヿ㐀-鿿가-힯฀-๿]/g, ' ').split(/\s+/).filter(Boolean).length;
            return cjk + rest;
        }
        function isRtl(langs) { return langs.split('+').some(function (l) { return RTL_LANG.test(l); }); }
        function selectedLangs() {
            var l = langSelect.value;
            var l2 = lang2Select ? lang2Select.value : '';
            return l2 && l2 !== l ? l + '+' + l2 : l;
        }
        function download(blob, name) {
            var url = URL.createObjectURL(blob);
            var a = document.createElement('a');
            a.href = url; a.download = name;
            document.body.appendChild(a); a.click(); a.remove();
            setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
        }
        function stamp() { return new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-'); }

        // ---------- file intake ----------
        function showBoxes(on) {
            show(boxes, on);
            preview.style.visibility = on ? 'hidden' : '';
        }
        function hideBoxes() {
            if (!boxes) return;
            showBoxes(false); show(boxesLegend, false);
            boxes.width = boxes.height = 0;
        }
        function resetResult() {
            hideBoxes();
            output.value = '';
            show(stats, false);
            state.pdfPages = null;
            setOutputButtons(false);
        }
        function clearAll() {
            if (state.previewUrl) URL.revokeObjectURL(state.previewUrl);
            state.file = null; state.previewUrl = null;
            preview.removeAttribute('src');
            fileMeta.textContent = '';
            show(previewBox, false); show(prompt, true); show(clearBtn, false);
            extractBtn.disabled = true;
            fileInput.value = '';
            notify('');
            resetResult();
        }
        function isPdf(file) { return file.type === 'application/pdf' || /\.pdf$/i.test(file.name || ''); }

        function handleFile(file) {
            if (!file) return;
            if (state.busy) return;
            var okImage = /^image\/(png|jpe?g|webp|bmp|gif)$/i.test(file.type);
            if (!okImage && !isPdf(file)) { notify(msg('errType'), 'error'); return; }
            if (file.size > MAX_FILE_BYTES) { notify(msg('errSize'), 'error'); return; }
            clearAll();
            state.file = file;
            loadScript(TESSERACT_JS).catch(function () {}); // warm up while the user picks options
            if (isPdf(file)) {
                fileMeta.textContent = '📄 ' + (file.name || 'document.pdf');
                show(preview, false);
            } else {
                state.previewUrl = URL.createObjectURL(file);
                preview.src = state.previewUrl;
                show(preview, true);
                fileMeta.textContent = file.name || '';
            }
            show(prompt, false); show(previewBox, true); show(clearBtn, true);
            extractBtn.disabled = false;
        }

        ['dragenter', 'dragover'].forEach(function (ev) {
            dropzone.addEventListener(ev, function (e) { e.preventDefault(); dropzone.classList.add('drag-over'); });
        });
        ['dragleave', 'drop'].forEach(function (ev) {
            dropzone.addEventListener(ev, function (e) { e.preventDefault(); dropzone.classList.remove('drag-over'); });
        });
        dropzone.addEventListener('drop', function (e) {
            if (e.dataTransfer && e.dataTransfer.files.length) handleFile(e.dataTransfer.files[0]);
        });
        dropzone.addEventListener('click', function (e) {
            if (state.file || e.target.closest('button')) return;
            fileInput.click();
        });
        dropzone.addEventListener('keydown', function (e) {
            if ((e.key === 'Enter' || e.key === ' ') && !state.file) { e.preventDefault(); fileInput.click(); }
        });
        browseBtn.addEventListener('click', function (e) { e.stopPropagation(); fileInput.click(); });
        fileInput.addEventListener('change', function () { if (fileInput.files.length) handleFile(fileInput.files[0]); });
        clearBtn.addEventListener('click', clearAll);

        // Paste a screenshot straight from the clipboard (Ctrl+V / Cmd+V).
        window.addEventListener('paste', function (e) {
            var items = (e.clipboardData && e.clipboardData.items) || [];
            for (var i = 0; i < items.length; i++) {
                if (items[i].kind === 'file') {
                    var f = items[i].getAsFile();
                    if (f && (/^image\//.test(f.type) || isPdf(f))) {
                        e.preventDefault();
                        handleFile(new File([f], f.name || 'pasted-image.png', { type: f.type }));
                        return;
                    }
                }
            }
        });

        // Built-in English sample images, drawn on a canvas.
        document.querySelectorAll('.sample-btn').forEach(function (btn) {
            btn.addEventListener('click', function () {
                var kind = btn.getAttribute('data-sample');
                var c = document.createElement('canvas');
                c.width = 1200; c.height = 600;
                var ctx = c.getContext('2d');
                ctx.fillStyle = '#ffffff'; ctx.fillRect(0, 0, c.width, c.height);
                ctx.fillStyle = '#111111';
                ctx.scale(2, 2);
                if (kind === 'receipt') {
                    ctx.font = 'bold 24px Arial, sans-serif'; ctx.fillText('TESSERACT STORE INVOICE', 40, 50);
                    ctx.font = '18px "Courier New", monospace';
                    ctx.fillText('Item 1: Open Source OCR Library  $0.00', 40, 100);
                    ctx.fillText('Item 2: WebAssembly Engine       $0.00', 40, 130);
                    ctx.fillText('TOTAL AMOUNT DUE:                $0.00', 40, 180);
                    ctx.fillText('Thank you for using Tesseract OCR!', 40, 230);
                } else if (kind === 'book') {
                    ctx.font = 'bold 24px Georgia, serif'; ctx.fillText('CHAPTER 1: Reading Machines', 40, 50);
                    ctx.font = '18px Georgia, serif';
                    ctx.fillText('Optical Character Recognition (OCR) lets computers', 40, 100);
                    ctx.fillText('read printed text inside digital images automatically.', 40, 130);
                    ctx.fillText('Tesseract uses LSTM neural networks to recognize', 40, 160);
                    ctx.fillText('text in more than 100 languages.', 40, 190);
                } else {
                    ctx.font = 'bold 40px Arial, sans-serif'; ctx.fillText('SPEED LIMIT', 175, 100);
                    ctx.font = 'bold 80px Arial, sans-serif'; ctx.fillText('65', 250, 200);
                }
                // The samples are English text, so recognise them with the English model.
                langSelect.value = 'eng';
                if (lang2Select) lang2Select.value = '';
                c.toBlob(function (blob) { handleFile(new File([blob], 'sample-' + kind + '.png', { type: 'image/png' })); });
            });
        });

        // ---------- image preparation ----------
        function fileToImage(file) {
            return new Promise(function (resolve, reject) {
                var url = URL.createObjectURL(file);
                var img = new Image();
                img.onload = function () { URL.revokeObjectURL(url); resolve(img); };
                img.onerror = function () { URL.revokeObjectURL(url); reject(new Error(msg('errDecode'))); };
                img.src = url;
            });
        }
        // Transparent images: light text on a transparent background would vanish on white,
        // so flatten onto black when the opaque pixels are mostly light.
        function matteFor(source, w, h) {
            var s = Math.min(1, 256 / Math.max(w, h));
            var c = document.createElement('canvas');
            c.width = Math.max(1, Math.round(w * s)); c.height = Math.max(1, Math.round(h * s));
            var ctx = c.getContext('2d');
            ctx.drawImage(source, 0, 0, c.width, c.height);
            var d = ctx.getImageData(0, 0, c.width, c.height).data, clear = 0, sum = 0, n = 0;
            for (var i = 0; i < d.length; i += 4) {
                if (d[i + 3] < 250) clear++;
                if (d[i + 3] > 128) { sum += 0.299 * d[i] + 0.587 * d[i + 1] + 0.114 * d[i + 2]; n++; }
            }
            return clear > d.length / 40 && n && sum / n > 160 ? '#000000' : '#ffffff';
        }
        function toGray(d) {
            var g = new Uint8ClampedArray(d.length / 4);
            for (var i = 0, j = 0; i < d.length; i += 4, j++) g[j] = 0.299 * d[i] + 0.587 * d[i + 1] + 0.114 * d[i + 2];
            return g;
        }
        // Estimate the paper brightness in a coarse grid (max of each block, then the max of its
        // 3x3 neighbourhood so bold strokes do not count as background).
        function backgroundGrid(g, w, h) {
            var B = Math.max(16, Math.round(Math.min(w, h) / 40));
            var gw = Math.ceil(w / B), gh = Math.ceil(h / B), blk = new Float32Array(gw * gh), bg = new Float32Array(gw * gh);
            var sum = new Float64Array(gw * gh), cnt = new Uint32Array(gw * gh), darkCells = 0;
            for (var y = 0; y < h; y++) {
                var row = y * w, brow = ((y / B) | 0) * gw;
                for (var x = 0; x < w; x++) {
                    var v = g[row + x], k = brow + ((x / B) | 0);
                    if (v > blk[k]) blk[k] = v;
                    sum[k] += v; cnt[k]++;
                }
            }
            for (var k2 = 0; k2 < sum.length; k2++) if (sum[k2] / cnt[k2] < 90) darkCells++;
            for (var by = 0; by < gh; by++) for (var bx = 0; bx < gw; bx++) {
                var m = 0;
                for (var dy = -1; dy <= 1; dy++) for (var dx = -1; dx <= 1; dx++) {
                    var yy = by + dy, xx = bx + dx;
                    if (yy >= 0 && yy < gh && xx >= 0 && xx < gw && blk[yy * gw + xx] > m) m = blk[yy * gw + xx];
                }
                bg[by * gw + bx] = Math.max(m, 1);
            }
            return { B: B, gw: gw, gh: gh, bg: bg, darkShare: darkCells / sum.length };
        }
        // Divide by the (bilinearly interpolated) background: removes shadows and uneven light.
        // Shadows change gradually, so cells next to an abrupt jump (dark UI panels, a table behind
        // the page) and very dark cells are left as they are instead of being blown out to white.
        function flattenLighting(g, w, h, grid, paper) {
            var B = grid.B, gw = grid.gw, gh = grid.gh, bg = grid.bg, n = gw * gh, k, x, y;
            var amt = new Float32Array(n), edge = new Uint8Array(n);
            for (k = 0; k < n; k++) {
                x = k % gw;
                if ((x + 1 < gw && Math.abs(bg[k] - bg[k + 1]) > paper * 0.3) || (k + gw < n && Math.abs(bg[k] - bg[k + gw]) > paper * 0.3)) {
                    edge[k] = 1;
                    if (x + 1 < gw) edge[k + 1] = 1;
                    if (k + gw < n) edge[k + gw] = 1;
                }
            }
            for (k = 0; k < n; k++) {
                x = k % gw; y = (k / gw) | 0;
                var near = false;
                for (var dy = -1; dy <= 1 && !near; dy++) for (var dx = -1; dx <= 1; dx++) {
                    var yy = y + dy, xx = x + dx;
                    if (yy >= 0 && yy < gh && xx >= 0 && xx < gw && edge[yy * gw + xx]) { near = true; break; }
                }
                amt[k] = near ? 0 : Math.min(1, Math.max(0, (bg[k] - paper * 0.15) / (paper * 0.15)));
            }
            function lerp(a, y0, y1, x0, x1, ty, tx) {
                return (a[y0 * gw + x0] * (1 - tx) + a[y0 * gw + x1] * tx) * (1 - ty) + (a[y1 * gw + x0] * (1 - tx) + a[y1 * gw + x1] * tx) * ty;
            }
            for (y = 0; y < h; y++) {
                var fy = Math.min(Math.max((y + 0.5) / B - 0.5, 0), gh - 1), y0 = fy | 0, y1 = Math.min(y0 + 1, gh - 1), ty = fy - y0;
                for (x = 0; x < w; x++) {
                    var fx = Math.min(Math.max((x + 0.5) / B - 0.5, 0), gw - 1), x0 = fx | 0, x1 = Math.min(x0 + 1, gw - 1), tx = fx - x0;
                    var a = lerp(amt, y0, y1, x0, x1, ty, tx);
                    if (a <= 0) continue;
                    var v = g[y * w + x];
                    g[y * w + x] = v * (1 - a) + Math.min(255, v * 255 / lerp(bg, y0, y1, x0, x1, ty, tx)) * a;
                }
            }
        }
        // Remove salt-and-pepper specks: a pixel far darker or lighter than all but one of its
        // 8 neighbours (so specks in pairs go too) takes their average. Stroke pixels have
        // similar neighbours on both sides along the stroke, so they stay. Returns null unless
        // the image really is speckled (lone pixels with nothing similar within 2 px are common).
        function despeckle(g, w, h) {
            var out = new Uint8ClampedArray(g), lone = 0;
            for (var y = 2; y < h - 2; y++) for (var x = 2; x < w - 2; x++) {
                var o = y * w + x, v = g[o], mn = 255, mn2 = 255, mx = 0, mx2 = 0, sum = 0, dy, dx, q;
                for (dy = -w; dy <= w; dy += w) for (dx = -1; dx <= 1; dx++) {
                    if (!dy && !dx) continue;
                    q = g[o + dy + dx];
                    sum += q;
                    if (q < mn) { mn2 = mn; mn = q; } else if (q < mn2) mn2 = q;
                    if (q > mx) { mx2 = mx; mx = q; } else if (q > mx2) mx2 = q;
                }
                var isDark = v < mn2 - 48, isLight = v > mx2 + 48;
                if (!isDark && !isLight) continue;
                out[o] = sum / 8;
                var rmin = 255, rmax = 0;
                for (dy = -2; dy <= 2; dy++) for (dx = -2; dx <= 2; dx++) {
                    if (Math.max(Math.abs(dy), Math.abs(dx)) !== 2) continue;
                    q = g[o + dy * w + dx]; if (q < rmin) rmin = q; if (q > rmax) rmax = q;
                }
                if ((isDark && rmin > v + 48) || (isLight && rmax < v - 48)) lone++;
            }
            return lone > g.length * 0.003 ? out : null;
        }
        // Stretch so the 1st percentile becomes black and the 99th white.
        function stretch(g) {
            var hist = new Uint32Array(256), i;
            for (i = 0; i < g.length; i++) hist[g[i]]++;
            var lo = 0, hi = 255, acc = 0;
            for (i = 0; i < 256; i++) { acc += hist[i]; if (acc > g.length * 0.01) { lo = i; break; } }
            for (acc = 0, i = 255; i >= 0; i--) { acc += hist[i]; if (acc > g.length * 0.01) { hi = i; break; } }
            if (hi - lo < 8) return;
            for (i = 0; i < g.length; i++) g[i] = (g[i] - lo) * 255 / (hi - lo);
        }
        function grayToCanvas(g, ctx, w, h) {
            var data = ctx.createImageData(w, h), d = data.data;
            for (var i = 0; i < g.length; i++) { var j = i * 4; d[j] = d[j + 1] = d[j + 2] = g[i]; d[j + 3] = 255; }
            ctx.putImageData(data, 0, 0);
        }
        function prepareCanvas(source, w, h) {
            var scale = 1, enhance = enhanceBox && enhanceBox.checked, i;
            if (w < MIN_WIDTH) scale = MIN_WIDTH / w;
            if (w * h * scale * scale > MAX_PIXELS) scale = Math.sqrt(MAX_PIXELS / (w * h));
            if (Math.max(w, h) * scale > MAX_SIDE) scale = MAX_SIDE / Math.max(w, h);
            var matte = matteFor(source, w, h);
            // Strong upscaling means tiny text, whose dots and strokes are speck-sized: no despeckle then.
            var speckle = scale < 2, cleaned;
            if (speckle && scale > 1) {
                // Remove specks at the original size: upscaling would smear them into blobs.
                var n = document.createElement('canvas');
                n.width = w; n.height = h;
                var nctx = n.getContext('2d', { willReadFrequently: true });
                nctx.fillStyle = matte; nctx.fillRect(0, 0, w, h);
                nctx.drawImage(source, 0, 0, w, h);
                cleaned = despeckle(toGray(nctx.getImageData(0, 0, w, h).data), w, h);
                if (cleaned) { grayToCanvas(cleaned, nctx, w, h); source = n; matte = '#ffffff'; }
                cleaned = null;
            }
            var c = document.createElement('canvas');
            c.width = Math.max(1, Math.round(w * scale)); c.height = Math.max(1, Math.round(h * scale));
            var ctx = c.getContext('2d', { willReadFrequently: true });
            ctx.fillStyle = matte; ctx.fillRect(0, 0, c.width, c.height); // flatten transparency
            ctx.imageSmoothingEnabled = true; ctx.imageSmoothingQuality = 'high';
            ctx.drawImage(source, 0, 0, c.width, c.height);

            var g = toGray(ctx.getImageData(0, 0, c.width, c.height).data);
            if (speckle && scale <= 1 && (cleaned = despeckle(g, c.width, c.height))) g = cleaned;
            var sorted = g.length > 4e5 ? g.filter(function (v, k) { return k % 7 === 0; }) : g.slice();
            sorted.sort();
            var dark = sorted[sorted.length >> 1] < 110;  // light text on a dark background: invert it
            if (dark) for (i = 0; i < g.length; i++) g[i] = 255 - g[i];
            var grid = backgroundGrid(g, c.width, c.height), lo = 255, hi = 0;
            for (i = 0; i < grid.bg.length; i++) { if (grid.bg[i] < lo) lo = grid.bg[i]; if (grid.bg[i] > hi) hi = grid.bg[i]; }
            // Dark panels or bars inside a light page (app screenshots): their light text needs a second, inverted pass.
            c.hasDarkAreas = grid.darkShare >= 0.02;
            var uneven = hi - lo > 40;  // shadows or a lighting gradient across the page
            if (!enhance && !uneven && !dark && !cleaned) return c;  // clean scans and screenshots go in untouched
            if (uneven) flattenLighting(g, c.width, c.height, grid, hi);
            if (enhance) stretch(g);
            grayToCanvas(g, ctx, c.width, c.height);
            return c;
        }
        function rotateCanvas(src, quarterTurns, maxSide) {
            var sw = src.naturalWidth || src.width, sh = src.naturalHeight || src.height;
            var s = maxSide ? Math.min(1, maxSide / Math.max(sw, sh)) : 1;
            var w = Math.round(sw * s), h = Math.round(sh * s), odd = quarterTurns % 2;
            var c = document.createElement('canvas');
            c.width = odd ? h : w; c.height = odd ? w : h;
            var ctx = c.getContext('2d');
            ctx.translate(c.width / 2, c.height / 2);
            ctx.rotate(quarterTurns * Math.PI / 2);
            ctx.drawImage(src, -w / 2, -h / 2, w, h);
            return c;
        }
        // Calls onPage(canvas, n, total) for each page in turn, so only one page is in memory at a time.
        function forEachPdfPage(file, onRender, onPage) {
            return import(PDFJS).then(function (pdfjs) {
                pdfjs.GlobalWorkerOptions.workerSrc = PDFJS_WORKER;
                return file.arrayBuffer().then(function (buf) {
                    return pdfjs.getDocument({ data: buf, isEvalSupported: false }).promise;
                }).then(function (doc) {
                    var total = Math.min(doc.numPages, MAX_PDF_PAGES);
                    if (doc.numPages > MAX_PDF_PAGES) notify(msg('warnPages', { max: MAX_PDF_PAGES, total: doc.numPages }), 'warn');
                    var chain = Promise.resolve();
                    for (var n = 1; n <= total; n++) {
                        (function (n) {
                            chain = chain.then(function () {
                                onRender(n, total);
                                return doc.getPage(n).then(function (page) {
                                    var base = page.getViewport({ scale: 1 });
                                    var viewport = page.getViewport({ scale: PDF_RENDER_WIDTH / base.width });
                                    var c = document.createElement('canvas');
                                    c.width = Math.round(viewport.width); c.height = Math.round(viewport.height);
                                    var ctx = c.getContext('2d');
                                    ctx.fillStyle = '#ffffff'; ctx.fillRect(0, 0, c.width, c.height);
                                    return page.render({ canvasContext: ctx, viewport: viewport }).promise.then(function () {
                                        page.cleanup();
                                        var prepared = prepareCanvas(c, c.width, c.height);
                                        c.width = c.height = 0;
                                        return onPage(prepared, n, total);
                                    });
                                });
                            });
                        })(n);
                    }
                    return chain.then(function () { doc.destroy(); });
                });
            });
        }

        // ---------- OCR ----------
        var progressLabel = '';
        function getWorker(langs) {
            if (state.worker && state.workerLangs === langs) return Promise.resolve(state.worker);
            var old = state.worker;
            state.worker = null;
            return (old ? old.terminate() : Promise.resolve()).then(function () {
                return loadScript(TESSERACT_JS);
            }).then(function () {
                return window.Tesseract.createWorker(langs, 1, {
                    logger: function (m) {
                        if (m.status === 'recognizing text') setProgress(progressLabel || msg('recognizing'), m.progress * 100);
                        else if (m.status) setProgress(msg('loadingModel'), m.progress * 100);
                    }
                });
            }).then(function (w) { state.worker = w; state.workerLangs = langs; return w; });
        }

        extractBtn.addEventListener('click', function () {
            if (!state.file || state.busy) return;
            state.busy = true;
            extractBtn.disabled = true;
            resetResult();
            notify('');
            setProgress(msg('preparing'), 0);

            var langs = selectedLangs();
            var file = state.file;
            var texts = [], confs = [], pdfs = [];

            function recognize(worker, canvas, pdf, noRotate) {
                return worker.recognize(canvas, { pdfTitle: 'OCR - TesseractOCR.org', rotateAuto: !noRotate },
                    { text: true, blocks: true, hocr: false, tsv: false, pdf: pdf });
            }
            var hasText = function (s) { return /[\p{L}\p{N}]/u.test(s); };
            function paragraphs(res) {
                var out = [];
                (res.data.blocks || []).forEach(function (b) { b.paragraphs.forEach(function (p) { if (hasText(p.text)) out.push(p); }); });
                return out;
            }
            // Light text on dark bars and cards is skipped by Tesseract when the rest of the page is
            // light. Read it from an inverted copy with the text already found blacked out.
            function invertedPass(worker, canvas, res) {
                if (res.data.rotateRadians) return Promise.resolve([]);  // boxes would not line up
                var w = canvas.width, h = canvas.height, inv = document.createElement('canvas');
                inv.width = w; inv.height = h;
                var ctx = inv.getContext('2d', { willReadFrequently: true });
                ctx.drawImage(canvas, 0, 0);
                var data = ctx.getImageData(0, 0, w, h), d = data.data;
                for (var i = 0; i < d.length; i += 4) { d[i] = 255 - d[i]; d[i + 1] = 255 - d[i + 1]; d[i + 2] = 255 - d[i + 2]; }
                ctx.putImageData(data, 0, 0);
                ctx.fillStyle = '#000000';
                paragraphs(res).forEach(function (p) {
                    p.lines.forEach(function (l) {
                        var b = l.bbox;
                        if (hasText(l.text)) ctx.fillRect(b.x0 - 4, b.y0 - 4, b.x1 - b.x0 + 8, b.y1 - b.y0 + 8);
                    });
                });
                return recognize(worker, inv, false, true).then(function (res2) {
                    inv.width = inv.height = 0;
                    return paragraphs(res2).filter(function (p) { return p.confidence >= 60 && /[\p{L}\p{N}]{2}/u.test(p.text); });
                });
            }
            // Tesseract's line confidence can be as low as one doubtful word (an Arabic line read
            // correctly scored 27 because its first word did), so judge a line by its words' mean.
            function lineConf(l) {
                var w = (l.words || []).filter(function (x) { return hasText(x.text); });
                if (!w.length) return l.confidence;
                return w.reduce(function (a, x) { return a + x.confidence; }, 0) / w.length;
            }
            // Page text from its paragraphs. Near-zero-confidence lines (page edges, photo borders,
            // textures read as letters) are dropped when the page also has lines read with confidence.
            function pageText(res, extra) {
                var paras = paragraphs(res), junk = 0, solid = false;
                paras.forEach(function (p) { p.lines.forEach(function (l) {
                    if (!hasText(l.text)) return;
                    var c = lineConf(l);
                    if (c < 30) junk++;
                    if (c >= 60) solid = true;
                }); });
                if (!extra.length && !(junk && solid)) return res.data.text;
                if (extra.length) {
                    paras = paras.concat(extra);
                    paras.sort(function (a, b) { return a.bbox.y0 - b.bbox.y0 || a.bbox.x0 - b.bbox.x0; });
                }
                return paras.map(function (p) {
                    return p.lines.filter(function (l) { return hasText(l.text) && !(solid && lineConf(l) < 30); })
                        .map(function (l) { return l.text.replace(/\s+$/, ''); }).join('\n');
                }).filter(Boolean).join('\n\n');
            }
            // A sideways or upside-down page reads as low-confidence noise. Try the other three
            // orientations on a small copy and redo the page if one of them is clearly better.
            function bestOrientation(worker, canvas) {
                var confsByTurn = [], chain = Promise.resolve();
                [0, 1, 2, 3].forEach(function (turns) {
                    chain = chain.then(function () {
                        return recognize(worker, rotateCanvas(canvas, turns, PROBE_SIDE), false);
                    }).then(function (res) { confsByTurn[turns] = res.data.text.trim() ? res.data.confidence : 0; });
                });
                return chain.then(function () {
                    var best = 0;
                    for (var k = 1; k < 4; k++) if (confsByTurn[k] > confsByTurn[best]) best = k;
                    return confsByTurn[best] >= confsByTurn[0] + 15 ? best : 0;
                });
            }
            // Word boxes over the image that was recognised, coloured by confidence (desktop only).
            function drawBoxes(canvas, res, extra) {
                if (!boxes || !previewBox.clientWidth || !(window.matchMedia && matchMedia('(min-width: 900px)').matches)) return;
                var cs = getComputedStyle(boxes), col = function (n, d) { return cs.getPropertyValue(n).trim() || d; };
                var hi = col('--box-hi', '#3fa34d'), mid = col('--box-mid', '#e0a100'), lo = col('--box-lo', '#e5484d');
                // Cover the whole preview area (minus the file name): a page turned by the orientation
                // retry no longer has the preview's shape.
                var pw = previewBox.clientWidth, ph = Math.max(1, previewBox.clientHeight - fileMeta.offsetHeight - 6), dpr = Math.min(window.devicePixelRatio || 1, 2);
                var s = Math.min(pw / canvas.width, ph / canvas.height), dw = canvas.width * s, dh = canvas.height * s;
                boxes.width = Math.round(pw * dpr); boxes.height = Math.round(ph * dpr);
                boxes.style.width = pw + 'px'; boxes.style.height = ph + 'px';
                boxes.style.left = '0px'; boxes.style.top = '0px';
                var ctx = boxes.getContext('2d');
                ctx.scale(dpr, dpr);
                ctx.translate((pw - dw) / 2, (ph - dh) / 2);
                ctx.save();
                var a = res.data.rotateRadians || 0;
                if (a) { ctx.translate(dw / 2, dh / 2); ctx.rotate(a); ctx.translate(-dw / 2, -dh / 2); }
                ctx.fillStyle = '#ffffff'; ctx.fillRect(0, 0, dw, dh);
                ctx.drawImage(canvas, 0, 0, dw, dh);
                ctx.restore();
                ctx.lineWidth = Math.max(1, Math.min(2, dw / 600));
                paragraphs(res).concat(extra).forEach(function (p) { p.lines.forEach(function (l) { (l.words || []).forEach(function (w) {
                    if (!hasText(w.text)) return;
                    var b = w.bbox, c = w.confidence;
                    ctx.strokeStyle = c >= 90 ? hi : c >= 60 ? mid : lo;
                    ctx.globalAlpha = 0.18; ctx.fillStyle = ctx.strokeStyle;
                    ctx.fillRect(b.x0 * s, b.y0 * s, (b.x1 - b.x0) * s, (b.y1 - b.y0) * s);
                    ctx.globalAlpha = 1;
                    ctx.strokeRect(b.x0 * s, b.y0 * s, (b.x1 - b.x0) * s, (b.y1 - b.y0) * s);
                }); }); });
                showBoxes(!boxesToggle || boxesToggle.checked); show(boxesLegend, true);
            }
            // rotated(turns) gives the page turned by quarter turns, prepared for OCR.
            function ocrPage(worker, canvas, rotated, n, total) {
                progressLabel = total > 1 ? msg('recognizingPage', { n: n, total: total }) : msg('recognizing');
                setProgress(progressLabel, 0);
                var used = canvas;
                return recognize(worker, canvas, true).then(function (res) {
                    if (res.data.confidence >= ROTATE_BELOW_CONF) return res;
                    return bestOrientation(worker, canvas).then(function (turns) {
                        if (!turns) return res;
                        used = rotated(turns);
                        return recognize(worker, used, true);
                    });
                }).then(function (res) {
                    var twoPass = used.hasDarkAreas && modeSelect.value !== '7';
                    return (twoPass ? invertedPass(worker, used, res) : Promise.resolve([])).then(function (extra) {
                        texts.push(pageText(res, extra).trim());
                        if (total === 1 && !isPdf(file)) drawBoxes(used, res, extra);
                        if (typeof res.data.confidence === 'number') confs.push(res.data.confidence);
                        if (res.data.pdf) pdfs.push(res.data.pdf);
                    });
                });
            }

            getWorker(langs).then(function (worker) {
                return worker.setParameters({ tessedit_pageseg_mode: modeSelect.value, preserve_interword_spaces: isRtl(langs) ? '0' : '1' }).then(function () {
                    if (isPdf(file)) {
                        return forEachPdfPage(file, function (n, total) {
                            setProgress(msg('renderingPage', { n: n, total: total }), (n - 1) / total * 100);
                        }, function (canvas, n, total) {
                            return ocrPage(worker, canvas, function (turns) {
                                var r = rotateCanvas(canvas, turns);
                                r.hasDarkAreas = canvas.hasDarkAreas;
                                return r;
                            }, n, total);
                        });
                    }
                    return fileToImage(file).then(function (img) {
                        // Rotate the original, not the prepared copy, so upscaling suits the new orientation.
                        return ocrPage(worker, prepareCanvas(img, img.naturalWidth, img.naturalHeight), function (turns) {
                            var r = rotateCanvas(img, turns);
                            return prepareCanvas(r, r.width, r.height);
                        }, 1, 1);
                    });
                });
            }).then(function () {
                if (!texts.length) throw new Error(msg('errDecode'));
                var text = texts.length > 1
                    ? texts.map(function (s, i) { return '— ' + msg('pageLabel', { n: i + 1 }) + ' —\n' + s; }).join('\n\n')
                    : (texts[0] || '');
                output.value = text;
                state.pdfPages = pdfs;
                if (!text.trim()) notify(msg('noText'), 'warn');
                wordsBadge.textContent = msg('words', { n: countWords(texts.join(' ')) });
                if (confs.length && text.trim()) {
                    var avg = confs.reduce(function (a, b) { return a + b; }, 0) / confs.length;
                    confBadge.textContent = msg('confidence', { n: Math.round(avg) });
                    show(confBadge, true);
                } else {
                    show(confBadge, false);
                }
                show(stats, true);
                setOutputButtons(!!text.trim());
                var nextSteps = document.querySelector('.ocr-next');
                if (nextSteps && text.trim()) nextSteps.classList.add('is-ready');
                if (window.gtag) window.gtag('event', 'ocr_complete', { ocr_lang: langs, pages: texts.length });
            }).catch(function (err) {
                console.error('OCR error:', err);
                if (state.worker) { state.worker.terminate(); state.worker = null; state.workerLangs = null; }
                var detail = err && (err.message || (typeof err === 'string' ? err : ''));
                notify(msg('errOcr') + (detail ? ' (' + detail + ')' : ''), 'error');
            }).then(function () {
                state.busy = false;
                progressLabel = '';
                extractBtn.disabled = !state.file;
                show(progressBox, false);
            });
        });

        if (boxes) window.addEventListener('resize', function () { if (boxes.width && !state.busy) hideBoxes(); });
        if (boxesToggle) boxesToggle.addEventListener('change', function () { if (boxes.width) showBoxes(boxesToggle.checked); });

        // ---------- output actions ----------
        function flash(btn, text) {
            var label = btn.querySelector('.btn-label');
            if (!label) return;
            var original = label.textContent;
            label.textContent = text;
            setTimeout(function () { label.textContent = original; }, 1800);
        }

        // Drop lines that are only symbols or stray 1–2 character noise.
        // Uses Unicode classes so CJK, Arabic, Cyrillic, Devanagari etc. survive.
        function cleanNoise(text) {
            return text.split('\n').map(function (l) { return l.trim(); }).filter(function (line) {
                if (!line) return true;
                if (!/[\p{L}\p{N}]/u.test(line)) return false;
                if (line.length <= 2 && /^[\p{Script=Latin}]+$/u.test(line) && !/^(a|i|in|it|is|on|of|or|to|by|at|no|us|we|if|do|go|so|y|e|o|à|é)$/i.test(line)) return false;
                return true;
            }).join('\n').replace(/\n{3,}/g, '\n\n').trim();
        }
        cleanBtn.addEventListener('click', function () {
            if (!output.value) return;
            output.value = cleanNoise(output.value);
            wordsBadge.textContent = msg('words', { n: countWords(output.value) });
            flash(cleanBtn, msg('cleaned'));
        });

        copyBtn.addEventListener('click', function () {
            if (!output.value) return;
            var done = function () { flash(copyBtn, msg('copied')); };
            if (navigator.clipboard && window.isSecureContext) {
                navigator.clipboard.writeText(output.value).then(done, function () { output.select(); document.execCommand('copy'); done(); });
            } else {
                output.select(); document.execCommand('copy'); done();
            }
        });

        txtBtn.addEventListener('click', function () {
            if (!output.value) return;
            download(new Blob([output.value], { type: 'text/plain;charset=utf-8' }), 'ocr-text-' + stamp() + '.txt');
        });

        // Searchable PDF: Tesseract's own PDF renderer (page image + invisible text layer),
        // so every script is preserved. Multi-page results are merged with pdf-lib.
        pdfBtn.addEventListener('click', function () {
            var pages = state.pdfPages;
            if (!pages || !pages.length) return;
            var name = 'searchable-' + stamp() + '.pdf';
            if (pages.length === 1) {
                download(new Blob([new Uint8Array(pages[0])], { type: 'application/pdf' }), name);
                return;
            }
            pdfBtn.disabled = true;
            notify(msg('buildingPdf'));
            loadScript(PDF_LIB).then(function () {
                var PDFDocument = window.PDFLib.PDFDocument;
                return PDFDocument.create().then(function (merged) {
                    var chain = Promise.resolve();
                    pages.forEach(function (bytes) {
                        chain = chain.then(function () {
                            return PDFDocument.load(new Uint8Array(bytes)).then(function (src) {
                                return merged.copyPages(src, src.getPageIndices()).then(function (copied) {
                                    copied.forEach(function (p) { merged.addPage(p); });
                                });
                            });
                        });
                    });
                    return chain.then(function () { return merged.save(); });
                });
            }).then(function (bytes) {
                download(new Blob([bytes], { type: 'application/pdf' }), name);
                notify('');
            }).catch(function (err) {
                console.error('PDF export error:', err);
                notify(msg('errPdf'), 'error');
            }).then(function () { pdfBtn.disabled = false; });
        });
    });
})();
