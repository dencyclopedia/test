"""Python OCR throughput: pytesseract per call vs multiprocessing pools vs tesserocr (reused API) vs one
multi-page TIFF call.

usage: python3 run_throughput.py IMGDIR RESULTS.json [--runs 5] [--repeat 3]
IMGDIR = output of bench/bindings/make_images.py (10 images, 2481x1170 px, 300 DPI). The 10 images are
repeated --repeat times (default 3 -> 30 images per run). Each strategy: 1 warm-up run, then --runs timed runs;
images/s = n_images / median wall time. OMP_THREAD_LIMIT=1 unless the row says otherwise.
"""
import argparse, glob, json, os, statistics, subprocess, sys, tempfile, time
from multiprocessing import get_context

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools"))
import metrics  # noqa: E402

TD = os.environ.get("TESSDATA_DIR", "/opt/tessdata/tessdata_fast")
BUDGET_S = int(os.environ.get("BUDGET_S", "600"))


def pyt_one(path):
    import pytesseract
    from PIL import Image
    return pytesseract.image_to_string(Image.open(path), lang="eng", config=f"--tessdata-dir {TD}")


_api = None


def _init_tesserocr():
    global _api
    import tesserocr
    _api = tesserocr.PyTessBaseAPI(path=TD, lang="eng")


def tesserocr_one(path):
    _api.SetImageFile(path)
    return _api.GetUTF8Text()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("imgdir"); ap.add_argument("out")
    ap.add_argument("--runs", type=int, default=5); ap.add_argument("--repeat", type=int, default=3)
    a = ap.parse_args()
    base = sorted(glob.glob(os.path.join(a.imgdir, "img-*.png")))
    imgs = base * a.repeat
    n = len(imgs)
    gts = {p: open(p[:-4] + ".gt.txt").read() for p in base}
    tmp = tempfile.mkdtemp()
    # one multi-page TIFF and one image list holding the same n images
    from PIL import Image
    tif = os.path.join(tmp, "all.tif")
    ims = [Image.open(p) for p in imgs]
    ims[0].save(tif, save_all=True, append_images=ims[1:], compression="tiff_lzw", dpi=(300, 300))
    lst = os.path.join(tmp, "list.txt"); open(lst, "w").write("\n".join(imgs) + "\n")

    def per_call():
        return [pyt_one(p) for p in imgs]

    def pool(k):
        def f():
            with get_context("fork").Pool(k) as pl:
                return pl.map(pyt_one, imgs)
        return f

    def tesserocr_single():
        _init_tesserocr()
        return [tesserocr_one(p) for p in imgs]

    def tesserocr_pool(k):
        def f():
            # 'spawn', not 'fork': forking after the parent has run tesserocr (libgomp initialised) hung the
            # first Actions run (fork + OpenMP); see README
            with get_context("spawn").Pool(k, initializer=_init_tesserocr) as pl:
                return pl.map(tesserocr_one, imgs)
        return f

    def cli_multi(target):
        def f():
            out = subprocess.run(["tesseract", target, "stdout", "--tessdata-dir", TD, "-l", "eng"],
                                 capture_output=True, text=True, check=True).stdout
            return out.split("\f")
        return f

    def pyt_multipage():
        import pytesseract
        return pytesseract.image_to_string(tif, lang="eng", config=f"--tessdata-dir {TD}").split("\f")

    strategies = [
        ("pytesseract per call (loop)", per_call, {}),
        ("pytesseract + multiprocessing.Pool(1)", pool(1), {}),
        ("pytesseract + multiprocessing.Pool(2)", pool(2), {}),
        ("pytesseract + multiprocessing.Pool(4)", pool(4), {}),
        ("tesserocr, one PyTessBaseAPI reused", tesserocr_single, {}),
        ("tesserocr, Pool(4), one API per worker", tesserocr_pool(4), {}),
        ("pytesseract on one multi-page TIFF (single call)", pyt_multipage, {}),
        ("tesseract CLI on one multi-page TIFF (single call)", cli_multi(tif), {}),
        ("tesseract CLI on an image list (single call)", cli_multi(lst), {}),
        ("pytesseract per call (loop), OMP_THREAD_LIMIT unset", per_call, {"unset_omp": True}),
        ("pytesseract + Pool(4), OMP_THREAD_LIMIT unset", pool(4), {"unset_omp": True}),
    ]
    rows = []
    for name, fn, o in strategies:
        if o.get("unset_omp"):
            os.environ.pop("OMP_THREAD_LIMIT", None)
        else:
            os.environ["OMP_THREAD_LIMIT"] = "1"
        import signal

        def _alarm(*_):
            raise TimeoutError
        signal.signal(signal.SIGALRM, _alarm)
        signal.alarm(BUDGET_S)  # whole strategy (warm-up + runs); OMP-unset strategies can be pathologically slow
        ts, t0 = [], time.perf_counter()
        try:
            texts = fn()  # warm-up
            for _ in range(a.runs):
                t = time.perf_counter(); fn(); ts.append(time.perf_counter() - t)
        except TimeoutError:
            rows.append({"strategy": name, "omp_thread_limit": "unset" if o.get("unset_omp") else "1", "images": n,
                         "status": f"stopped after {BUDGET_S} s budget", "completed_timed_runs_s": [round(x, 3) for x in ts],
                         "elapsed_s": round(time.perf_counter() - t0, 1)})
            print(json.dumps(rows[-1]), flush=True)
            subprocess.run(["pkill", "-x", "tesseract"], capture_output=True)
            continue
        finally:
            signal.alarm(0)
        texts = [t for t in texts if t.strip()][:len(base)]
        cer = statistics.mean(metrics.cer(gts[p], t) for p, t in zip(base, texts)) if len(texts) == len(base) else None
        row = {"strategy": name, "omp_thread_limit": "unset" if o.get("unset_omp") else "1", "images": n,
               "median_s": round(statistics.median(ts), 3), "min_s": round(min(ts), 3), "max_s": round(max(ts), 3),
               "images_per_s": round(n / statistics.median(ts), 3), "cer_mean_first10": round(cer, 5) if cer is not None else None,
               "all_s": [round(x, 3) for x in ts]}
        print(json.dumps(row), flush=True)
        rows.append(row)
    os.environ["OMP_THREAD_LIMIT"] = "1"
    json.dump(rows, open(a.out, "w"), indent=2)


if __name__ == "__main__":
    main()
