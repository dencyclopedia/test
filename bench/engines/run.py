#!/usr/bin/env python3
"""Engine comparison: Tesseract 5.5.4 vs EasyOCR vs PaddleOCR on a shared subset (see subset.py). CPU only.

Steps:
  1. python3 bench/engines/run.py tesseract                 (Tesseract 5.5.4, tessdata standard, OEM 1, PSM 3)
  2. <easyocr venv>/bin/python bench/engines/run_easyocr.py
  3. PADDLE_PDX_MODEL_SOURCE=huggingface <paddle venv>/bin/python bench/engines/run_paddleocr.py
  4. python3 bench/engines/run.py score                     (CER/WER for every engine with raw output present)
For EasyOCR/PaddleOCR (box output) the page text is rebuilt with subset.lines_from_boxes (documented there).
"""
import statistics
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "accuracy"))
sys.path.insert(0, str(HERE))
import benchlib as B  # noqa: E402
from subset import subset  # noqa: E402

RES = HERE / "results"
ENGINES = ["tesseract", "easyocr", "paddleocr"]


def tesseract():
    jobs = [(e["id"], B.tess_cmd(B.CORPUS / e["image"], lang=e["lang"]), B.gt(e),
             RES / "raw" / "tesseract" / (e["id"] + ".txt")) for _, e in subset()]
    B.run_jobs(jobs)


def score():
    sub = subset()
    items = []
    for eng in ENGINES:
        for kind, e in sub:
            p = RES / "raw" / eng / (e["id"] + ".txt")
            if p.exists():
                items.append(((eng, kind, e["id"]), B.gt(e), p.read_text(encoding="utf-8")))
    sc = B.score_jobs(items)
    rows = [dict(engine=k[0], kind=k[1], id=k[2], **s) for k, s in sc.items()]
    B.write_csv(RES / "per_image.csv", rows)
    g = defaultdict(list)
    for r in rows:
        g[(r["kind"], r["engine"])].append(r)
    summ = [dict(kind=k, engine=eng, n=len(rs), cer_mean=B.mean(r["cer"] for r in rs),
                 cer_median=statistics.median(r["cer"] for r in rs), wer_mean=B.mean(r["wer"] for r in rs),
                 word_recall_unordered_mean=B.mean(r["word_recall_unordered"] for r in rs))
            for (k, eng), rs in sorted(g.items())]
    B.write_csv(RES / "summary.csv", summ)
    B.write_meta(RES / "meta.json", {"tesseract": " ".join(B.tess_cmd("<image>", lang="<lang>")),
                                     "easyocr": "bench/engines/run_easyocr.py", "paddleocr": "bench/engines/run_paddleocr.py"},
                 {"images": len(sub)})


if __name__ == "__main__":
    {"tesseract": tesseract, "score": score}[sys.argv[1]]()
