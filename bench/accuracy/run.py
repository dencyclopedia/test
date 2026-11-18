#!/usr/bin/env python3
"""Accuracy of Tesseract on the clean (DPI x font) and degraded corpus sets, and 5.3.4 vs 5.5.4.

Runs:
  554-standard : Tesseract 5.5.4, tessdata (standard) eng, --oem 1 --psm 3   (the reference run)
  534-standard : Tesseract 5.3.4 (Ubuntu 24.04 apt binary), same model files, same flags
  534-apt      : Tesseract 5.3.4 with Ubuntu's packaged eng.traineddata (tesseract-ocr-eng 1:4.1.0-2)
Usage: python3 bench/accuracy/run.py
Outputs: results/per_image.csv, results/summary_*.csv, results/raw/<run>/<image id>.txt, results/meta.json
"""
import statistics
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import benchlib as B  # noqa: E402

RES = HERE / "results"
RUNS = {
    "554-standard": dict(version="5.5.4", model="standard"),
    "534-standard": dict(version="5.3.4", model="standard"),
    "534-apt": dict(version="5.3.4", model="apt"),
}


def main():
    images = B.manifest(set=("clean", "degraded"))
    jobs, commands = [], {}
    for run, cfg in RUNS.items():
        commands[run] = " ".join(B.tess_cmd("<image>", lang="eng", oem=1, psm=3, **cfg))
        for e in images:
            cmd = B.tess_cmd(B.CORPUS / e["image"], lang="eng", oem=1, psm=3, **cfg)
            jobs.append(((run, e["id"]), cmd, B.gt(e), RES / "raw" / run / (e["id"] + ".txt")))
    print(len(jobs), "tesseract runs")
    res = B.run_jobs(jobs)
    rows = []
    for (run, id_), s in sorted(res.items()):
        e = next(x for x in images if x["id"] == id_)
        rows.append(dict(run=run, id=id_, set=e["set"], dpi=e["dpi"], size_pt=e["size_pt"], font=e["font"], font_class=e["font_class"],
                         level=e.get("level", "none"), base=e.get("base", ""), **s))
    B.write_csv(RES / "per_image.csv", rows)

    def summarize(name, keyfn, filt):
        g = defaultdict(list)
        for r in rows:
            if filt(r):
                g[keyfn(r)].append(r)
        out = []
        for k, rs in sorted(g.items(), key=lambda kv: str(kv[0])):
            k = k if isinstance(k, tuple) else (k,)
            cers = [r["cer"] for r in rs]
            out.append(dict(zip(name, k), n=len(rs), cer_mean=B.mean(cers), cer_median=statistics.median(cers),
                            cer_max=max(cers), wer_mean=B.mean(r["wer"] for r in rs), cer_charweighted=B.micro_cer(rs)))
        return out

    clean = lambda r: r["set"] == "clean"  # noqa: E731
    deg = lambda r: r["set"] == "degraded"  # noqa: E731
    B.write_csv(RES / "summary_dpi.csv", summarize(("run", "size_pt", "dpi"), lambda r: (r["run"], r["size_pt"], r["dpi"]), clean))
    B.write_csv(RES / "summary_dpi_fontclass.csv",
                summarize(("run", "size_pt", "dpi", "font_class"),
                          lambda r: (r["run"], r["size_pt"], r["dpi"], r["font_class"]), clean))
    B.write_csv(RES / "summary_dpi_font.csv",
                summarize(("run", "size_pt", "dpi", "font"), lambda r: (r["run"], r["size_pt"], r["dpi"], r["font"]), clean))
    B.write_csv(RES / "summary_degradation.csv", summarize(("run", "level"), lambda r: (r["run"], r["level"]), deg))
    B.write_csv(RES / "summary_degradation_font.csv",
                summarize(("run", "level", "font"), lambda r: (r["run"], r["level"], r["font"]), deg))
    B.write_csv(RES / "summary_runs.csv", summarize(("run", "set"), lambda r: (r["run"], r["set"]), lambda r: True))
    # 5.3.4 vs 5.5.4 on identical models: how many images give byte-identical output?
    same = defaultdict(int)
    for e in images:
        a = (RES / "raw" / "554-standard" / (e["id"] + ".txt")).read_text(encoding="utf-8")
        b = (RES / "raw" / "534-standard" / (e["id"] + ".txt")).read_text(encoding="utf-8")
        same["identical" if a == b else "different"] += 1
    B.write_csv(RES / "version_identical_output.csv", [dict(comparison="5.5.4 vs 5.3.4, tessdata standard eng",
                                                             images=len(images), **same)])
    B.write_meta(RES / "meta.json", commands, {"images": len(images), "sets": ["clean", "degraded"]})
    print("done")


if __name__ == "__main__":
    main()
