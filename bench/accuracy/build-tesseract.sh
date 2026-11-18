#!/usr/bin/env bash
# Build Tesseract 5.5.4 from the upstream tag into /opt/tess554 (no training tools) and fetch the pinned models
# into /opt/tessdata/{tessdata_fast,tessdata,tessdata_best}. Used by the bench-* timing workflows on ubuntu-24.04.
# Skips the build when /opt/tess554/bin/tesseract already reports 5.5.4 (restored from the Actions cache).
set -euo pipefail
PREFIX=/opt/tess554
LANGS="${LANGS:-eng osd deu fra rus chi_sim ara}"
declare -A COMMIT=(
  [tessdata_fast]=87416418657359cb625c412a48b6e1d6d41c29bd
  [tessdata]=ced78752cc61322fb554c280d13360b35b8684e4
  [tessdata_best]=e12c65a915945e4c28e237a9b52bc4a8f39a0cec
)
sudo apt-get update -qq
sudo apt-get install -y -qq --no-install-recommends build-essential autoconf automake libtool pkg-config \
  libleptonica-dev libpng-dev libjpeg-dev libtiff-dev zlib1g-dev libwebp-dev libopenjp2-7-dev libgif-dev \
  libarchive-dev libcurl4-openssl-dev git >/dev/null
if ! "$PREFIX/bin/tesseract" --version 2>/dev/null | grep -q '^tesseract 5.5.4'; then
  src=$(mktemp -d)
  git clone -q --depth 1 --branch 5.5.4 https://github.com/tesseract-ocr/tesseract.git "$src"
  (cd "$src" && ./autogen.sh >/dev/null && ./configure --prefix="$PREFIX" --disable-doc >/dev/null \
     && make -j"$(nproc)" >/dev/null && make install >/dev/null)
  git -C "$src" rev-parse HEAD > "$PREFIX/SOURCE_COMMIT"
fi
"$PREFIX/bin/tesseract" --version
for repo in "${!COMMIT[@]}"; do
  d=/opt/tessdata/$repo; mkdir -p "$d"
  echo "${COMMIT[$repo]}" > "$d/COMMIT"
  for l in $LANGS; do
    [ -s "$d/$l.traineddata" ] || curl -fsSL -o "$d/$l.traineddata" \
      "https://raw.githubusercontent.com/tesseract-ocr/$repo/${COMMIT[$repo]}/$l.traineddata"
  done
done
ls -l /opt/tessdata/*
