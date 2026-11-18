#!/usr/bin/env python3
"""HTML fragments for tesseractocr.org/doc/ built only from bench results (nothing typed by hand).

usage: python3 tools/images/figures/doc_fragments.py [--page /home/user/tesseract/doc/index.html]

Replaces the text between <!-- gen:NAME --> and <!-- /gen:NAME --> in the page for:
  psm-heatmap   mean CER per --psm x sample type          (bench/psm/results/summary.csv)
  psm-explorer  raw stdout of all 14 modes on 4 images    (bench/psm/results/raw, per_image.csv)
  oem-models    OEM 0-3 x tessdata_fast/standard/best     (bench/models/results/summary.csv)
  model-speed   median seconds per page per model         (bench/accuracy/results/timing/timing-models.csv)
  formats       output files: command, size, excerpt      (bench/formats/results)
  help-extra    tesseract --help-extra, verbatim          (bench/formats/results/help-extra.txt)
The page only shows/hides the explorer panels with CSS/JS; every word is in the HTML.
"""
import argparse, csv, html, json, os, re, statistics, textwrap

T = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
TREE = "https://github.com/dencyclopedia/test/tree/claude/upbeat-volta-fdndl6/"
e = lambda s: html.escape(str(s), quote=False)
P = lambda x: os.path.join(T, x)
KINDS = [("page", "Page"), ("receipt", "Receipt"), ("line", "Line"), ("word", "Word"), ("sparse", "Labels &amp; UI")]
SHORT = {"0": "OSD only", "1": "auto + OSD", "2": "auto, no OCR", "3": "auto (default)", "4": "single column",
         "5": "vertical block", "6": "single block", "7": "single line", "8": "single word", "9": "word in a circle",
         "10": "single character", "11": "sparse text", "12": "sparse + OSD", "13": "raw line"}


def pct(v, d=1):
    return f"{float(v) * 100:.{d}f}%"


def heat_class(c):
    c = float(c)
    return "h0" if c < 0.01 else "h1" if c < 0.05 else "h2" if c < 0.15 else "h3" if c < 0.5 else "h4"


def psm_heatmap():
    rows = list(csv.DictReader(open(P("bench/psm/results/summary.csv"))))
    by = {(r["psm"], r["kind"]): r for r in rows}
    n = {k: by[("3", k)]["n"] for k, _ in KINDS}
    o = ['<div class="table-wrap"><table class="heat" aria-label="Mean character error rate for each --psm on five kinds of image">',
         '<thead><tr><th scope="col">--psm</th>' + "".join(f'<th scope="col">{lab} <span>({n[k]})</span></th>' for k, lab in KINDS) + "</tr></thead><tbody>"]
    for p in range(14):
        p = str(p)
        cells = []
        for k, _ in KINDS:
            r = by[(p, k)]
            if int(r["errors"]) == int(r["n"]):
                cells.append('<td class="hx">error</td>')
            elif int(r["empty_outputs"]) == int(r["n"]):
                cells.append('<td class="hx">no text</td>')
            else:
                cells.append(f'<td class="{heat_class(r["cer_mean"])}">{pct(r["cer_mean"], 2)}</td>')
        o.append(f'<tr><th scope="row"><code>{p}</code> {SHORT[p]}</th>{"".join(cells)}</tr>')
    o.append("</tbody></table></div>")
    return "\n".join(o)


EXPLORER = [("receipt", "receipt/receipt03_freemono", "Receipt", "FreeMono, 300 DPI"),
            ("screenshot", "screenshot/inbox_light_1x", "Inbox screenshot", "light UI, 1x"),
            ("line", "line/line01_dejavu-serif", "Single line", "DejaVu Serif"),
            ("word", "word/word04_courier10", "Single word", "Courier 10 Pitch")]


def read(p):
    return open(P(p), encoding="utf-8").read() if os.path.exists(P(p)) else ""


