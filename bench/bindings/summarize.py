"""Print the markdown tables used in README.md from results/bindings.json and results/versions.json."""
import json, os, sys
R = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
rows = json.load(open(os.path.join(R, "bindings.json")))
print("| Binding | PSM | Engine (as reported) | Init s | Per-call ms (tiny img, median) | Images/s (10 imgs) | Peak RSS MB | CER | Identical to CLI (bytes / normalised) |")
print("|---|---|---|---|---|---|---|---|---|")
for r in rows:
    if "images_per_s" not in r:
        print(f"| {r['binding']} | {r['psm']} | FAILED (exit {r['exit_code']}) | | | | | | |"); continue
    eng = (r.get("info") or {}).get("engine") or (r.get("info") or {}).get("tesseract.js-core", "")
    ident = f"{r.get('identical_bytes_vs_cli')}/10 / {r.get('identical_normalized_vs_cli')}/10" if r.get("identical_bytes_vs_cli") is not None else "(reference)"
    print(f"| {r['binding']} | {r['psm']} | {eng} | {r['init_s'] if r['init_s'] is not None else '–'} | {r['per_call_tiny_median_ms']} | "
          f"{r['images_per_s']} | {r['peak_rss_mb']} | {100*r['cer_mean']:.3f} % | {ident} |")
print()
print("| Package | Registry | Latest | Released | Licence |")
print("|---|---|---|---|---|")
for v in json.load(open(os.path.join(R, "versions.json"))):
    print(f"| {v['package']} | {v.get('registry','')} | {v.get('latest', v.get('error'))} | {(v.get('released') or '')[:10]} | {v.get('license')} |")
