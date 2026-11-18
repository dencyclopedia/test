#!/bin/bash
# Survey of third-party Tesseract images on Docker Hub: search, then pull the 3 most-pulled
# and report compressed/uncompressed size, last push and the tesseract version inside.
set -u
OUT=$1; mkdir -p "$OUT"
curl -sS "https://hub.docker.com/v2/search/repositories/?query=tesseract&page_size=50" > "$OUT/hub-search.json"
python3 - "$OUT/hub-search.json" > "$OUT/hub-search.tsv" <<'PY'
import json,sys
d=json.load(open(sys.argv[1]))
print("repo\tpull_count\tstar_count\tis_official\tdescription")
for r in sorted(d.get('results',[]), key=lambda r:-r.get('pull_count',0)):
    print(f"{r['repo_name']}\t{r.get('pull_count')}\t{r.get('star_count')}\t{r.get('is_official')}\t{(r.get('short_description') or '').replace(chr(9),' ')[:100]}")
PY
cat "$OUT/hub-search.tsv" | head -25
printf 'image\ttag_last_pushed\tcompressed_bytes\tuncompressed_bytes\tpull_seconds\ttesseract_version_line\tleptonica\n' > "$OUT/images.tsv"
for repo in $(tail -n +2 "$OUT/hub-search.tsv" | head -3 | cut -f1); do
  curl -sS "https://hub.docker.com/v2/repositories/$repo/tags/latest" > "$OUT/tag-${repo//\//_}.json"
  pushed=$(python3 -c "import json;d=json.load(open('$OUT/tag-${repo//\//_}.json'));print(d.get('tag_last_pushed') or d.get('last_updated') or d.get('message'))")
  comp=$(python3 -c "import json;d=json.load(open('$OUT/tag-${repo//\//_}.json'));print(d.get('full_size'))")
  s=$(date +%s.%N); docker pull -q "$repo:latest" > /dev/null 2>"$OUT/pullerr-${repo//\//_}.txt"; e=$(date +%s.%N)
  size=$(docker image inspect "$repo:latest" --format '{{.Size}}' 2>/dev/null || echo NA)
  vout=$(docker run --rm --entrypoint tesseract "$repo:latest" --version 2>&1 || docker run --rm --entrypoint sh "$repo:latest" -c 'tesseract --version' 2>&1)
  echo "=== $repo:latest" >> "$OUT/versions.txt"; echo "$vout" >> "$OUT/versions.txt"
  docker run --rm --entrypoint tesseract "$repo:latest" --list-langs >> "$OUT/versions.txt" 2>&1
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$repo:latest" "$pushed" "$comp" "$size" "$(python3 -c "print(round($e-$s,1))")" "$(echo "$vout" | grep -m1 -i '^tesseract')" "$(echo "$vout" | grep -m1 -io 'leptonica-[0-9.]*')" >> "$OUT/images.tsv"
done
cat "$OUT/images.tsv"
