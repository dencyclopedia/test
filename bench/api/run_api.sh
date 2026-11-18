#!/usr/bin/env bash
# OCR API bench: load test matrix on the host, the /api/ page's OMP_THREAD_LIMIT claim inside the page's
# own Docker image, Docker image-size matrix, container cold start, curl transcript.
# usage: run_api.sh WORKDIR RESULTS_DIR   (needs docker, python venv with requirements + httpx, tesseract on PATH)
set -euo pipefail
W=$(realpath -m "$1"); RES=$(realpath -m "$2"); HERE=$(cd "$(dirname "$0")" && pwd)
PARTS=${PARTS:-"host docker sizes curl"}
mkdir -p "$W" "$RES/raw"
PY=${PY:-python3}

# --- inputs (synthetic): an A4 300-DPI page (PNG) and a till receipt (PNG)
$PY - "$W" "$RES" "$HERE/../pdf" <<'EOF'
import sys, os, json
sys.path.insert(0, sys.argv[3])
import scanlib
w, res = sys.argv[1:3]
lines = scanlib.layout_pages(n_pages=1)[0]
im = scanlib.degrade(scanlib.render_lines(lines), seed=1001)
im.save(f"{w}/a4.png", dpi=(300, 300))
r, gt = scanlib.render_receipt()
r.save(f"{w}/receipt.png", dpi=(200, 200)); r.save(f"{res}/raw/receipt.png", dpi=(200, 200))
open(f"{res}/raw/receipt.gt.txt", "w").write(gt)
json.dump({"a4.png": {"bytes": os.path.getsize(f"{w}/a4.png"), "size_px": im.size, "dpi": 300,
                      "synthetic": True, "text": "Pride and Prejudice ch.1, Liberation Serif 11 pt, seeded scan noise"},
           "receipt.png": {"bytes": os.path.getsize(f"{w}/receipt.png"), "size_px": r.size, "dpi": 200,
                           "synthetic": True}}, open(f"{res}/inputs.json", "w"), indent=2)
EOF

PORT=8100
start_server() {  # $1 pool size, $2 OMP (unset|1); a fresh port each time (a pool child that outlives the
                  # server keeps the old listening socket open, and requests to it then hang: first Actions run)
  PORT=$((PORT + 1))
  local envs
  if [ "$2" = "unset" ]; then envs=(-u OMP_THREAD_LIMIT POOL_WORKERS="$1"); else envs=(POOL_WORKERS="$1" OMP_THREAD_LIMIT="$2"); fi
  (cd "$HERE" && env "${envs[@]}" $PY -m uvicorn app:app --host 127.0.0.1 --port $PORT > "$W/uvicorn.log" 2>&1 &)
  for _ in $(seq 100); do curl -fs -m 2 http://127.0.0.1:$PORT/health >/dev/null && return 0; sleep 0.2; done
  echo "server did not start"; cat "$W/uvicorn.log"; exit 1
}
stop_server() { pkill -9 -f "uvicorn app:app" || true; sleep 2; }

if [[ " $PARTS " == *" host "* ]]; then
  rm -f "$RES/host_matrix.jsonl"
  for pool in 1 2 4; do for omp in unset 1; do
    stop_server; start_server "$pool" "$omp"
    for img in a4 receipt; do
      if [ "$img" = a4 ]; then n=24; else n=80; fi
      b=$($PY "$HERE/loadtest.py" burst "http://127.0.0.1:$PORT/ocr?lang=eng" "$W/$img.png" --concurrency 8 --repeats 5)
      c=$($PY "$HERE/loadtest.py" closed "http://127.0.0.1:$PORT/ocr?lang=eng" "$W/$img.png" --concurrency 8 --requests $n)
      $PY -c "import json,sys; print(json.dumps({'where':'host','pool':$pool,'omp_thread_limit':'$omp','image':'$img','burst8':json.loads(sys.argv[1]),'closed8':json.loads(sys.argv[2])}))" "$b" "$c" | tee -a "$RES/host_matrix.jsonl" | cut -c1-300
    done
  done; done
  stop_server
fi

