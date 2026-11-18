"""Python harnesses: cli (subprocess tesseract), pytesseract, tesserocr. Common protocol, see ../README.md.
usage: python3 harness.py MODE TESSDATA LANG PSM PASSES TINY IMG...   (PSM = 'default' or a number)"""
import json, os, subprocess, sys, time

mode, td, lang, psm, passes, tiny, *imgs = sys.argv[1:]
passes = int(passes)
T = os.environ.get("TESSERACT", "tesseract")
info, init_s = {}, None

if mode == "cli":
    def ocr(p):
        cmd = [T, p, "stdout", "--tessdata-dir", td, "-l", lang] + ([] if psm == "default" else ["--psm", psm])
        return subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    info["engine"] = subprocess.run([T, "--version"], capture_output=True, text=True).stdout.splitlines()[0]
elif mode == "pytesseract":
    import pytesseract
    from PIL import Image
    cfg = f"--tessdata-dir {td}" + ("" if psm == "default" else f" --psm {psm}")
    def ocr(p):
        return pytesseract.image_to_string(Image.open(p), lang=lang, config=cfg)
    info["pytesseract"] = pytesseract.__version__ if hasattr(pytesseract, "__version__") else "?"
    info["engine"] = str(pytesseract.get_tesseract_version())
elif mode == "tesserocr":
    import tesserocr
    t = time.perf_counter()
    kw = {} if psm == "default" else {"psm": int(psm)}
    api = tesserocr.PyTessBaseAPI(path=td, lang=lang, **kw)
    init_s = time.perf_counter() - t
    def ocr(p):
        api.SetImageFile(p)
        return api.GetUTF8Text()
    info["tesserocr"] = tesserocr.__version__
    info["engine"] = tesserocr.tesseract_version().splitlines()[0] + " / " + tesserocr.tesseract_version().splitlines()[1].strip()
    info["default_psm"] = str(api.GetPageSegMode())
else:
    raise SystemExit("mode?")

ocr(tiny)  # warm-up
tiny_s = []
for _ in range(20):
    t = time.perf_counter(); ocr(tiny); tiny_s.append(time.perf_counter() - t)
texts = [ocr(p) for p in imgs]  # warm-up pass, also the texts compared for identity
pass_s = []
for _ in range(passes):
    row = []
    for p in imgs:
        t = time.perf_counter(); ocr(p); row.append(time.perf_counter() - t)
    pass_s.append(row)
print(json.dumps({"binding": mode, "info": info, "init_s": init_s, "tiny_s": tiny_s, "pass_s": pass_s, "texts": texts}))
