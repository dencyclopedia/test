#!/usr/bin/env bash
# Two checks for tesseractocr.org/about/:
#  1. release history: upstream git tags and their dates (git, no API)
#  2. "does Tesseract phone home?": OCR with no network at all (unshare -n) + every syscall traced (strace -f)
# Usage: sudo bash bench/about/run.sh   (from the repo root; unshare -n needs root)
set -u
cd "$(dirname "$0")/../.."
OUT=bench/about/results; mkdir -p "$OUT"
T=/opt/tess554/bin/tesseract
TD=/opt/tessdata/tessdata
IMG=corpus/receipt/receipt01_dejavu-mono.png
W=$(mktemp -d)

# 1. tags (lightweight tags have no tagger date: their commit date is used)
git clone -q --bare --filter=tree:0 https://github.com/tesseract-ocr/tesseract "$W/tess.git"
{ printf 'tag\ttype\tdate\n'
  git -C "$W/tess.git" for-each-ref refs/tags --sort=creatordate \
    --format='%(refname:short)	%(objecttype)	%(taggerdate:short)%(if)%(taggerdate)%(then)%(else)%(committerdate:short)%(end)'
} > "$OUT/tags.tsv"

# 2. offline OCR
{
  echo "date_utc: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "machine: development container, $(grep -m1 'model name' /proc/cpuinfo | cut -d: -f2 | sed 's/^ //'), $(. /etc/os-release; echo "$PRETTY_NAME")"
  $T --version 2>&1 | head -2
  echo "strace: $(strace -V | head -1)"
} > "$OUT/offline-meta.txt"
{
  echo '$ unshare -n -- sh -c "cat /proc/net/dev; getent hosts github.com || echo DNS: no answer"'
  unshare -n -- sh -c 'cat /proc/net/dev; getent hosts github.com || echo "DNS: no answer"' 2>&1
  echo '$ unshare -n -- tesseract receipt01_dejavu-mono.png stdout -l eng --oem 1 --psm 6'
  unshare -n -- $T "$IMG" stdout --tessdata-dir $TD -l eng --oem 1 --psm 6 2>&1; echo "exit=$?"
} > "$OUT/offline-run.txt"
# strace with networking ON (normal machine): does it even try to open a socket?
strace -f -qq -e trace=network -o "$OUT/strace-network.txt" $T "$IMG" "$W/o" --tessdata-dir $TD -l eng --oem 1 --psm 6 >/dev/null 2>&1
echo "exit=$?" > "$OUT/strace-network-exit.txt"
strace -f -qq -c -o "$OUT/strace-summary.txt" $T "$IMG" "$W/o2" --tessdata-dir $TD -l eng --oem 1 --psm 6 >/dev/null 2>&1
strace -f -qq -e trace=openat -o "$W/open.txt" $T "$IMG" "$W/o3" --tessdata-dir $TD -l eng --oem 1 --psm 6 >/dev/null 2>&1
grep -v ENOENT "$W/open.txt" | grep -o '"[^"]*"' | sort -u | sed "s#$W#<tmp>#" > "$OUT/strace-files-opened.txt"
wc -l < "$OUT/strace-network.txt" > "$OUT/strace-network-count.txt"
echo done
