#!/bin/bash
# Feasibility test: install a cask app, run it, uninstall it the way a normal user does
# (drag to Trash), and measure what is left behind. Screenshots + screen recording.
# usage: mac_uninstall.sh <cask> <App Name.app> <outdir>
set -u
CASK=$1; APP=$2; OUT=$(mkdir -p "$3" && cd "$3" && pwd); LOG=$OUT/log.txt
log() { echo "[$(date -u +%T)] $*" | tee -a "$LOG"; }
shot() { sleep 1; screencapture -x "$OUT/$1.png" && log "screenshot $1.png" || log "screenshot FAILED $1"; }
LOCS=( /Applications "$HOME/Applications" "$HOME/Library/Application Support" "$HOME/Library/Caches"
  "$HOME/Library/Preferences" "$HOME/Library/Containers" "$HOME/Library/Group Containers"
  "$HOME/Library/Saved Application State" "$HOME/Library/LaunchAgents" "$HOME/Library/Logs"
  "$HOME/Library/HTTPStorages" "$HOME/Library/WebKit" "$HOME/Library/Cookies" "$HOME/Library/Application Scripts"
  /Library/LaunchAgents /Library/LaunchDaemons "/Library/Application Support" /Library/PrivilegedHelperTools
  /Library/Preferences /private/var/db/receipts /Users/Shared )
snap() { for d in "${LOCS[@]}"; do [ -d "$d" ] && find "$d" -mindepth 1 -maxdepth 1 2>/dev/null; done | sort > "$1"; }
sizes() { while IFS= read -r p; do [ -e "$p" ] && printf '%s\t%s\n' "$(du -sk "$p" 2>/dev/null | cut -f1)" "${p/#$HOME/~}"; done; }

cat > "$OUT/meta.json" <<J
{"os": "$(sw_vers -productName) $(sw_vers -productVersion) ($(sw_vers -buildVersion))", "arch": "$(uname -m)",
 "runner_image": "${ImageOS:-} ${ImageVersion:-}", "brew": "$(brew --version | head -1)", "cask": "$CASK",
 "date_utc": "$(date -u +%FT%TZ)", "run": "${RUN_URL:-}", "git_sha": "${GITHUB_SHA:-}"}
J
log "start $CASK ($APP)"
snap "$OUT/snap-0-before.txt"

# screen recording of the whole session (part of the feasibility test)
screencapture -x -V 150 "$OUT/recording-raw.mov" > "$OUT/recording.log" 2>&1 &
REC=$!

s=$(date +%s); brew install --cask "$CASK" > "$OUT/brew-install.txt" 2>&1; log "brew install exit=$? seconds=$(( $(date +%s)-s ))"
brew info --json=v2 --cask "$CASK" > "$OUT/cask-info.json" 2>&1
log "version: $(python3 -c "import json;print(json.load(open('$OUT/cask-info.json'))['casks'][0]['version'])" 2>&1)"
log "app bundle size: $(du -sh "/Applications/$APP" 2>/dev/null | cut -f1)"
snap "$OUT/snap-1-installed.txt"

open -a "/Applications/$APP" 2>>"$LOG"; log "launched"; sleep 25
shot 01-app-first-launch
osascript -e "tell application \"${APP%.app}\" to quit" >/dev/null 2>&1; sleep 5
pkill -f "/Applications/$APP" 2>/dev/null; sleep 2
snap "$OUT/snap-2-after-first-run.txt"
comm -13 "$OUT/snap-0-before.txt" "$OUT/snap-2-after-first-run.txt" | sizes > "$OUT/created-by-install-and-first-run.tsv"
log "items created by install + first run: $(wc -l < "$OUT/created-by-install-and-first-run.tsv")"

# what a normal user does: Finder > Applications > move to Trash
open -R "/Applications/$APP"; sleep 4; shot 02-finder-app-selected
if osascript -e "tell application \"Finder\" to delete (POSIX file \"/Applications/$APP\" as alias)" >>"$LOG" 2>&1; then
  log "moved to Trash via Finder (AppleScript)"; METHOD=finder
else
  log "Finder AppleScript refused; falling back to mv into ~/.Trash"; mv "/Applications/$APP" "$HOME/.Trash/" 2>>"$LOG"; METHOD=mv
fi
sleep 3; shot 03-after-move-to-trash
open "$HOME/.Trash"; sleep 3; shot 04-trash-window
osascript -e 'tell application "Finder" to empty trash' >>"$LOG" 2>&1 || rm -rf "$HOME/.Trash/$APP"
sleep 2
snap "$OUT/snap-3-after-trash.txt"
cut -f2 "$OUT/created-by-install-and-first-run.tsv" | sed "s#^~#$HOME#" | sort > /tmp/created.txt
comm -12 /tmp/created.txt "$OUT/snap-3-after-trash.txt" | sizes > "$OUT/leftovers-after-trash.tsv"
log "LEFTOVERS after drag-to-Trash: $(wc -l < "$OUT/leftovers-after-trash.tsv") items, $(awk -F'\t' '{s+=$1} END{print s+0}' "$OUT/leftovers-after-trash.tsv") KB"

# show the leftovers to the reader
first=$(cut -f2 "$OUT/leftovers-after-trash.tsv" | sed "s#^~#$HOME#" | grep -m1 'Application Support\|Caches\|Preferences')
[ -n "$first" ] && { open -R "$first"; sleep 4; shot 05-finder-leftover-files; }

# clean removal: brew's zap stanza (the cask's own list of support files)
python3 -c "import json;c=json.load(open('$OUT/cask-info.json'))['casks'][0];print(json.dumps([a for a in c['artifacts'] if 'zap' in a or 'uninstall' in a],indent=1))" > "$OUT/cask-zap-stanza.json" 2>&1
s=$(date +%s); brew uninstall --zap --cask "$CASK" > "$OUT/brew-uninstall-zap.txt" 2>&1; log "brew uninstall --zap exit=$? seconds=$(( $(date +%s)-s ))"
snap "$OUT/snap-4-after-zap.txt"
comm -12 /tmp/created.txt "$OUT/snap-4-after-zap.txt" | sizes > "$OUT/leftovers-after-zap.tsv"
log "LEFTOVERS after brew --zap: $(wc -l < "$OUT/leftovers-after-zap.tsv") items"
shot 06-final-desktop

wait $REC; log "recording exit=$? $(ls -la "$OUT/recording-raw.mov" 2>&1)"
if [ -s "$OUT/recording-raw.mov" ]; then
  avconvert --preset Preset960x540 --source "$OUT/recording-raw.mov" --output "$OUT/recording.mp4" >>"$LOG" 2>&1 \
    && rm -f "$OUT/recording-raw.mov"; log "recording: $(ls -la "$OUT"/recording* 2>&1 | tr '\n' ' ')"
fi
echo "{\"trash_method\": \"$METHOD\"}" > "$OUT/result.json"
log done
