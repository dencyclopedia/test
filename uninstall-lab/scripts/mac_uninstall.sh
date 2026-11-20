#!/bin/bash
# Uninstall capture on a GitHub Actions macOS runner.
# Installs a Homebrew cask, launches it once, removes it the way a user does (Applications -> Trash),
# measures what is left behind, then runs `brew uninstall --zap`. Screenshots (window crops + full
# desktop) and a screen recording. Every step has a timeout so one stuck app can't hang the job.
# usage: mac_uninstall.sh <cask> <outdir>
set -u
CASK=$1; OUT=$(mkdir -p "$2" && cd "$2" && pwd); LOG=$OUT/log.txt
log() { echo "[$(date -u +%T)] $*" | tee -a "$LOG"; }
tmo() { local s=$1; shift; perl -e 'alarm shift; exec @ARGV' "$s" "$@"; }   # tmo <seconds> cmd...
LOCS=( /Applications "$HOME/Applications" "$HOME/Library/Application Support" "$HOME/Library/Caches"
  "$HOME/Library/Preferences" "$HOME/Library/Containers" "$HOME/Library/Group Containers"
  "$HOME/Library/Saved Application State" "$HOME/Library/LaunchAgents" "$HOME/Library/Logs"
  "$HOME/Library/HTTPStorages" "$HOME/Library/WebKit" "$HOME/Library/Cookies" "$HOME/Library/Application Scripts"
  "$HOME/Library/Internet Plug-Ins" /Library/LaunchAgents /Library/LaunchDaemons "/Library/Application Support"
  /Library/PrivilegedHelperTools /Library/Preferences /Library/Logs "/Library/Internet Plug-Ins"
  /Library/SystemExtensions /private/var/db/receipts /Users/Shared "$HOME" )
snap() { for d in "${LOCS[@]}"; do [ -d "$d" ] && sudo find "$d" -mindepth 1 -maxdepth 1 2>/dev/null; done | sort -u > "$1"; }
sizes() { while IFS= read -r p; do [ -e "$p" ] && printf '%s\t%s\n' "$(sudo du -sk "$p" 2>/dev/null | cut -f1)" "${p/#$HOME/~}"; done; }

# --- window ids for screencapture -l (largest on-screen window of a process whose name contains $1)
cat > /tmp/winid.swift <<'S'
import CoreGraphics
let want = CommandLine.arguments.count > 1 ? CommandLine.arguments[1].lowercased() : ""
var best = (0, 0.0)
if let list = CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID) as? [[String: Any]] {
  for w in list {
    let owner = ((w[kCGWindowOwnerName as String] as? String) ?? "").lowercased()
    guard owner.contains(want), (w[kCGWindowLayer as String] as? Int) == 0,
          let b = w[kCGWindowBounds as String] as? [String: Double] else { continue }
    let area = (b["Width"] ?? 0) * (b["Height"] ?? 0)
    if area > best.1 && area > 40000 { best = (w[kCGWindowNumber as String] as! Int, area) }
  }
}
if best.0 > 0 { print(best.0) }
S
[ -x /tmp/winid ] || swiftc -O /tmp/winid.swift -o /tmp/winid 2>>"$LOG" || log "swiftc failed"
shot() {  # shot <name> [owner-substring]  -> <name>.png (window crop, if found) + <name>-desktop.png
  sleep 1; local wid=""
  [ -n "${2:-}" ] && wid=$(/tmp/winid "$2" 2>/dev/null)
  [ -n "$wid" ] && screencapture -x -o -l"$wid" "$OUT/$1.png" && log "screenshot $1.png (window of '$2')"
  screencapture -x "$OUT/$1-desktop.png" && log "screenshot $1-desktop.png"
}
close_finder() { tmo 8 osascript -e 'tell application "Finder" to close every window' >/dev/null 2>&1 || { killall Finder 2>/dev/null; sleep 3; }; }

cat > "$OUT/meta.json" <<J
{"os": "$(sw_vers -productName) $(sw_vers -productVersion) ($(sw_vers -buildVersion))", "arch": "$(uname -m)",
 "runner_image": "${ImageOS:-} ${ImageVersion:-}", "brew": "$(brew --version | head -1)", "cask": "$CASK",
 "date_utc": "$(date -u +%FT%TZ)", "run": "${RUN_URL:-}", "git_sha": "${GITHUB_SHA:-}"}
