#!/bin/bash
# Host side (ubuntu-24.04 runner). Usage: run-distro.sh <flavour> <image> <outdir>
set -u
F=$1; IMG=$2; OUT=$3
HERE=$(cd "$(dirname "$0")" && pwd); REPO=$(cd "$HERE/../.." && pwd)
mkdir -p "$OUT"
s=$(date +%s.%N); docker pull -q "$IMG" > "$OUT/pull.txt" 2>&1; e=$(date +%s.%N)
echo "pull_seconds=$(python3 -c "print(round($e - $s, 2))")" > "$OUT/host.txt"
docker image inspect "$IMG" --format 'image_id={{.Id}} image_size_bytes={{.Size}} created={{.Created}} digest={{index .RepoDigests 0}}' >> "$OUT/host.txt"
python3 "$REPO/install/scripts/castrec.py" "$OUT/session.cast" "Tesseract install on $F ($IMG)" -- \
  docker run --rm -t --hostname "$F" -v "$REPO/samples:/samples:ro" -v "$HERE/in-container.sh:/in-container.sh:ro" -v "$(realpath "$OUT"):/out" \
  "$IMG" sh /in-container.sh "$F"
echo "container_exit=$?" >> "$OUT/host.txt"
cat "$OUT/host.txt" "$OUT/steps.tsv" "$OUT/notes.txt" 2>/dev/null
