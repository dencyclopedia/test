#!/usr/bin/env python3
"""Score the online tool's outputs (results/raw/browser, from run.js) and compare with native Tesseract 5.5.4 on the
same image files (no preprocessing, no rotation detection): tessdata (standard) and tessdata_best, OEM 1, PSM 3.
Usage: python3 bench/ocr-online/score.py
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "accuracy"))
import benchlib as B  # noqa: E402

RES = HERE / "results"


def main():
    runs = json.loads((RES / "browser_runs.json").read_text(encoding="utf-8"))["runs"]
    man = {e["id"]: e for e in B.manifest()}
    jobs = []
    for r in runs:
        e = man[r["id"]]
        for m in ("standard", "best"):
            jobs.append(((f"native-5.5.4-{m}", r["id"]), B.tess_cmd(B.CORPUS / e["image"], model=m, lang=e["lang"]),
                         B.gt(e), RES / "raw" / f"native-5.5.4-{m}" / (r["id"] + ".txt")))
    native = B.run_jobs(jobs)
    items = [(("browser", r["id"]), B.gt(man[r["id"]]),
              (RES / "raw" / "browser" / (r["id"] + ".txt")).read_text(encoding="utf-8")) for r in runs]
    br = B.score_jobs(items)
    rows = []
    for r in runs:
        row = dict(label=r["label"], id=r["id"], lang=r["lang"], browser_status=r["status"])
        for k, sc in (("browser", br[("browser", r["id"])]), ("native_standard", native[("native-5.5.4-standard", r["id"])]),
                      ("native_best", native[("native-5.5.4-best", r["id"])])):
            row[f"{k}_cer"] = sc["cer"]
            row[f"{k}_wer"] = sc["wer"]
            row[f"{k}_word_recall_unordered"] = sc["word_recall_unordered"]
        rows.append(row)
    B.write_csv(RES / "comparison.csv", rows)
    B.write_meta(RES / "meta.json", {"browser": "node bench/ocr-online/run.js (see browser_runs.json)",
                                     "native": " ".join(B.tess_cmd("<image>", model="standard", lang="<lang>")) + "  (and tessdata_best)"},
                 {"tesseract_js": "5.1.1 (tesseract.js-core v5.1.1, simd-lstm build)",
                  "tesseract_js_core_embedded_version_string": "5.1.0-280-ge20b (found in the wasm binary of "
                  "https://cdn.jsdelivr.net/npm/tesseract.js-core@v5.1.1/tesseract-core-simd-lstm.wasm.js, sha256 "
                  "ce20eda9533cbed1e6c2b4276fbae1e0adc61b6754b5513084be601787b457cf)",
                  "browser_models": "@tesseract.js-data/<lang>/4.0.0_best_int (jsdelivr)"})
    for r in rows:
        print(f'{r["label"]:22} browser {r["browser_cer"]:.4f}  native-std {r["native_standard_cer"]:.4f}  native-best {r["native_best_cer"]:.4f}')


if __name__ == "__main__":
    main()