J
log "start $CASK"
# --- pre-clean: some apps (Chrome, Firefox...) come preinstalled on the runner image. Remove the app
# and every path in the cask's zap list first, so the test starts from a machine without the app.
brew info --json=v2 --cask "$CASK" > "$OUT/cask-info-before.json" 2>&1
python3 - "$OUT/cask-info-before.json" > /tmp/preclean.txt <<'P'
import json, sys, glob, os
c = json.load(open(sys.argv[1]))['casks'][0]
paths = []
for a in c['artifacts']:
    if 'app' in a: paths.append('/Applications/' + a['app'][0])
    for k in ('zap', 'uninstall'):
        for st in a.get(k, []):
            if isinstance(st, dict):
                for kk in ('trash', 'delete', 'rmdir'):
                    v = st.get(kk, [])
                    paths += [v] if isinstance(v, str) else v
for p in paths:
    for g in glob.glob(os.path.expanduser(p)):
        print(g)
P
if [ -s /tmp/preclean.txt ]; then
  log "pre-clean (already on runner image): $(tr '\n' ' ' < /tmp/preclean.txt)"
  while IFS= read -r p; do sudo rm -rf "$p"; done < /tmp/preclean.txt
fi
brew list --cask "$CASK" >/dev/null 2>&1 && tmo 120 brew uninstall --force --cask "$CASK" >/dev/null 2>&1
close_finder
snap "$OUT/snap-0-before.txt"
screencapture -x -V 240 "$OUT/recording-raw.mov" > "$OUT/recording.log" 2>&1 & REC=$!
stop_rec() { for i in $(seq 1 30); do kill -0 $REC 2>/dev/null || break; sleep 10; done; kill -INT $REC 2>/dev/null; sleep 3; kill -9 $REC 2>/dev/null; }

