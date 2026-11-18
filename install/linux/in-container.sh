#!/bin/sh
# Runs INSIDE a clean distro container. Usage: in-container.sh <flavour>
# Prints a shell-like transcript (prompt + command + real output). Timings of each step go
# to /out/steps.tsv (seconds from /proc/uptime, 10 ms resolution).
F="$1"
OUT=/out
HOSTN="$F"
printf 'step\tseconds\texit\tcommand\n' > $OUT/steps.tsv
now() { cut -d' ' -f1 /proc/uptime; }
step() {  # step NAME COMMAND...
  name="$1"; shift
  printf '\033[1;32mroot@%s\033[0m:\033[1;34m/\033[0m# %s\n' "$HOSTN" "$*"
  s=$(now); sh -c "$*"; rc=$?; e=$(now)
  printf '%s\t%s\t%s\t%s\n' "$name" "$(awk -v a="$s" -v b="$e" 'BEGIN{printf "%.2f", b-a}')" "$rc" "$*" >> $OUT/steps.tsv
  return $rc
}
rootkb() { du -skx / 2>/dev/null | cut -f1; }
note() { printf '%s\n' "$*" >> $OUT/notes.txt; }

cat /etc/os-release > $OUT/os-release.txt 2>/dev/null
note "rootfs_kb_before=$(rootkb)"
step os "cat /etc/os-release | head -4"
step which-before "command -v tesseract || echo 'tesseract: not installed'"
step run-before "tesseract --version"

case "$F" in
  ubuntu-22.04|ubuntu-24.04|debian-12|debian-13)
    export DEBIAN_FRONTEND=noninteractive
    step update "apt-get update"
    step policy "apt-cache policy tesseract-ocr"
    step install "apt-get install -y tesseract-ocr"
    step clean "apt-get clean"
    step pkgs "dpkg-query -W -f='\${Package} \${Version} \${Installed-Size}KiB\n' | grep -Ei 'tesseract|lept|libarchive|libtiff|libwebp|libgif|libpng|libjpeg|libopenjp|libicu|libpango|libcairo'"
    step langs-search "apt-cache search --names-only '^tesseract-ocr-' | sort"
    step langs-count "apt-cache search --names-only '^tesseract-ocr-' | grep -vE '^tesseract-ocr-(all|script-|osd|dev)' | wc -l"
    step size-dev "apt-get install --assume-no libtesseract-dev"
    step size-all "apt-get install --assume-no tesseract-ocr-all"
    ;;
  ubuntu-24.04-ppa)
    export DEBIAN_FRONTEND=noninteractive
    step update "apt-get update"
    step prereq "apt-get install -y software-properties-common"
    step add-ppa "add-apt-repository -y ppa:alex-p/tesseract-ocr5"
    step policy "apt-cache policy tesseract-ocr"
    step install "apt-get install -y tesseract-ocr"
    step clean "apt-get clean"
    step pkgs "dpkg-query -W -f='\${Package} \${Version} \${Installed-Size}KiB\n' | grep -Ei 'tesseract|lept'"
    ;;
  fedora)
    step install "dnf install -y tesseract"
    step clean "dnf clean all"
    step pkgs "rpm -qa | grep -Ei 'tesseract|lept' | sort"
    step info "dnf info --installed tesseract"
    step langs-search "dnf repoquery --qf '%{name}\n' 'tesseract-langpack-*' 'tesseract-script-*' 2>/dev/null | sort -u"
    step langs-count "dnf repoquery --qf '%{name}\n' 'tesseract-langpack-*' 2>/dev/null | sort -u | wc -l"
    step size-dev "dnf install --assumeno tesseract-devel"
    ;;
  archlinux)
    step sync "pacman -Sy --noconfirm"
    step provider-default "pacman -Sp --print-format '%n %v' --noconfirm tesseract"
    step install "pacman -S --noconfirm --needed tesseract tesseract-data-eng"
    step clean "pacman -Scc --noconfirm"
    step pkgs "pacman -Q | grep -Ei 'tesseract|lept'"
    step info "pacman -Qi tesseract"
    step langs-search "pacman -Ss '^tesseract-data-' | grep -E '^[a-z]+/' | sort"
    step langs-count "pacman -Ssq '^tesseract-data-' | wc -l"
    ;;
  alpine)
    step update "apk update"
    step install "apk add tesseract-ocr"
    step pkgs "apk info -vv 2>/dev/null | grep -Ei 'tesseract|lept'"
    step info "apk info -s tesseract-ocr tesseract-ocr-data-eng tesseract-ocr-data-osd leptonica 2>/dev/null"
    step langs-search "apk search -q 'tesseract-ocr-data-*' | sort"
    step langs-count "apk search -q 'tesseract-ocr-data-*' | wc -l"
    ;;
  opensuse-tumbleweed)
    step refresh "zypper --non-interactive refresh"
    step install "zypper --non-interactive install tesseract-ocr"
    step langs-after-base "tesseract --list-langs"
    step install-eng "rpm -q tesseract-ocr-traineddata-english || zypper --non-interactive install tesseract-ocr-traineddata-english"
    step clean "zypper clean --all"
    step pkgs "rpm -qa | grep -Ei 'tesseract|lept' | sort"
    step langs-search "zypper --non-interactive search 'tesseract-ocr-traineddata-*'"
    step langs-count "zypper --non-interactive search 'tesseract-ocr-traineddata-*' | grep -c 'tesseract-ocr-traineddata-'"
    ;;
  conda)
    note "conda_kb_before=$(du -skx /opt/conda | cut -f1)"
    step conda-version "conda --version"
    step install "conda install -y -c conda-forge tesseract"
    step clean "conda clean -a -y"
    note "conda_kb_after=$(du -skx /opt/conda | cut -f1)"
    step pkgs "conda list | grep -Ei 'tesseract|lept'"
    step which "command -v tesseract"
    ;;
esac

note "rootfs_kb_after=$(rootkb)"
step version "tesseract --version"
step list-langs "tesseract --list-langs"
step ocr "tesseract /samples/receipt.png -"
TD=$(tesseract --list-langs 2>&1 | head -1 | sed -n 's/.*"\(.*\)".*/\1/p')
step where "command -v tesseract; ls -la '$TD'; du -sh '$TD'"
# real error captures (missing language, wrong tessdata dir)
step err-lang "tesseract /samples/receipt.png - -l xyz"
step err-tessdata "tesseract /samples/receipt.png - --tessdata-dir /nonexistent"
step err-prefix "TESSDATA_PREFIX=/tmp tesseract /samples/receipt.png -"
step err-noimage "tesseract /samples/missing.png -"
exit 0
