#!/usr/bin/env python3
"""All 14 page segmentation modes (--psm 0..13) on five kinds of image, Tesseract 5.5.4, tessdata standard eng, OEM 1.

Sample types (from corpus/manifest.json):
  page       clean full pages, 300 DPI, DejaVu Serif (3)
  receipt    clean receipts (4)
  line       single text lines (8)
  word       single words (10)
  sparse     scattered labels (4) and light-mode UI screenshots at 1x (5)
Every output (stdout and stderr) is kept in results/raw/psm<N>/<image id>.txt / .err so the real outputs can be shown.
Usage: python3 bench/psm/run.py
"""
import statistics
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "accuracy"))
import benchlib as B  # noqa: E402

RES = HERE / "results"
PSM_NAMES = {
    0: "Orientation and script detection (OSD) only", 1: "Automatic page segmentation with OSD",
    2: "Automatic page segmentation, but no OSD, or OCR (not implemented)", 3: "Fully automatic page segmentation, but no OSD (default)",
    4: "Assume a single column of text of variable sizes", 5: "Assume a single uniform block of vertically aligned text",
    6: "Assume a single uniform block of text", 7: "Treat the image as a single text line",
    8: "Treat the image as a single word", 9: "Treat the image as a single word in a circle",
    10: "Treat the image as a single character", 11: "Sparse text. Find as much text as possible in no particular order",
    12: "Sparse text with OSD", 13: "Raw line. Treat the image as a single text line, bypassing Tesseract-specific hacks",
}


def samples():
    s = [("page", e) for e in B.manifest(set="clean", dpi=300, size_pt=12, font="DejaVu Serif")]
    s += [("receipt", e) for e in B.manifest(set="receipt", degradation=None)[:4]]
    s += [("line", e) for e in B.manifest(set="line")]
    s += [("word", e) for e in B.manifest(set="word")]
    s += [("sparse", e) for e in B.manifest(set="sparse")]
    s += [("sparse", e) for e in B.manifest(set="screenshot", theme="light", device_scale_factor=1)]
    return s


def main():
    smp = samples()
    jobs, commands = [], {}
    for psm in range(14):
        commands[f"psm{psm}"] = " ".join(B.tess_cmd("<image>", psm=psm))
        for kind, e in smp:
            jobs.append(((psm, e["id"]), B.tess_cmd(B.CORPUS / e["image"], psm=psm), B.gt(e),
                         RES / "raw" / f"psm{psm}" / (e["id"] + ".txt")))
    print(len(jobs), "runs")
    res = B.run_jobs(jobs)
    kinds = {e["id"]: k for k, e in smp}
    rows = []
    for (psm, id_), s in sorted(res.items()):
        (RES / "raw" / f"psm{psm}" / (id_ + ".err")).write_text(s["stderr"] + "\n", encoding="utf-8")
        rows.append(dict(psm=psm, psm_name=PSM_NAMES[psm], kind=kinds[id_], id=id_,
                         empty_output=s["out_chars"] == 0, **s))
    B.write_csv(RES / "per_image.csv", rows)
    g = defaultdict(list)
    for r in rows:
        g[(r["psm"], r["kind"])].append(r)
    summ = []
    for (psm, kind), rs in sorted(g.items()):
        cers = [r["cer"] for r in rs]
        summ.append(dict(psm=psm, psm_name=PSM_NAMES[psm], kind=kind, n=len(rs),
                         empty_outputs=sum(r["empty_output"] for r in rs), errors=sum(r["rc"] != 0 for r in rs),
                         cer_mean=B.mean(cers), cer_median=statistics.median(cers), wer_mean=B.mean(r["wer"] for r in rs),
                         word_recall_unordered_mean=B.mean(r["word_recall_unordered"] for r in rs),
                         example_stderr=next((r["stderr"] for r in rs if r["stderr"]), "")))
    B.write_csv(RES / "summary.csv", summ)
    B.write_meta(RES / "meta.json", commands, {"psm_names": PSM_NAMES, "samples": {k: [e["id"] for kk, e in smp if kk == k]
                                                                                   for k in dict(smp)}})


if __name__ == "__main__":
    main()
