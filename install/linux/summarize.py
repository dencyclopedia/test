#!/usr/bin/env python3
"""Summarise install/linux/results/*/ into results/summary.tsv (every value parsed from the captured files)."""
import csv, glob, json, os, re, sys
R = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results')
ANSI = re.compile(r'\x1b\[[0-9;?]*[A-Za-z]|\x1b[78]|\r')
rows = []
for d in sorted(glob.glob(os.path.join(R, '*/session.log'))):
    d = os.path.dirname(d); name = os.path.basename(d)
    log = ANSI.sub('', open(os.path.join(d, 'session.log'), encoding='utf-8', errors='replace').read())
    steps = {r['step']: r for r in csv.DictReader(open(os.path.join(d, 'steps.tsv')), delimiter='\t')}
    notes = dict(l.strip().split('=', 1) for l in open(os.path.join(d, 'notes.txt')) if '=' in l)
    host = dict(kv.split('=', 1) for kv in open(os.path.join(d, 'host.txt')).read().split() if '=' in kv)
    osr = dict(l.strip().split('=', 1) for l in open(os.path.join(d, 'os-release.txt')) if '=' in l)
    m = re.search(r'^tesseract v?(\S+)\n\s*leptonica-(\S+)', log, re.M)
    langs = re.search(r'List of available languages[^\n]*\((\d+)\):\n', log.split('# tesseract --list-langs')[-1])
    if langs:
        n_l = int(langs.group(1)); rest = log.split('# tesseract --list-langs')[-1][langs.end():].split('\n')
        langs_txt = f"{n_l}: " + ' '.join(rest[:min(n_l, 6)]) + (' ...' if n_l > 6 else '')
    def t(*names):
        v = [float(steps[n]['seconds']) for n in names if n in steps and steps[n]['seconds']]
        return round(sum(v), 2) if v else ''
    install_steps = [s for s in ('update', 'sync', 'refresh', 'prereq', 'add-ppa', 'install', 'install-eng') if s in steps]
    seg = log[log.find('# ' + steps['install']['command']):] if 'install' in steps else log
    dl = re.search(r'(Need to get [^\n]*|Total size of inbound packages[^\n]*|Total Download Size: *[^\n]*|Package download size: *[^\n]*|Total: +[\d.]+ [MG]B)', seg)
    inst = re.search(r'(After this operation, [^\n]*|Total Installed Size: *[^\n]*|OK: [^\n]* in \d+ packages|[\d.]+ MiB +required by packages that will be installed)', seg)
    oks = re.findall(r'OK: [\d.]+ MiB in \d+ packages', log)
    if oks and inst and inst.group(1).startswith('OK:'):
        inst = None; ok_last = f'{oks[0]} after tesseract-ocr; {oks[-1]} after tesseract-ocr-data-eng (whole system)' if len(oks) > 1 else oks[0]
    else:
        ok_last = None
    lc = None
    if 'langs-count' in steps:
        seg = log.split('langs-count')[0]
        mm = re.findall(r'\n(\d+)\n', log[log.find(steps['langs-count']['command']):][:400])
        lc = mm[0] if mm else ''
    kb = lambda k: int(notes[k]) if k in notes else None
    rows.append({
        'flavour': name, 'os': osr.get('PRETTY_NAME', '').strip('"'),
        'tesseract': m.group(1) if m else '', 'leptonica': m.group(2) if m else '',
        'install_cmd_seconds': t('install', 'install-eng'), 'update_seconds': t('update', 'sync', 'refresh'),
        'all_steps_to_installed_seconds': t(*install_steps), 'first_ocr_seconds': t('ocr'),
        'pm_download': dl.group(1).strip() if dl else '', 'pm_installed': ok_last or (inst.group(1).strip() if inst else ''),
        'rootfs_growth_MiB_after_cache_clean': round((kb('rootfs_kb_after') - kb('rootfs_kb_before')) / 1024, 1) if kb('rootfs_kb_after') else '',
        'conda_env_growth_MiB': round((kb('conda_kb_after') - kb('conda_kb_before')) / 1024, 1) if kb('conda_kb_after') else '',
        'langs_listed': langs_txt if langs else '',
        'language_packages_available': lc or '', 'image_pull_seconds': host.get('pull_seconds', ''),
        'source': f'install/linux/results/{name}/session.cast',
    })
with open(os.path.join(R, 'summary.tsv'), 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]), delimiter='\t'); w.writeheader(); w.writerows(rows)
for r in rows: print(json.dumps(r))