s=$(date +%s); tmo 900 brew install --cask "$CASK" > "$OUT/brew-install.txt" 2>&1; rc=$?
log "brew install exit=$rc seconds=$(( $(date +%s)-s ))"
brew info --json=v2 --cask "$CASK" > "$OUT/cask-info.json" 2>&1
APPNAME=$(python3 -c "
import json; c=json.load(open('$OUT/cask-info.json'))['casks'][0]
apps=[a['app'][0] for a in c['artifacts'] if 'app' in a]
print(apps[0] if apps else '')" 2>/dev/null)
snap /tmp/snap-installed-probe.txt
if [ -z "$APPNAME" ] || [ ! -d "/Applications/$APPNAME" ]; then
  # .pkg-based casks (Zoom, Teams, OneDrive) have no `app` artifact: take the new bundle in /Applications
  APPNAME=$(comm -13 "$OUT/snap-0-before.txt" /tmp/snap-installed-probe.txt | grep -E '^/Applications/[^/]+\.app$' | head -1 | sed 's#^/Applications/##')
  log "app bundle found by diff (pkg cask): $APPNAME"
fi
APP=/Applications/$APPNAME
if [ -z "$APPNAME" ] || [ ! -d "$APP" ]; then log "FAILED: no app bundle after install ($APPNAME)"; stop_rec; exit 0; fi
sudo xattr -dr com.apple.quarantine "$APP" 2>/dev/null   # skip the first-launch "downloaded from the internet" prompt
BID=$(defaults read "$APP/Contents/Info" CFBundleIdentifier 2>/dev/null)
EXE=$(defaults read "$APP/Contents/Info" CFBundleExecutable 2>/dev/null)
VER=$(defaults read "$APP/Contents/Info" CFBundleShortVersionString 2>/dev/null)
TEAM=$(codesign -dv "$APP" 2>&1 | sed -n 's/^TeamIdentifier=//p')
log "app=$APPNAME bundle_id=$BID exe=$EXE version=$VER team=$TEAM size=$(du -sh "$APP" | cut -f1)"
snap "$OUT/snap-1-installed.txt"

tmo 20 open "$APP" 2>>"$LOG"; log "launch requested"; sleep 30
shot 01-app-first-launch "$EXE"
tmo 10 osascript -e "tell application id \"$BID\" to quit" >/dev/null 2>&1; sleep 4
pkill -f "$APP/" 2>/dev/null; sleep 1; sudo pkill -9 -f "$APP/" 2>/dev/null; sleep 2
snap "$OUT/snap-2-after-first-run.txt"
comm -13 "$OUT/snap-0-before.txt" "$OUT/snap-2-after-first-run.txt" > /tmp/created.txt

# normal user removal: Finder > Applications > Move to Trash > Empty Trash
close_finder; tmo 10 open -R "$APP"; sleep 4; shot 02-finder-app-in-applications Finder
if tmo 15 osascript -e "tell application \"Finder\" to delete (POSIX file \"$APP\" as alias)" >>"$LOG" 2>&1; then
  METHOD="Finder Move to Trash (AppleScript)"
else
  sudo mv "$APP" "$HOME/.Trash/" 2>>"$LOG"; sudo chown -R "$(id -un)" "$HOME/.Trash/$APPNAME" 2>/dev/null
  METHOD="mv into ~/.Trash (Finder automation is not permitted on the runner)"
fi
log "removed app: $METHOD; still in /Applications: $([ -e "$APP" ] && echo YES || echo no)"
close_finder; tmo 10 open "$HOME/.Trash"; sleep 3; shot 03-trash-with-app Finder
sudo rm -rf "$HOME/.Trash/$APPNAME"; close_finder; sleep 2
snap "$OUT/snap-3-after-trash.txt"

# attribute changes to the app: bundle id, its vendor prefix, team id, app/exe/cask names
python3 - "$BID" "$TEAM" "$APPNAME" "$EXE" "$CASK" > /tmp/tokens.txt <<'P'
import sys, re
bid, team, app, exe, cask = sys.argv[1:]
t = {bid, team, app.removesuffix('.app'), exe, cask}
parts = bid.split('.')
if len(parts) >= 2: t.add('.'.join(parts[:2]))            # e.g. us.zoom, com.spotify
for x in (app.removesuffix('.app'), exe, cask):
    for w in re.split(r'[^A-Za-z0-9]+', x):
        if len(w) >= 4 and w.lower() not in {'google','microsoft','mozilla','apple','desktop','client','player','media'}: t.add(w)
print('\n'.join(sorted(x for x in t if x and len(x) >= 3)))
P
grep -iFf /tmp/tokens.txt /tmp/created.txt > /tmp/attr.txt || true
grep -viFf /tmp/tokens.txt /tmp/created.txt > /tmp/other.txt || true
log "attribution tokens: $(tr '\n' ' ' < /tmp/tokens.txt)"
sizes < /tmp/attr.txt > "$OUT/created-by-app.tsv"
sizes < /tmp/other.txt > "$OUT/created-other-during-test.tsv"
comm -12 <(sort /tmp/attr.txt) "$OUT/snap-3-after-trash.txt" | sizes > "$OUT/leftovers-after-trash.tsv"
log "app created $(wc -l < "$OUT/created-by-app.tsv" | tr -d ' ') items; other system changes during test: $(wc -l < "$OUT/created-other-during-test.tsv" | tr -d ' ')"
log "LEFTOVERS after Trash: $(wc -l < "$OUT/leftovers-after-trash.tsv" | tr -d ' ') items, $(awk -F'\t' '{s+=$1} END{print s+0}' "$OUT/leftovers-after-trash.tsv") KB"

first=$(cut -f2 "$OUT/leftovers-after-trash.tsv" | grep -m1 'Application Support' || cut -f2 "$OUT/leftovers-after-trash.tsv" | grep -m1 '^~/Library')
if [ -n "$first" ]; then close_finder; tmo 10 open -R "${first/#\~/$HOME}"; sleep 4; shot 04-finder-leftover Finder; fi

# ---- Clean-up proof (docs/05 §16 in the site repo) -------------------------------------------------
# If the site exported its clean-up command for this app (uninstall-lab/cleanup/<slug>-mac.sh), run it now,
# exactly as a reader would, and prove: (1) every measured leftover is gone, (2) nothing that existed
# before the app was installed was deleted, (3) the app installs and launches again afterwards.
CLEANUP="${CLEANUP_DIR:-}/${SLUG:-$CASK}-mac.sh"
if [ -n "${CLEANUP_DIR:-}" ] && [ -f "$CLEANUP" ]; then
  SHA=$(tr -d '\r' < "$CLEANUP" | shasum -a 256 | cut -d' ' -f1)
  log "clean-up proof: running $CLEANUP (sha256 $SHA)"
  cp "$CLEANUP" "$OUT/cleanup-command.sh"
  tmo 180 zsh "$CLEANUP" > "$OUT/cleanup-run.txt" 2>&1; log "clean-up command exit=$?"
  sleep 2
  snap "$OUT/snap-5-after-cleanup.txt"
  comm -23 "$OUT/snap-3-after-trash.txt" "$OUT/snap-5-after-cleanup.txt" > "$OUT/cleanup-removed.txt"
  comm -12 "$OUT/cleanup-removed.txt" "$OUT/snap-0-before.txt" > "$OUT/cleanup-removed-preexisting.txt"
  comm -12 <(sort /tmp/attr.txt) "$OUT/snap-5-after-cleanup.txt" > "$OUT/cleanup-residual.txt"
  log "clean-up removed $(wc -l < "$OUT/cleanup-removed.txt" | tr -d ' ') items; pre-existing removed: $(wc -l < "$OUT/cleanup-removed-preexisting.txt" | tr -d ' '); residual: $(wc -l < "$OUT/cleanup-residual.txt" | tr -d ' ')"
  # health check: the app installs and starts again on the cleaned machine
  tmo 120 brew uninstall --force --cask "$CASK" > "$OUT/cleanup-brew-forget.txt" 2>&1
  tmo 900 brew install --cask "$CASK" > "$OUT/cleanup-reinstall.txt" 2>&1; RI=$?
  [ -d "$APP" ] && sudo xattr -dr com.apple.quarantine "$APP" 2>/dev/null
  tmo 20 open "$APP" 2>>"$LOG"; sleep 25
  if [ "$RI" = 0 ] && pgrep -f "$APP/" > /dev/null; then REINSTALL=true; else REINSTALL=false; fi
  shot 06-reinstalled-after-cleanup "$EXE"
  log "reinstall exit=$RI, app running after reinstall: $REINSTALL"
  tmo 10 osascript -e "tell application id \"$BID\" to quit" >/dev/null 2>&1; sleep 3; pkill -f "$APP/" 2>/dev/null
  python3 - "$OUT" "$SHA" "$REINSTALL" "${RUN_URL:-}" > "$OUT/cleanup-verification.json" <<'P2'
import sys, json, datetime, os
out, sha, reinstall, run = sys.argv[1:]
home = os.path.expanduser('~')
lines = lambda f: [l.rstrip('\n').replace(home, '~', 1) for l in open(os.path.join(out, f)) if l.strip()]
print(json.dumps({'runUrl': run, 'verifiedAt': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
  'commandSha256': sha, 'removedCount': len(lines('cleanup-removed.txt')), 'residual': lines('cleanup-residual.txt'),
  'preexistingRemoved': lines('cleanup-removed-preexisting.txt'), 'reinstallOk': reinstall == 'true'}, indent=1))
P2
  log "clean-up verification: $(tr -d '\n ' < "$OUT/cleanup-verification.json" | cut -c1-300)"
fi

# clean removal using the cask's zap list
python3 -c "import json;c=json.load(open('$OUT/cask-info.json'))['casks'][0];print(json.dumps([a for a in c['artifacts'] if 'zap' in a or 'uninstall' in a],indent=1))" > "$OUT/cask-zap-stanza.json" 2>&1
s=$(date +%s); tmo 300 brew uninstall --zap --cask "$CASK" > "$OUT/brew-uninstall-zap.txt" 2>&1; log "brew uninstall --zap exit=$? seconds=$(( $(date +%s)-s ))"
snap "$OUT/snap-4-after-zap.txt"
comm -12 <(sort /tmp/attr.txt) "$OUT/snap-4-after-zap.txt" | sizes > "$OUT/leftovers-after-zap.tsv"
log "LEFTOVERS after brew --zap: $(wc -l < "$OUT/leftovers-after-zap.tsv" | tr -d ' ') items"
close_finder; shot 05-final-desktop

python3 - "$OUT" "$CASK" "$APPNAME" "$BID" "$VER" "$METHOD" > "$OUT/summary.json" <<'P'
import sys, json, os
out, cask, app, bid, ver, method = sys.argv[1:]
def rows(f):
    p = os.path.join(out, f)
    return [l.rstrip('\n').split('\t') for l in open(p) if l.strip()] if os.path.exists(p) else []
def kb(r): return sum(int(x[0]) for x in r if x[0].isdigit())
c, t, z = rows('created-by-app.tsv'), rows('leftovers-after-trash.tsv'), rows('leftovers-after-zap.tsv')
print(json.dumps({'os': 'macOS', 'cask': cask, 'app': app, 'bundle_id': bid, 'version': ver, 'removal_method': method,
  'created_items': len(c), 'created_kb': kb(c), 'leftover_items_after_trash': len(t), 'leftover_kb_after_trash': kb(t),
  'leftovers_after_trash': [x[1] for x in t], 'leftover_items_after_zap': len(z), 'leftovers_after_zap': [x[1] for x in z]}, indent=1))
P
stop_rec; log "recording stopped"
if [ -s "$OUT/recording-raw.mov" ]; then
  tmo 300 avconvert --preset Preset640x480 --source "$OUT/recording-raw.mov" --output "$OUT/recording.mp4" >>"$LOG" 2>&1 && rm -f "$OUT/recording-raw.mov"
fi
log "recording: $(ls -la "$OUT"/recording*.m* 2>&1 | awk '{print $5, $9}' | tr '\n' ' ')"
log done
