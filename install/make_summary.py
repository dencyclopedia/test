#!/usr/bin/env python3
"""Build the comparison table in install/SUMMARY.md from the captured result files.
Every cell is parsed from a file under install/; the file is named in the last column.
usage: python3 install/make_summary.py   (rewrites the block between the TABLE markers)"""
import csv, json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
P = lambda *a: os.path.join(HERE, *a)
ANSI = re.compile(r'\x1b\[[0-9;?]*[A-Za-z]')

def rd(*a):
    return ANSI.sub('', open(P(*a), encoding='utf-8-sig', errors='replace').read()).replace('\x00', '')

def js(*a):
    return json.load(open(P(*a), encoding='utf-8-sig'))

def mb(b):
    return f'{b / 1e6:.1f}' if b not in (None, '') else 'n/c'

rows = []
H = ['Method', 'OS (as tested)', 'Tesseract', 'Time to working OCR (s)', 'Download', 'Installed', 'Admin / root', 'PATH set automatically?', 'Notes', 'Source']

# ---------------- Windows
if os.path.exists(P('windows', 'gui-default', 'result.json')):
    meta = js('windows', 'gui-default', 'meta.json')
    wos = f"{meta['os']} build {meta['build']}"
    dl = rd('windows', 'gui-default', 'download.txt')
    inst_bytes = int(re.search(r'bytes: (\d+)', dl).group(1))
    man = re.search(r'level="(\w+)"', dl).group(1)
    pr = js('windows', 'gui-default', 'path-result.json')
    for mode, label in (('default', 'UB Mannheim installer, default components (GUI)'), ('all', 'UB Mannheim installer, all script + language data ticked (GUI)')):
        r = js('windows', f'gui-{mode}', 'result.json')
        ver = re.search(r'setup-([\d.]+)\.exe', r['installer']).group(1)
        rows.append([label, wos, ver, f"{r['installing_seconds']} (Installing page only)", f"{mb(inst_bytes)} MB" + (' + language downloads during install' if mode == 'all' else ''),
                     mb(r['installed_bytes']) + ' MB', f'installer manifest: `{man}`; installs to Program Files', 'no' if not any(pr['registry_path_has_tesseract_after_gui_install'].values()) else 'yes',
                     f"{len(r['traineddata_files'])} .traineddata; wizard says {r['space_required_selected']}", f'windows/gui-{mode}/result.json, windows/gui-default/download.txt, windows/gui-default/path-result.json'])
    for pm, label in (('winget', 'winget `UB-Mannheim.TesseractOCR`'), ('winget-tesseract-ocr', 'winget `tesseract-ocr.tesseract`'), ('choco', 'Chocolatey `tesseract`'), ('scoop', 'Scoop `tesseract`')):
        if not os.path.exists(P('windows', pm, 'result.json')):
            continue
        r = js('windows', pm, 'result.json'); log = rd('windows', pm, 'log.txt')
        ver = re.search(r'tesseract v([\d.]+)', log.split('--version (full path)')[-1]).group(1)
        url = re.search(r'Installer Url: (\S+)', log)
        dlmb = 'n/c'
        if url:
            for row in csv.DictReader(open(P('windows', 'ub-mannheim', 'installers-sha256.tsv')), delimiter='\t'):
                if row['source_url'] == url.group(1):
                    dlmb = mb(int(row['bytes']))
        t = r['install_seconds']; note = ''
        if pm == 'scoop':
            t = f"{r['install_seconds']} + {r['languages_install_seconds']} (`tesseract-languages`)"
            note = f"no language data until `scoop install tesseract-languages` ({mb(r['languages_bytes'])} MB); scoop itself took {r['scoop_setup_seconds']} s to install"
        if pm == 'winget':
            note = 'winget still serves 5.4.0.20240606 for this id'
        fresh = log.split('### after install')[-1]
        works = 'tesseract v' in fresh
        added = r.get('path_entries_added') or []
        path = ('yes: ' + ', '.join(f'`{a}`' for a in added)) if added else 'no'
        path += '' if works else ' (new shell: "not recognized")'
        adm = 'user profile (runner session was admin)' if pm == 'scoop' else 'yes (Program Files; runner is admin)'
        rows.append([label, wos, ver, str(t), dlmb + (' MB' if dlmb != 'n/c' else ''), mb(r['installed_bytes']) + ' MB', adm, path, note, f'windows/{pm}/result.json, windows/{pm}/log.txt'])
    if os.path.exists(P('windows', 'wsl', 'result.json')):
        r = js('windows', 'wsl', 'result.json'); log = rd('windows', 'wsl', 'log.txt')
        ver = re.search(r'^tesseract ([\d.]+)', log, re.M).group(1)
        dl_ = re.search(r'Need to get ([\d.]+ \w+) of archives', log).group(1); after = re.search(r'After this operation, ([\d.]+ \w+)', log).group(1)
        rows.append(['WSL2 Ubuntu 24.04 + `apt-get install tesseract-ocr`', wos + ', WSL ' + re.search(r'WSL version: (\S+)', log).group(1), ver,
                     f"{r['apt_update_seconds']} + {r['apt_install_seconds']} (apt update + install)", dl_.replace(' kB', ' kB'), after + ' (apt)', 'root inside WSL', 'n/a (Linux side only; Windows `where tesseract` finds nothing)',
                     f"`wsl --install -d Ubuntu-24.04` took {r['distro_install_seconds']} s", 'windows/wsl/result.json, windows/wsl/log.txt'])