if [[ " $PARTS " == *" docker "* ]]; then
  # the page's Dockerfile exactly, and the same file without the ENV OMP_THREAD_LIMIT=1 line
  B="$W/build"; rm -rf "$B"; mkdir -p "$B"; cp "$HERE/app.py" "$HERE/requirements.txt" "$B/"
  cp "$HERE/docker/Dockerfile.page" "$B/Dockerfile.page"
  grep -v '^ENV OMP_THREAD_LIMIT' "$HERE/docker/Dockerfile.page" > "$B/Dockerfile.page-noomp"
  sed 's/tesseract-ocr-deu \\/tesseract-ocr-deu libgl1 libglib2.0-0 \\/' "$HERE/docker/Dockerfile.page" > "$B/Dockerfile.page-opencv-libs"
  for v in page page-noomp page-opencv-libs; do
    docker build -q -t "ocrapi:$v" -f "$B/Dockerfile.$v" "$B" > /dev/null
  done
  docker run --rm --entrypoint sh ocrapi:page -c 'tesseract --version 2>&1 | head -3; cat /etc/debian_version; python --version; pip freeze' > "$RES/page-image-versions.txt" 2>&1
  rm -f "$RES/docker_claim.jsonl"
  for v in page page-noomp; do
    docker rm -f api >/dev/null 2>&1 || true
    docker run -d --name api -p 8000:8000 "ocrapi:$v" >/dev/null
    for _ in $(seq 150); do curl -fs -m 2 http://127.0.0.1:8000/health >/dev/null && break; sleep 0.2; done
    docker exec api sh -c 'echo "OMP_THREAD_LIMIT=${OMP_THREAD_LIMIT:-<unset>} nproc=$(nproc)"' > "$RES/raw/docker-$v-env.txt"
    for img in a4 receipt; do
      b=$($PY "$HERE/loadtest.py" burst "http://127.0.0.1:8000/ocr?lang=eng" "$W/$img.png" --concurrency 8 --repeats 5)
      $PY -c "import json,sys; print(json.dumps({'where':'docker','image_tag':'ocrapi:$v','pool':4,'image':'$img','burst8':json.loads(sys.argv[1])}))" "$b" | tee -a "$RES/docker_claim.jsonl" | cut -c1-300
    done
    docker logs api > "$RES/raw/docker-$v.log" 2>&1 || true
    docker rm -f api >/dev/null
  done
  for v in page page-noomp page-opencv-libs; do
    echo "{\"tag\":\"ocrapi:$v\",\"bytes\":$(docker image inspect -f '{{.Size}}' ocrapi:$v)}"
  done > "$RES/page_image_sizes.jsonl"
fi

if [[ " $PARTS " == *" sizes "* ]]; then
  M="$W/matrix"; rm -rf "$M"; mkdir -p "$M"; cp "$HERE/app.py" "$HERE/requirements.txt" "$M/"
  $PY "$HERE/docker/gen_dockerfiles.py" "$M" > "$M/names.txt"
  rm -f "$RES/image_matrix.jsonl"
  while read -r n; do
    t0=$(date +%s.%N)
    if ! docker build -q -t "m:$n" -f "$M/Dockerfile.$n" "$M" > "$M/$n.build.log" 2>&1; then
      echo "{\"name\":\"$n\",\"status\":\"build failed\",\"log\":$(tail -c 1500 "$M/$n.build.log" | $PY -c 'import json,sys;print(json.dumps(sys.stdin.read()))')}" >> "$RES/image_matrix.jsonl"; continue
    fi
    t1=$(date +%s.%N)
    size=$(docker image inspect -f '{{.Size}}' "m:$n")
    info=$(docker run --rm --entrypoint sh "m:$n" -c 'tesseract --version 2>&1 | head -1; for f in $(tesseract --list-langs 2>/dev/null | tail -n +2); do :; done; d=$(dirname $(find / -name eng.traineddata 2>/dev/null | head -1)); ls -l $d/*.traineddata | awk "{print \$5, \$9}"; python --version')
    cold=$($PY "$HERE/loadtest.py" coldstart "m:$n" "$W/receipt.png" --repeats 5)
    $PY - "$n" "$size" "$info" "$cold" "$t0" "$t1" >> "$RES/image_matrix.jsonl" <<'EOF'
import json, sys
n, size, info, cold, t0, t1 = sys.argv[1:]
base, langs, model = n.rsplit("-", 2)
print(json.dumps({"name": n, "base": base, "langs": langs, "model": model, "bytes": int(size),
                  "mb": round(int(size) / 1e6, 1), "inside": info.splitlines(), "build_s": round(float(t1) - float(t0), 1),
                  "coldstart": json.loads(cold), "status": "ok"}))
EOF
    tail -1 "$RES/image_matrix.jsonl" | cut -c1-250
  done < "$M/names.txt"
  cp "$M"/Dockerfile.* "$RES/raw/" 2>/dev/null || true
fi

if [[ " $PARTS " == *" curl "* ]]; then
  docker rm -f api >/dev/null 2>&1 || true
  docker run -d --name api -p 8000:8000 ocrapi:page >/dev/null
  for _ in $(seq 150); do curl -fs -m 2 http://127.0.0.1:8000/health >/dev/null && break; sleep 0.2; done
  cp "$W/receipt.png" "$W/invoice.png"
  {
    cd "$W"
    for c in 'curl -sS -i -F "file=@receipt.png" "http://localhost:8000/ocr?lang=eng"' \
             'curl -sS -i -F "file=@receipt.png" "http://localhost:8000/ocr?lang=fra"' \
             'curl -sS -i http://localhost:8000/health'; do
      echo "\$ $c"; eval "$c"; echo; echo
    done
    head -c 11000000 /dev/urandom > big.bin
    echo '$ curl -sS -i -F "file=@big.bin" "http://localhost:8000/ocr?lang=eng"   # 11 MB file'
    curl -sS -i -F "file=@big.bin" "http://localhost:8000/ocr?lang=eng"; echo; echo
    printf 'not an image' > bad.png
    echo '$ curl -sS -i -F "file=@bad.png" "http://localhost:8000/ocr?lang=eng"'
    curl -sS -i -F "file=@bad.png" "http://localhost:8000/ocr?lang=eng"; echo
  } > "$RES/curl-transcript.txt" 2>&1
  curl -sS -F "file=@$W/receipt.png" "http://localhost:8000/ocr?lang=eng" > "$RES/response.json"
  docker logs api > "$RES/raw/curl-server.log" 2>&1
  docker rm -f api >/dev/null
fi
echo done
