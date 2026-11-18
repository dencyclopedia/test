#!/usr/bin/env python3
"""Per-language accuracy: 14 languages x tessdata_fast / tessdata / tessdata_best, Tesseract 5.5.4, OEM 1, PSM 3.

Images: corpus 'multilingual' set: 2 UDHR pages per language, 300 DPI, 12 pt, rendered in a font that covers the
script (DejaVu Serif for Latin/Cyrillic/Vietnamese, Noto Sans SC, IPAGothic, Noto Sans KR, Noto Naskh Arabic,
Noto Sans Devanagari).
Besides CER/WER (tools/metrics.py) we report cer_nospace: CER after deleting all whitespace from both texts, because
Tesseract often inserts spaces between Chinese/Japanese characters, which plain CER counts as errors.
Usage: python3 bench/languages/run.py
"""
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "accuracy"))
import benchlib as B  # noqa: E402

RES = HERE / "results"
MODELS = ["fast", "standard", "best"]
# extra run: tessdata standard with -c preserve_interword_spaces=1 (the setting the site's online tool uses)
VARIANTS = {m: (m, ()) for m in MODELS}
VARIANTS["standard+pis1"] = ("standard", ("-c", "preserve_interword_spaces=1"))


def nospace(s):
    return "".join(s.split())


def main():
    imgs = B.manifest(set="multilingual")
    jobs, commands = [], {}
    for m, (model, extra) in VARIANTS.items():
        commands[m] = " ".join(B.tess_cmd("<image>", model=model, lang="<lang>", extra=extra))
        for e in imgs:
            jobs.append(((m, e["id"]), B.tess_cmd(B.CORPUS / e["image"], model=model, lang=e["lang"], extra=extra),
                         B.gt(e), RES / "raw" / m / (e["id"] + ".txt")))
    print(len(jobs), "runs")
    res = B.run_jobs(jobs)
    by_id = {e["id"]: e for e in imgs}
    rows = []
    for (m, id_), s in sorted(res.items()):
        e = by_id[id_]
        hyp = (RES / "raw" / m / (id_ + ".txt")).read_text(encoding="utf-8")
        s["cer_nospace"] = B.metrics.cer(nospace(B.gt(e)), nospace(hyp))
        rows.append(dict(model=m, lang=e["lang"], id=id_, font=e["font"], **s))
    B.write_csv(RES / "per_image.csv", rows)
    g = defaultdict(list)
    for r in rows:
        g[(r["lang"], r["model"])].append(r)
    summ = [dict(lang=l, model=m, font=rs[0]["font"], n=len(rs), cer_mean=B.mean(r["cer"] for r in rs),
                 cer_nospace_mean=B.mean(r["cer_nospace"] for r in rs), wer_mean=B.mean(r["wer"] for r in rs),
                 cer_charweighted=B.micro_cer(rs)) for (l, m), rs in sorted(g.items())]
    B.write_csv(RES / "summary.csv", summ)
    B.write_meta(RES / "meta.json", commands, {"images": len(imgs)})


if __name__ == "__main__":
    main()