# ---------------- macOS
for d in sorted(os.listdir(P('macos'))):
    if not d.startswith('brew-') or not os.path.exists(P('macos', d, 'log.txt')):
        continue
    if d.endswith('-full'):
        log = rd('macos', d, 'log.txt')
        m = re.search(r'brew install tesseract exit=(\d+) seconds=(\d+)', log)
        ver = re.search(r'^tesseract ([\d.]+)', log, re.M); sz = re.search(r'^\s*(\S+)\s+/usr/local/Cellar/tesseract', log, re.M)
        nb = re.search(r'formulae built from source: (\d+)\s+poured from bottles: (\d+)', log)
        osl = re.search(r'ProductVersion:\s*(\S+)', log)
        if m:
            rows.append(['Homebrew `brew install tesseract` (macos-15-intel, run to completion)', f"macOS {osl.group(1) if osl else '?'} x86_64", ver.group(1) if ver else 'n/c',
                         f"{m.group(2)} (exit {m.group(1)})", 'n/c', (sz.group(1) + 'B (Cellar)') if sz else 'n/c', 'no', 'yes (/usr/local/bin)',
                         f"{nb.group(1)} formulae built from source, {nb.group(2)} poured from bottles" if nb else '', f'macos/{d}/log.txt'])
        continue
    meta = js('macos', d, 'meta.json'); log = rd('macos', d, 'log.txt')
    t1 = re.search(r'([\d.]+) total', rd('macos', d, 'macos-terminal-01-brew-install-tesseract.log'))
    ver = re.search(r'^tesseract ([\d.]+)', rd('macos', d, 'macos-terminal-02-version.log'), re.M)
    size = re.search(r'^\s*(\S+)\s+/opt/homebrew/Cellar/tesseract$|^\s*(\S+)\s+/usr/local/Cellar/tesseract$', log, re.M)
    deps = re.search(r'deps already installed on the runner: (\d+)', log); depn = re.search(r'\(recursive\) count: (\d+)', log)
    mos = f"{meta['os']} {meta['arch']}"
    to = re.search(r'macos-terminal-01-brew-install-tesseract: finished=NO-timeout wall_seconds=(\d+)', log)
    if to:
        rows.append([f"Homebrew `brew install tesseract` ({d[5:]}, Terminal capture)", mos, 'not installed', f"> {to.group(1)} (still compiling from source when the capture stopped)", 'n/c', 'n/c', 'no', 'n/a',
                     f"{re.search(r'count: (\d+)', log).group(1)} recursive deps; brew update took {re.search(r'brew update seconds: (\d+)', log).group(1)} s", f'macos/{d}/log.txt, macos/{d}/macos-terminal-01-brew-install-tesseract.png'])
        continue
    rows.append([f"Homebrew `brew install tesseract` ({d[5:]})", mos, ver.group(1) if ver else 'n/c', t1.group(1) if t1 else 'n/c', 'n/c',
                 (size.group(1) or size.group(2)) + 'B (Cellar, `du -sh`)' if size else 'n/c', 'no', 'yes (brew bin already on PATH)',
                 f"{depn.group(1)} recursive deps, {deps.group(1)} already on the runner image; `brew update` excluded" if deps else '', f'macos/{d}/log.txt, macos/{d}/macos-terminal-01-brew-install-tesseract.log'])
    t5 = re.search(r'([\d.]+) total', rd('macos', d, 'macos-terminal-05-brew-install-tesseract-lang.log'))
    s5 = re.search(r'^\s*(\S+)\s+/opt/homebrew/Cellar/tesseract-lang$|^\s*(\S+)\s+/usr/local/Cellar/tesseract-lang$', log, re.M)
    nl = re.findall(r'^\s*(\d+)\s*$', rd('macos', d, 'macos-terminal-05-brew-install-tesseract-lang.log'), re.M)
    rows.append([f"Homebrew `brew install tesseract-lang` ({d[5:]})", mos, '(language data)', t5.group(1) if t5 else 'n/c', 'n/c',
                 (s5.group(1) or s5.group(2)) + 'B' if s5 else 'n/c', 'no', 'n/a', f'{nl[-1]} languages listed afterwards' if nl else '', f'macos/{d}/macos-terminal-05-brew-install-tesseract-lang.log'])
