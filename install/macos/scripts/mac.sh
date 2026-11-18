#!/bin/bash
# macOS install capture on a GitHub Actions runner. Commands that matter for the guide run
# INSIDE Terminal.app (opened via .command files) so the screenshots are real; each also
# tees its output to a .log next to the screenshot.  usage: mac.sh <outdir>
set -u
OUT=$(cd "$1" && pwd); REPO=$(pwd)
LOG=$OUT/log.txt
log() { echo "$*" | tee -a "$LOG"; }
cat > "$OUT/meta.json" <<J
{"os": "$(sw_vers -productName) $(sw_vers -productVersion) ($(sw_vers -buildVersion))", "arch": "$(uname -m)",
 "cpu": "$(sysctl -n machdep.cpu.brand_string)", "cores": $(sysctl -n hw.ncpu), "runner_image": "${ImageOS:-} ${ImageVersion:-}",
 "brew": "$(brew --version | head -1)", "date_utc": "$(date -u +%FT%TZ)", "run": "${RUN_URL:-}", "git_sha": "${GITHUB_SHA:-}"}
J
cat "$OUT/meta.json" | tee -a "$LOG"
log "which tesseract before: $(which tesseract 2>&1 || echo 'not found')"
log "brew prefix: $(brew --prefix)"

# Window id of the front Terminal window (CGWindowID) for screencapture -l
cat > /tmp/winid.swift <<'S'
import CoreGraphics
let opts = CGWindowListOption(arrayLiteral: .optionOnScreenOnly, .excludeDesktopElements)
if let list = CGWindowListCopyWindowInfo(opts, kCGNullWindowID) as? [[String: Any]] {
  for w in list where (w[kCGWindowOwnerName as String] as? String) == "Terminal" && (w[kCGWindowLayer as String] as? Int) == 0 {
    print(w[kCGWindowNumber as String] as! Int); break
  }
}
S
swiftc -O /tmp/winid.swift -o /tmp/winid 2>>"$LOG" || log "swiftc failed"

N=0
term() {  # term <slug> <timeout_s> <commands...>  -> runs in a new Terminal window, screenshots it
  local slug=$1 to=$2; shift 2; N=$((N+1))
  local name; name=$(printf 'macos-terminal-%02d-%s' $N "$slug")
  local cmdf=/tmp/$name.command marker=/tmp/$name.done
  rm -f "$marker"
  {
    echo '#!/bin/zsh'
    echo "printf '\\e[8;34;110t'; clear; cd '$REPO'"
    echo "export PATH=\"$(brew --prefix)/bin:\$PATH\""
    echo "{"
    for c in "$@"; do
      printf "print -P '%%F{green}%%n@%%m%%f %%F{blue}~%%f %%# '%q\n" "$c"
      echo "$c"
    done
    echo "} 2>&1 | tee '$OUT/$name.log'"
    echo "touch '$marker'"
  } > "$cmdf"
  chmod +x "$cmdf"
  local s; s=$(date +%s)
  open -a Terminal "$cmdf"
  while [ ! -f "$marker" ] && [ $(( $(date +%s) - s )) -lt "$to" ]; do sleep 2; done
  local e; e=$(date +%s)
  log "$name: finished=$([ -f "$marker" ] && echo yes || echo NO-timeout) wall_seconds=$((e-s))"
  sleep 2
  osascript -e 'tell application "Terminal" to activate' 2>>"$LOG"
  sleep 1
  local wid; wid=$(/tmp/winid 2>/dev/null)
  if [ -n "$wid" ]; then screencapture -x -o -l"$wid" "$OUT/$name.png" && log "  window shot $name.png (id $wid)"; fi
  screencapture -x "$OUT/$name-desktop.png" && log "  desktop shot $name-desktop.png"
  osascript -e 'tell application "Terminal" to close front window' >/dev/null 2>&1 || true
}

# 1. brew facts before installing
brew info tesseract > "$OUT/brew-info-before.txt" 2>&1
brew info --json=v2 tesseract > "$OUT/brew-info.json"
brew deps tesseract > "$OUT/brew-deps.txt"; brew deps --tree tesseract > "$OUT/brew-deps-tree.txt"
log "brew deps tesseract (recursive) count: $(wc -l < "$OUT/brew-deps.txt" | tr -d ' ')"
log "direct dependencies: $(python3 -c "import json;d=json.load(open('$OUT/brew-info.json'));f=d['formulae'][0];print(len(f['dependencies']), f['dependencies'], 'stable', f['versions']['stable'], 'bottle', list(f['bottle']['stable']['files'].keys()))")"
log "deps already installed on the runner: $(brew list --formula -1 | grep -Fxf "$OUT/brew-deps.txt" | wc -l | tr -d ' ') ($(brew list --formula -1 | grep -Fxf "$OUT/brew-deps.txt" | tr '\n' ' '))"
s=$(date +%s); brew update > "$OUT/brew-update.txt" 2>&1; log "brew update seconds: $(( $(date +%s)-s ))"
df -k / | tail -1 | awk '{print "free_kb_before " $4}' | tee -a "$LOG"

# 2. install in Terminal (auto-update already done above, so it's not counted)
term brew-install-tesseract 1800 'export HOMEBREW_NO_AUTO_UPDATE=1' 'time brew install tesseract'
df -k / | tail -1 | awk '{print "free_kb_after " $4}' | tee -a "$LOG"
log "installed now: $(brew list --formula -1 | wc -l | tr -d ' ') formulae"
du -sh "$(brew --prefix tesseract)/" "$(brew --cellar tesseract)" "$(brew --prefix)/share/tessdata" 2>&1 | tee -a "$LOG"
log "tessdata dir: $(ls -la "$(brew --prefix)/share/tessdata/" 2>&1)"
term version 120 'which tesseract' 'tesseract --version' 'tesseract --list-langs'
term ocr-receipt 120 'tesseract samples/receipt.png -'
term error-missing-language 60 'tesseract samples/receipt.png - -l fra' 'tesseract samples/receipt.png - -l xyz'
term brew-install-tesseract-lang 1800 'export HOMEBREW_NO_AUTO_UPDATE=1' 'time brew install tesseract-lang' 'tesseract --list-langs | head -5' 'tesseract --list-langs | tail -n +2 | wc -l'
du -sh "$(brew --prefix tesseract-lang)/" "$(brew --cellar tesseract-lang)" 2>&1 | tee -a "$LOG"
brew info tesseract-lang > "$OUT/brew-info-tesseract-lang.txt" 2>&1
term ocr-french-after-lang 120 'tesseract samples/receipt.png - -l eng+fra | head -5'
df -k / | tail -1 | awk '{print "free_kb_after_lang " $4}' | tee -a "$LOG"

# 3. pytesseract error when the binary can't be found (PATH without Homebrew)
python3 -m venv /tmp/venv && /tmp/venv/bin/pip -q install pytesseract pillow >> "$LOG" 2>&1
cat > /tmp/ocr_test.py <<P
import pytesseract
from PIL import Image
print(pytesseract.image_to_string(Image.open("samples/receipt.png"))[:60])
P
term error-pytesseract-not-found 120 'env PATH=/usr/bin:/bin /tmp/venv/bin/python /tmp/ocr_test.py' '/tmp/venv/bin/python /tmp/ocr_test.py'
log "done"
