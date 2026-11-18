#!/usr/bin/env python3
"""Run the site's chart generator (tesseract repo ops/tools/charts/charts.py) with three additions, without
changing the shared tool:

  - data "format": "json"   a JSON list of objects (bench/python-throughput/results/throughput.json,
                            bench/bindings/results/bindings.json)
  - "label_head"            first column header of an hbar's data table (charts.py prints "Model")
  - "type": "vhist"         grouped vertical histogram from a wide CSV (one row per bin, one column per
                            series), "normalize": true = each series as % of its column total, optional
                            "ref": {"bin": "90-95", "label": "..."} dashed reference line at that bin

Every value is still read from the bench file named in the spec.

usage: python3 tools/images/figures/lab_charts.py /home/user/tesseract/ops/tools/charts/specs/<page>.json [--inject]
"""
import importlib.util
import json
import os
import sys

SITE = os.environ.get("SITE_REPO", "/home/user/tesseract")
_spec = importlib.util.spec_from_file_location("charts", os.path.join(SITE, "ops", "tools", "charts", "charts.py"))
C = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(C)

_load, _hbar, _line = C.load, C.hbar, C.line


def load(spec, test):
    if spec["data"]["format"] == "json":
        return json.load(open(os.path.join(test, spec["data"]["file"]), encoding="utf-8"))
    return _load(spec, test)


def hbar(spec, rows):
    out, h, table, head = _hbar(spec, rows)
    return out, h, table, [spec.get("label_head", head[0])] + head[1:]


def vhist(spec, rows):
    esc, W = C.esc, C.W
    dec = spec.get("decimals", 1)
    cols = [s["col"] for s in spec["series"]]
    tot = {c: sum(float(r[c]) for r in rows) for c in cols}
    val = (lambda r, c: float(r[c]) / tot[c] * 100) if spec.get("normalize") else (lambda r, c: float(r[c]))
    unit = "%" if spec.get("normalize") else spec.get("unit", "")
    ymax = spec.get("y_max") or C.nice_max(max(val(r, c) for r in rows for c in cols) * 1.08)
    left, right, top, ph = 56, 16, 84, 250
    pw = W - left - right
    h = top + ph + 50
    bw = pw / len(rows)
    Y = lambda v: top + ph - ph * min(v, ymax) / ymax
    out = [f'<text class="ch-title" x="0" y="18">{esc(spec["title"])}</text>',
           f'<text class="ch-axis" x="0" y="{top - 20}">{esc(spec.get("y_axis", ""))}</text>']
    lx = 0
    for k, s in enumerate(spec["series"]):
        out.append(f'<rect class="ch-key ch-s{k + 1}" x="{lx}" y="36" width="12" height="12" rx="2"/>'
                   f'<text class="ch-dl" x="{lx + 18}" y="46">{esc(s["label"])}</text>')
        lx += 18 + len(s["label"]) * 7.3 + 22
    for i in range(5):
        v = ymax * i / 4
        out.append(f'<line class="ch-grid" x1="{left}" x2="{left + pw}" y1="{Y(v):.1f}" y2="{Y(v):.1f}"/>'
                   f'<text class="ch-tick" x="{left - 8}" y="{Y(v) + 4:.1f}" text-anchor="end">{v:g}{esc(unit)}</text>')
    inner = bw * 0.8 / len(cols)
    for i, r in enumerate(rows):
        x0 = left + i * bw + bw * 0.1
        for k, c in enumerate(cols):
            v = val(r, c)
            out.append(f'<rect class="ch-s{k + 1}" x="{x0 + k * inner:.1f}" y="{Y(v):.1f}" width="{inner - 1:.1f}" '
                       f'height="{max(0.5, top + ph - Y(v)):.1f}"/>')
        if i % spec.get("x_every", 2) == 0:
            out.append(f'<text class="ch-tick" x="{left + i * bw:.1f}" y="{top + ph + 18}" text-anchor="middle">'
                       f'{esc(str(r[spec["x"]]).split("-")[0])}</text>')
    out.append(f'<text class="ch-tick" x="{left + pw:.1f}" y="{top + ph + 18}" text-anchor="middle">'
               f'{esc(str(rows[-1][spec["x"]]).split("-")[-1])}</text>')
    if spec.get("ref"):
        i = [str(r[spec["x"]]) for r in rows].index(spec["ref"]["bin"])
        x = left + i * bw
        out.append(f'<line class="ch-ref" x1="{x:.1f}" x2="{x:.1f}" y1="{top - 6}" y2="{top + ph}"/>'
                   f'<text class="ch-ref-l" x="{x - 6:.1f}" y="{top + 8}" text-anchor="end">{esc(spec["ref"]["label"])}</text>')
    out.append(f'<line class="ch-base" x1="{left}" x2="{left + pw}" y1="{top + ph}" y2="{top + ph}"/>'
               f'<text class="ch-axis" x="{left + pw}" y="{top + ph + 36}" text-anchor="end">{esc(spec.get("x_axis", ""))}</text>')
    table = [(str(r[spec["x"]]),) + tuple(f"{val(r, c):.{dec}f}{unit} ({int(float(r[c])):,})" for c in cols) for r in rows]
    return out, h, table, [spec.get("x_axis", "x")] + [s["label"] for s in spec["series"]]


def line(spec, rows):  # charts.build() calls line() for every non-hbar type
    return vhist(spec, rows) if spec["type"] == "vhist" else _line(spec, rows)


C.load, C.hbar, C.line = load, hbar, line
C.STANDALONE_CSS += ".ch-ref{stroke:#c8372b;stroke-dasharray:4 4;stroke-width:1.5}.ch-ref-l{fill:#c8372b;font-size:11px}\n"

if __name__ == "__main__":
    C.main()
