#!/usr/bin/env python3
"""tessdata_fast vs tessdata (standard) vs tessdata_best, and OEM 0/1/2/3, with Tesseract 5.5.4.

Image subset (from corpus/manifest.json):
  eng: clean pages at 300 DPI (18), degraded pages at 8 levels (32), clean receipts (10)
  other languages: multilingual pages for deu fra rus chi_sim ara hin (2 pages each)
Runs:
  model in {fast, standard, best} x --oem 1 --psm 3
  OEM in {0 legacy, 1 LSTM, 2 legacy+LSTM, 3 default} with tessdata (standard, has legacy data);
  plus OEM 0 attempted with fast and best to record the error they give.
Usage: python3 bench/models/run.py
"""
import statistics
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "accuracy"))
import benchlib as B  # noqa: E402

RES = HERE / "results"
DEG_LEVELS = ["none", "blur2", "noise30", "jpeg50", "skew3", "light75", "contrast2", "phone1"]
OTHER_LANGS = ["deu", "fra", "rus", "chi_sim", "ara", "hin"]


def subset():
    imgs = B.manifest(set="clean", dpi=300, size_pt=12)
    imgs += B.manifest(set="degraded", level=DEG_LEVELS)
    imgs += B.manifest(set="receipt", degradation=None)
    imgs += B.manifest(set="multilingual", lang=OTHER_LANGS)
    return imgs


def group(e):
    if e["set"] == "multilingual":
        return "lang:" + e["lang"]
    if e["set"] == "degraded":
        return "eng-degraded"
    return "eng-" + e["set"]


def main():
    imgs = subset()
    configs = [(m, 1) for m in ("fast", "standard", "best")] + [("standard", o) for o in (0, 2, 3)] + \
              [("fast", 0), ("best", 0)]
    jobs, commands = [], {}
    for model, oem in configs:
        run = f"{model}-oem{oem}"
        commands[run] = " ".join(B.tess_cmd("<image>", model=model, lang="<lang>", oem=oem, psm=3))
        for e in imgs:
            if oem != 1 and model != "standard" and e["set"] != "clean":
                continue  # fast/best OEM 0 only attempted on clean pages to capture the error
            cmd = B.tess_cmd(B.CORPUS / e["image"], model=model, lang=e["lang"], oem=oem, psm=3)
            jobs.append(((run, e["id"]), cmd, B.gt(e), RES / "raw" / run / (e["id"] + ".txt")))
    print(len(jobs), "runs")
    res = B.run_jobs(jobs)
    by_id = {e["id"]: e for e in imgs}
    rows = []
    for (run, id_), s in sorted(res.items()):
        e = by_id[id_]
        model, oem = run.split("-oem")
        rows.append(dict(run=run, model=model, oem=int(oem), id=id_, set=e["set"], lang=e["lang"], group=group(e),
                         level=e.get("level", ""), **s))
    B.write_csv(RES / "per_image.csv", rows)
    g = defaultdict(list)
    for r in rows:
        g[(r["model"], r["oem"], r["group"])].append(r)
    summ = []
    for (model, oem, grp), rs in sorted(g.items()):
        cers = [r["cer"] for r in rs]
        summ.append(dict(model=model, oem=oem, group=grp, n=len(rs), failed=sum(r["rc"] != 0 for r in rs),
                         cer_mean=B.mean(cers), cer_median=statistics.median(cers), wer_mean=B.mean(r["wer"] for r in rs),
                         cer_charweighted=B.micro_cer(rs), example_stderr=next((r["stderr"] for r in rs if r["rc"]), "")))
    B.write_csv(RES / "summary.csv", summ)
    B.write_meta(RES / "meta.json", commands, {"images": len(imgs), "degraded_levels": DEG_LEVELS,
                                               "other_langs": OTHER_LANGS})


if __name__ == "__main__":
    main()
