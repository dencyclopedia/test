# The FastAPI service from tesseractocr.org/api/ ("A production Python service"), copied verbatim except:
#   - pool size comes from POOL_WORKERS (default 4, as on the page) so the bench can vary it
#   - LANGS comes from OCR_LANGS (default "eng deu", as on the page)
import asyncio, io, os
from concurrent.futures import ProcessPoolExecutor
from fastapi import FastAPI, File, UploadFile, HTTPException, Query
from PIL import Image
import pytesseract

app = FastAPI(title="Tesseract OCR API")
pool = ProcessPoolExecutor(max_workers=int(os.environ.get("POOL_WORKERS", "4")))  # workers x pool size = CPU cores
MAX_BYTES = 10 * 1024 * 1024  # 10 MB
LANGS = set(os.environ.get("OCR_LANGS", "eng deu").split())  # the language packs in the image


def _ocr(data: bytes, lang: str) -> str:
    image = Image.open(io.BytesIO(data))
    return pytesseract.image_to_string(image, lang=lang, timeout=25)  # kills a stuck tesseract


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ocr")
async def ocr(file: UploadFile = File(...), lang: str = Query("eng")):
    if lang not in LANGS:
        raise HTTPException(400, "Unsupported language")
    data = await file.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "File too large")
    loop = asyncio.get_running_loop()
    try:
        text = await asyncio.wait_for(loop.run_in_executor(pool, _ocr, data, lang), timeout=30)
    except (asyncio.TimeoutError, RuntimeError):
        raise HTTPException(504, "OCR timed out")
    return {"text": text, "lang": lang}
