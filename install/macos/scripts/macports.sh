#!/bin/bash
# MacPorts is not preinstalled on GitHub's macOS runners. Install the official .pkg for this
# macOS version, then `sudo port install tesseract`; record times or the failure.  usage: macports.sh <outdir>
set -u
OUT=$1; LOG=$OUT/macports.txt
exec > >(tee -a "$LOG") 2>&1
echo "port before: $(which port 2>&1 || echo 'not installed')"
major=$(sw_vers -productVersion | cut -d. -f1)
curl -sS https://api.github.com/repos/macports/macports-base/releases/latest > /tmp/mp.json
python3 - "$major" <<'P' > /tmp/mp-url.txt
import json,sys
d=json.load(open('/tmp/mp.json')); m=sys.argv[1]
print(d.get('tag_name'), file=sys.stderr)
c=[a['browser_download_url'] for a in d.get('assets',[]) if a['name'].endswith('.pkg') and f"-{m}-" in a['name']]
print(c[0] if c else '')
P
url=$(cat /tmp/mp-url.txt)
echo "macports pkg for macOS $major: ${url:-NONE FOUND}"
python3 -c "import json;print('assets:', [a['name'] for a in json.load(open('/tmp/mp.json')).get('assets',[]) if a['name'].endswith('.pkg')])"
[ -z "$url" ] && { echo "RESULT: no MacPorts installer for this macOS version"; exit 0; }
s=$(date +%s); curl -sSL -o /tmp/mp.pkg "$url" && sudo installer -pkg /tmp/mp.pkg -target / ; echo "macports install seconds: $(( $(date +%s)-s ))"
export PATH=/opt/local/bin:/opt/local/sbin:$PATH
port version || { echo "RESULT: port not usable"; exit 0; }
s=$(date +%s); sudo port -N selfupdate; echo "selfupdate seconds: $(( $(date +%s)-s ))"
port info tesseract; port search --name --glob 'tesseract-*' | grep -c '^tesseract-' | sed 's/^/language ports found: /'
s=$(date +%s); timeout 1800 sudo port -N install tesseract; rc=$?; echo "port install tesseract exit=$rc seconds: $(( $(date +%s)-s ))"
port installed | head -80 > "$OUT/macports-installed.txt"
echo "ports installed: $(port installed | tail -n +2 | wc -l)"
du -sh /opt/local 2>/dev/null
/opt/local/bin/tesseract --version 2>&1; /opt/local/bin/tesseract --list-langs 2>&1
/opt/local/bin/tesseract samples/receipt.png - 2>&1 | head -5
s=$(date +%s); timeout 600 sudo port -N install tesseract-eng; echo "port install tesseract-eng exit=$? seconds: $(( $(date +%s)-s ))"
/opt/local/bin/tesseract --list-langs 2>&1
/opt/local/bin/tesseract samples/receipt.png - 2>&1 | head -5