def psm_explorer():
    per = {(r["psm"], r["id"]): r for r in csv.DictReader(open(P("bench/psm/results/per_image.csv")))}
    names = json.load(open(P("bench/psm/results/meta.json")))["psm_names"]
    o = ['<div class="psmx" data-psmx>',
         '<div class="seg" role="group" aria-label="Choose a page segmentation mode">'
         + "".join(f'<button type="button" data-psm="{p}" aria-pressed="{str(p == 3).lower()}">{p}</button>' for p in range(14))
         + "</div>"]
    for p in range(14):
        p = str(p)
        o.append(f'<div class="px-p{" on" if p == "3" else ""}" data-psm="{p}">')
        o.append(f'<p class="px-h"><code>--psm {p}</code> {e(names[p])}</p><div class="px-grid">')
        for kind, iid, lab, sub in EXPLORER:
            stem = iid.split("/", 1)[1]
            r = per[(p, iid)]
            gt = len(read(f"corpus/{iid}.gt.txt").strip())
            if p == "0":
                out = read(f"bench/psm/results/raw/psm0-default-oem/{iid}.txt")
                std, _, err = out.partition("--- stderr ---")
                err1 = read(f"bench/psm/results/raw/psm0/{iid}.err").strip()
                body = (f'<span class="px-n">--oem 1: {e(err1)}</span>\n<span class="px-n">default OEM (stdout):</span>\n'
                        + (e(std.strip()) if std.strip() else '<span class="px-n">(empty)</span>')
                        + (f'\n<span class="px-n">stderr: {e(" | ".join(x for x in err.strip().splitlines()))}</span>' if err.strip() else ""))
                score = '<b class="px-c">no text by design</b>'
            else:
                txt = read(f"bench/psm/results/raw/psm{p}/{iid}.txt")
                err = read(f"bench/psm/results/raw/psm{p}/{iid}.err").strip()
                txt = "\n".join(l for l in txt.rstrip().splitlines() if l.strip())  # blank lines dropped
                body = e(txt) if txt else '<span class="px-n">(empty output)</span>'
                if p == "2" and err:
                    body += f'\n<span class="px-n">stderr: {e(err)}</span>'
                c = float(r["cer"])
                score = f'<b class="px-c {"good" if c < 0.02 else "bad" if c > 0.2 else ""}">CER {pct(c)}</b>'
            o.append(f'<figure class="px-o"><figcaption><span>{lab} <i>{sub} · {gt} chars</i></span>{score}</figcaption>'
                     f'<pre tabindex="0">{body}</pre></figure>')
        o.append("</div></div>")
    o.append("</div>")
    return "\n".join(o)


def oem_models():
    rows = list(csv.DictReader(open(P("bench/models/results/summary.csv"))))
    by = {(r["model"], r["oem"], r["group"]): r for r in rows}
    errs = {x["id"]: x for x in json.load(open(P("bench/errors/results/errors.json")))}

    def cell(m, oem):
        vals = []
        for g, lab in (("eng-clean", "clean"), ("eng-degraded", "degraded")):
            r = by.get((m, oem, g))
            if r is None:
                if m == "fast" and oem == "2" and "oem2-tessdata-fast" in errs:
                    return '<td class="bad">error: no legacy data</td>'
                return '<td class="hx">not run</td>'
            if int(r["failed"]) == int(r["n"]):
                return '<td class="bad">error: no legacy data</td>'
            vals.append(f"{pct(r['cer_mean'], 2)} {lab}")
        return "<td>" + " · ".join(vals) + "</td>"
    lab = {"0": "0 · legacy only", "1": "1 · LSTM only", "2": "2 · legacy + LSTM", "3": "3 · default"}
    o = ['<div class="table-wrap"><table aria-label="Mean CER by --oem and model set, English clean and degraded pages">',
         '<thead><tr><th scope="col">--oem</th><th scope="col">tessdata_fast</th><th scope="col">tessdata (standard)</th><th scope="col">tessdata_best</th></tr></thead><tbody>']
    for oem in "0123":
        o.append(f'<tr><th scope="row">{lab[oem]}</th>{cell("fast", oem)}{cell("standard", oem)}{cell("best", oem)}</tr>')
    o.append("</tbody></table></div>")
    return "\n".join(o)


def model_speed():
    rows = [r for r in csv.DictReader(open(P("bench/accuracy/results/timing/timing-models.csv"))) if r["id"].startswith("clean/")]
    meta = json.load(open(P("bench/accuracy/results/timing/meta.json")))
    med = {m: statistics.median(float(r["median_s"]) for r in rows if r["model"] == m) for m in ("fast", "standard", "best")}
    n = len({r["id"] for r in rows})
    return (f'<ul class="kpis"><li><b>{med["fast"]:.2f} s</b><span>tessdata_fast, per page</span></li>'
            f'<li><b>{med["standard"]:.2f} s</b><span>tessdata (standard)</span></li>'
            f'<li><b class="bad">{med["best"]:.2f} s</b><span>tessdata_best</span></li></ul>\n'
            f'<span class="src">Median of the per-page medians (5 runs each) on {n} clean 300 DPI pages, <code>OMP_THREAD_LIMIT=1</code>. Source: '
            f'<a href="{TREE}bench/accuracy" rel="noopener">bench/accuracy</a> (results/timing/timing-models.csv) · '
            f'{e(meta["machine"])}, {e(meta["cpu"])}, {meta["cores"]} vCPU · Tesseract 5.5.4 · {meta["date_utc"][:10]}</span>')