if os.path.exists(P('macos', 'macports', 'macports.txt')):
    log = rd('macos', 'macports', 'macports.txt')
    m = re.search(r'port install tesseract exit=0 seconds: (\d+)', log); e = re.search(r'port install tesseract-eng exit=0 seconds: (\d+)', log)
    ver = re.search(r'^tesseract ([\d.]+)', log, re.M); sz = re.search(r'^(\S+)\s+/opt/local$', log, re.M)
    pk = re.search(r'macports install seconds: (\d+)', log); su = re.search(r'selfupdate seconds: (\d+)', log)
    sw = rd('macos', 'macports', 'sw_vers.txt')
    mos = 'macOS ' + re.search(r'ProductVersion:\s*(\S+)', sw).group(1) + ' ' + sw.strip().split('\n')[-1]
    if m and ver:
        rows.append(['MacPorts `sudo port install tesseract` + `tesseract-eng`', mos, ver.group(1), f"{m.group(1)} + {e.group(1) if e else 'n/c'}", 'n/c',
                     f"{sz.group(1)}B (all of /opt/local, incl. MacPorts base)" if sz else 'n/c', 'yes (sudo)', 'not tested (the script called /opt/local/bin/tesseract directly)',
                     f"MacPorts not preinstalled: .pkg {pk.group(1) if pk else '?'} s + selfupdate {su.group(1) if su else '?'} s; no language data until `tesseract-eng`", 'macos/macports/macports.txt'])

# ---------------- Linux
for r in csv.DictReader(open(P('linux', 'results', 'summary.tsv')), delimiter='\t'):
    t = float(r['all_steps_to_installed_seconds'] or 0)
    dlm = re.search(r'([\d.]+) (kB|MB|MiB)', r['pm_download'])
    dl = f"{dlm.group(1)} {dlm.group(2)}" if dlm else 'n/c'
    ins = re.search(r'([\d.]+) (MB|MiB)', r['pm_installed'])
    inst = f"{ins.group(1)} {ins.group(2)} (pkg mgr); {r['rootfs_growth_MiB_after_cache_clean']} MiB rootfs growth" if ins and not r['pm_installed'].startswith('OK') else f"{r['rootfs_growth_MiB_after_cache_clean']} MiB rootfs growth"
    rows.append([f"`{r['flavour']}` container", r['os'] + (' (base OS of condaforge/miniforge3)' if r['flavour'] == 'conda' else ''), r['tesseract'], f"{t:.2f}", dl, inst, 'root (container)', 'yes (/usr/bin)' if r['flavour'] != 'conda' else 'yes (conda env bin)',
                 f"languages: {r['langs_listed'].split(':')[0]}", f"linux/results/{r['flavour']}/session.cast, linux/results/summary.tsv"])

out = ['| ' + ' | '.join(H) + ' |', '|' + '---|' * len(H)]
for r in rows:
    out.append('| ' + ' | '.join(str(c).replace('|', '/') for c in r) + ' |')
table = '\n'.join(out)
p = P('SUMMARY.md')
s = open(p).read() if os.path.exists(p) else '<!-- TABLE -->\n<!-- /TABLE -->\n'
s = re.sub(r'<!-- TABLE -->.*<!-- /TABLE -->', '<!-- TABLE -->\n' + table.replace('\\', '\\\\') + '\n<!-- /TABLE -->', s, flags=re.S)
open(p, 'w').write(s)
print(table)
