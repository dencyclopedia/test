#!/usr/bin/env bash
# Build Tesseract 5.5.4 (upstream tag) with training tools into $PREFIX (default /opt/tess554)
# and fetch models pinned by commit. Used by every bench-*.yml workflow on ubuntu-24.04.
# The install dir is cached by actions/cache; if $PREFIX/bin/lstmtraining exists the build is skipped.
set -euo pipefail
PREFIX=${PREFIX:-/opt/tess554}
TAG=5.5.4
TESSDATA_ROOT=${TESSDATA_ROOT:-/opt/tessdata}
FAST_SHA=87416418657359cb625c412a48b6e1d6d41c29bd
STD_SHA=ced78752cc61322fb554c280d13360b35b8684e4
BEST_SHA=e12c65a915945e4c28e237a9b52bc4a8f39a0cec
LANGS=${LANGS:-"eng deu osd"}

sudo apt-get update -qq
sudo apt-get install -y -qq --no-install-recommends \
  autoconf automake libtool pkg-config g++ make git curl \
  libleptonica-dev libarchive-dev libcurl4-openssl-dev \
  libicu-dev libpango1.0-dev libcairo2-dev >/dev/null

if [ ! -x "$PREFIX/bin/lstmtraining" ]; then
  src=$(mktemp -d)
  git clone -q --depth 1 -b "$TAG" https://github.com/tesseract-ocr/tesseract "$src"
  (cd "$src" && ./autogen.sh >/dev/null && ./configure -q --prefix="$PREFIX" --disable-doc \
     && make -s -j"$(nproc)" && make -s -j"$(nproc)" training \
     && make -s install && make -s training-install)
  rm -rf "$src"
fi
echo "$PREFIX/lib" | sudo tee /etc/ld.so.conf.d/tess554.conf >/dev/null
sudo ldconfig

for kind in fast std best; do
  case $kind in
    fast) repo=tessdata_fast; sha=$FAST_SHA; dir=$TESSDATA_ROOT/tessdata_fast;;
    std)  repo=tessdata;      sha=$STD_SHA;  dir=$TESSDATA_ROOT/tessdata;;
    best) repo=tessdata_best; sha=$BEST_SHA; dir=$TESSDATA_ROOT/tessdata_best;;
  esac
  sudo mkdir -p "$dir"; sudo chown "$(id -u)" "$dir"
  for l in $LANGS; do
    [ -s "$dir/$l.traineddata" ] || curl -fsSL -o "$dir/$l.traineddata" \
      "https://raw.githubusercontent.com/tesseract-ocr/$repo/$sha/$l.traineddata"
  done
  # the model dirs hold only *.traineddata; link configs/ and pdf.ttf in, or `tesseract ... pdf`
  # prints "read_params_file: Can't open pdf" and writes only a .txt (see bench/errors)
  ln -sfn "$PREFIX/share/tessdata/configs" "$dir/configs"
  ln -sf "$PREFIX/share/tessdata/pdf.ttf" "$dir/pdf.ttf"
done
"$PREFIX/bin/tesseract" --version
