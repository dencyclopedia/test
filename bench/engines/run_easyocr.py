#!/usr/bin/env python3
"""Run EasyOCR (CPU) on the engine subset. Run with the Python of a venv that has easyocr installed:
   <venv>/bin/python bench/engines/run_easyocr.py
Writes results/raw/easyocr/<id>.txt and results/easyocr_info.json."""
import json, os, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from subset import subset, lines_from_boxes, EASYOCR_LANG, CORPUS  # noqa: E402
import easyocr  # noqa: E402

OUT = HERE / "results" / "raw" / "easyocr"
readers = {}
info = {"easyocr": easyocr.__version__, "gpu": False, "readtext_args": "detail=1, paragraph=False", "langs": {}}
for kind, e in subset():
    lang = e["lang"]
    langs = [EASYOCR_LANG[lang]] if lang == "eng" else [EASYOCR_LANG[lang], "en"]
    key = tuple(langs)
    if key not in readers:
        readers[key] = easyocr.Reader(list(key), gpu=False, verbose=False)
        info["langs"][lang] = list(key)
    res = readers[key].readtext(str(CORPUS / e["image"]), detail=1, paragraph=False)
    items = [(min(p[0] for p in b), min(p[1] for p in b), max(p[0] for p in b), max(p[1] for p in b), t) for b, t, c in res]
    txt = lines_from_boxes(items, rtl=lang == "ara")
    p = OUT / (e["id"] + ".txt")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(txt, encoding="utf-8")
    print(e["id"], flush=True)
(HERE / "results" / "easyocr_info.json").write_text(json.dumps(info, indent=1) + "\n")
