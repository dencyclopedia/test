"""Small asyncio load generator for the OCR API (httpx).

usage:
  python3 loadtest.py closed URL IMAGE --concurrency 8 --requests 32      # closed loop -> RPS, p50/p95
  python3 loadtest.py burst  URL IMAGE --concurrency 8 --repeats 5         # N simultaneous requests, repeated
  python3 loadtest.py coldstart IMAGE_TAG IMAGE --repeats 5                 # docker run -> first OCR 200
Prints one JSON object (all per-request latencies and status codes are included).
"""
import argparse, asyncio, json, statistics, subprocess, time
import httpx


def pct(xs, p):
    xs = sorted(xs)
    if not xs:
        return None
    k = (len(xs) - 1) * p / 100
    f = int(k); c = min(f + 1, len(xs) - 1)
    return round(xs[f] + (xs[c] - xs[f]) * (k - f), 3)


async def one(client, url, data):
    t = time.perf_counter()
    try:
        r = await client.post(url, files={"file": ("img.png", data, "image/png")}, timeout=120)
        code = r.status_code
    except Exception as e:  # noqa
        code = f"exc:{type(e).__name__}"
    return code, time.perf_counter() - t


async def closed(url, data, conc, n):
    q = asyncio.Queue()
    for _ in range(n):
        q.put_nowait(1)
    res = []
    async with httpx.AsyncClient() as c:
        async def worker():
            while not q.empty():
                q.get_nowait()
                res.append(await one(c, url, data))
        t = time.perf_counter()
        await asyncio.gather(*[worker() for _ in range(conc)])
        wall = time.perf_counter() - t
    lat = [l for code, l in res if code == 200]
    return {"mode": "closed", "concurrency": conc, "requests": n, "wall_s": round(wall, 3),
            "ok": len(lat), "rps_ok": round(len(lat) / wall, 3),
            "p50_s": pct(lat, 50), "p95_s": pct(lat, 95), "max_s": pct(lat, 100),
            "status_counts": {str(k): sum(1 for c, _ in res if c == k) for k in {c for c, _ in res}},
            "all": [[str(c), round(l, 3)] for c, l in res]}


async def burst(url, data, conc, repeats):
    out = []
    async with httpx.AsyncClient() as c:
        await one(c, url, data)  # warm-up
        for _ in range(repeats):
            t = time.perf_counter()
            res = await asyncio.gather(*[one(c, url, data) for _ in range(conc)])
            out.append({"wall_s": round(time.perf_counter() - t, 3),
                        "requests": [[str(code), round(l, 3)] for code, l in res]})
    allres = [r for b in out for r in b["requests"]]
    lat_ok = [l for code, l in allres if code == "200"]
    return {"mode": "burst", "concurrency": conc, "repeats": repeats,
            "ok": len(lat_ok), "total": len(allres),
            "status_counts": {k: sum(1 for c, _ in allres if c == k) for k in {c for c, _ in allres}},
            "p50_s_ok": pct(lat_ok, 50), "max_s_ok": pct(lat_ok, 100),
            "max_s_any": pct([l for _, l in allres], 100), "bursts": out}


def coldstart(tag, data, repeats, port=8099):
    url = f"http://127.0.0.1:{port}/ocr?lang=eng"
    times = []
    for i in range(repeats + 1):
        subprocess.run(["docker", "rm", "-f", "cold"], capture_output=True)
        t = time.perf_counter()
        subprocess.run(["docker", "run", "-d", "--name", "cold", "-p", f"{port}:8000", tag], check=True, capture_output=True)
        while True:
            try:
                r = httpx.post(url, files={"file": ("r.png", data, "image/png")}, timeout=30)
                if r.status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            if time.perf_counter() - t > 120:
                raise SystemExit("no response in 120 s")
            time.sleep(0.02)
        dt = time.perf_counter() - t
        if i > 0:  # first run is the warm-up
            times.append(dt)
    subprocess.run(["docker", "rm", "-f", "cold"], capture_output=True)
    return {"mode": "coldstart", "image": tag, "repeats": repeats,
            "median_s": round(statistics.median(times), 3), "min_s": round(min(times), 3),
            "max_s": round(max(times), 3), "all_s": [round(x, 3) for x in times],
            "measures": "time from `docker run -d` to the first HTTP 200 from POST /ocr (receipt image), polled every 20 ms"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode"); ap.add_argument("target"); ap.add_argument("image")
    ap.add_argument("--concurrency", type=int, default=8); ap.add_argument("--requests", type=int, default=32)
    ap.add_argument("--repeats", type=int, default=5)
    a = ap.parse_args()
    data = open(a.image, "rb").read()
    if a.mode == "closed":
        r = asyncio.run(closed(a.target, data, a.concurrency, a.requests))
    elif a.mode == "burst":
        r = asyncio.run(burst(a.target, data, a.concurrency, a.repeats))
    else:
        r = coldstart(a.target, data, a.repeats)
    print(json.dumps(r))


if __name__ == "__main__":
    main()