FORMATS = [("txt", "receipt.txt", "(default, no config)", "Plain text, one line per text line."),
           ("hocr", "receipt-hocr.hocr", "hocr", "XHTML with a bbox and word confidence (x_wconf) for every page, block, line and word."),
           ("tsv", "receipt-tsv.tsv", "tsv", "One row per element: level, position, size, confidence (0-100) and text. Easiest to parse."),
           ("alto", "receipt-alto.xml", "alto", "ALTO v3 XML (library and archive standard); WC is confidence 0-1."),
           ("page", "receipt-page.page.xml", "page", "PAGE XML (PRImA), used by transcription tools."),
           ("box", "receipt-box.box", "makebox", "One character per line with its box (origin bottom-left), for training."),
           ("pdf", "receipt-pdf.pdf", "pdf", "The image plus an invisible text layer: a searchable PDF."),
           ("textonly_pdf", "receipt-textonly.pdf", "-c textonly_pdf=1 pdf", "Only the invisible text layer, no image: for overlaying on an existing PDF.")]


def formats():
    sizes = {r["file"]: int(r["bytes"]) for r in csv.DictReader(open(P("bench/formats/results/sizes.csv")))}
    meta = read("bench/formats/results/meta.txt")
    ver = re.search(r"^tesseract (\S+)", meta, re.M).group(1)
    o = ['<div class="table-wrap"><table aria-label="Tesseract output formats: command, file and size for one receipt">',
         '<thead><tr><th scope="col">Format</th><th scope="col">Command (after <code>tesseract receipt.png out</code>)</th><th scope="col">File</th><th scope="col">Size</th><th scope="col">What you get</th></tr></thead><tbody>']
    for name, f, cmd, what in FORMATS:
        ext = f.split("receipt", 1)[1].split(".", 1)[1]
        o.append(f'<tr><th scope="row">{name}</th><td><code>{e(cmd)}</code></td><td><code>out.{ext}</code></td>'
                 f'<td class="num">{sizes[f]:,} B</td><td>{e(what)}</td></tr>')
    o.append("</tbody></table></div>")
    o.append(f'<span class="src">One 945 × 1222 px receipt (300 DPI, synthetic), <code>-l eng --oem 1 --psm 6</code>, Tesseract {ver}, tessdata (standard). '
             f'Source: <a href="{TREE}bench/formats" rel="noopener">bench/formats</a> (run.sh, results/sizes.csv, results/out/)</span>')
    return "\n".join(o)


def excerpt(name, f, n):
    lines = read(f"bench/formats/results/out/{f}").splitlines()
    return e("\n".join(lines[:n]))


def help_extra():
    t = read("bench/formats/results/help-extra.txt").replace("/opt/tess554/bin/tesseract", "tesseract")
    return e(t.rstrip())


def inject(page, name, frag):
    s = open(page, encoding="utf-8").read()
    a, b = f"<!-- gen:{name} -->", f"<!-- /gen:{name} -->"
    if a not in s:
        print("skip (no marker)", name)
        return s
    i, j = s.index(a) + len(a), s.index(b)
    s = s[:i] + "\n" + frag + "\n" + s[j:]
    open(page, "w", encoding="utf-8").write(s)
    print("injected", name, len(frag), "chars")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--page", default="/home/user/tesseract/doc/index.html")
    a = ap.parse_args()
    frags = {"psm-heatmap": psm_heatmap(), "psm-explorer": psm_explorer(), "oem-models": oem_models(),
             "model-speed": model_speed(), "formats": formats(), "help-extra": help_extra(),
             "x-txt": excerpt("txt", "receipt.txt", 8), "x-hocr": e(textwrap.dedent("\n".join(read("bench/formats/results/out/receipt-hocr.hocr").splitlines()[13:19]))),
             "x-tsv": excerpt("tsv", "receipt-tsv.tsv", 9), "x-alto": e(textwrap.dedent("\n".join(read("bench/formats/results/out/receipt-alto.xml").splitlines()[20:25]))),
             "x-box": excerpt("box", "receipt-box.box", 6)}
    for k, v in frags.items():
        inject(a.page, k, v)
