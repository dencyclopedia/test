#!/usr/bin/env python3
"""Run PaddleOCR (CPU) on the engine subset. Run with the Python of a venv that has paddleocr + paddlepaddle:
   PADDLE_PDX_MODEL_SOURCE=huggingface <venv>/bin/python bench/engines/run_paddleocr.py
Default pipeline models for each language; document orientation / unwarping / textline orientation off
(plain OCR, comparable with Tesseract PSM 3). enable_mkldnn=False: with paddlepaddle 3.3.1 the oneDNN path
fails with "ConvertPirAttribute2RuntimeAttribute not support" on this CPU (see README).
Writes results/raw/paddleocr/<id>.txt and results/paddleocr_info.json."""
import json, os, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from subset import subset, lines_from_boxes, PADDLE_LANG, CORPUS  # noqa: E402
import paddle, paddleocr  # noqa: E402
from paddleocr import PaddleOCR  # noqa: E402

OUT = HERE / "results" / "raw" / "paddleocr"
pipes, info = {}, {"paddleocr": paddleocr.__version__, "paddlepaddle": paddle.__version__, "enable_mkldnn": False,
                   "models": {}}
for kind, e in subset():
    if (OUT / (e["id"] + ".txt")).exists() and "--resume" in sys.argv:
        continue
    if e["lang"] in os.environ.get("SKIP_LANGS", "").split(","):
        continue
    lang = PADDLE_LANG[e["lang"]]
    if lang not in pipes:
        pipes.clear()  # one pipeline in memory at a time (several at once ran out of RAM)
        pipes[lang] = PaddleOCR(lang=lang, use_doc_orientation_classify=False, use_doc_unwarping=False,
                                use_textline_orientation=False, enable_mkldnn=False,
                                **({"text_det_limit_type": "max", "text_det_limit_side_len": int(os.environ["DET_MAX_SIDE"])}
                                   if os.environ.get("DET_MAX_SIDE") else {}))
    items = []
    for r in pipes[lang].predict(str(CORPUS / e["image"])):
        info["models"][e["lang"]] = [r.get("model_settings", {}) and str(r["model_settings"])]
        for poly, t in zip(r["rec_polys"], r["rec_texts"]):
            xs, ys = [p[0] for p in poly], [p[1] for p in poly]
            items.append((min(xs), min(ys), max(xs), max(ys), t))
    p = OUT / (e["id"] + ".txt")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(lines_from_boxes(items, rtl=e["lang"] == "ara"), encoding="utf-8")
    print(e["id"], flush=True)
(HERE / "results" / "paddleocr_info.json").write_text(json.dumps(info, indent=1, default=str) + "\n")
