"""Drive the UB Mannheim NSIS installer through every wizard page with pywinauto (win32 backend),
screenshotting each page. usage: gui_install.py <installer.exe> <mode: default|all>
mode=all ticks 'Additional script data' and 'Additional language data' on the components page."""
import json, os, re, sys, time
os.environ.setdefault('CAP_OUT', 'out')
from wincap import log, shot, minimize_all, dir_size
from pywinauto import Application
from pywinauto.timings import TimeoutError as PwaTimeout

exe, mode = sys.argv[1], sys.argv[2]
prefix = 'windows-installer'
n = 0
def name(slug):
    global n; n += 1
    return f'{prefix}-{n:02d}-{slug}'
def slugify(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')[:40] or 'page'

result = {'mode': mode, 'installer': os.path.basename(exe)}
minimize_all()
t_start = time.time()
app = Application(backend='win32').start(f'"{exe}"', wait_for_idle=False)
log('installer started', exe)

# 1. language selection dialog
lang = app.window(title='Installer Language')
lang.wait('visible', timeout=60)
lang.set_focus()
shot(name('language'), lang.handle)
try:
    result['language_choices_count'] = len(lang.child_window(class_name='ComboBox').wrapper_object().item_texts())
    log('language combobox items:', result['language_choices_count'])
except Exception as e:
    log('combobox read failed', e)
lang.child_window(title='OK', class_name='Button').click()

def page_info(w):
    texts = []
    for c in w.descendants():
        try:
            if c.is_visible() and c.window_text().strip():
                texts.append((c.class_name(), c.control_id(), c.window_text().strip()))
        except Exception:
            pass
    return texts

def header_of(texts):
    for cls, cid, t in texts:
        if cid in (1037, 1201):  # MUI header title / welcome-finish title
            return t
    return texts[0][2] if texts else 'page'

seen = []
install_click = None
for step in range(30):
    time.sleep(1.2)
    w = app.top_window()
    w.wait('visible', timeout=60)
    try: w.set_focus()
    except Exception: pass
    texts = page_info(w)
    header = header_of(texts)
    btn = w.child_window(control_id=1, class_name='Button')
    btext = btn.window_text()
    log(f'page: {header!r} | button1={btext!r} enabled={btn.is_enabled()} | window title={w.window_text()!r}')
    with open(os.path.join(os.environ['CAP_OUT'], 'pages.txt'), 'a', encoding='utf-8') as f:
        f.write(f'== {header} ==\n' + '\n'.join(f'  [{c} id={i}] {t}' for c, i, t in texts) + '\n')
    seen.append(header)

    trees = w.children(class_name='SysTreeView32')
    if trees and seen.count(header) > 1:  # already handled; the Next click did not register
        log('components page again: clicking Next with the mouse'); btn.click_input(); continue
    if trees:  # components page
        tree = trees[0]
        def space_text():
            return ' | '.join(t for c, i, t in page_info(w) if 'space' in t.lower() or 'MB' in t or 'GB' in t)
        result['space_required_default'] = space_text(); log('space text (default selection):', result['space_required_default'])
        shot(name('components'), w.handle)
        items = []
        def walk(it, depth):
            items.append(('  ' * depth) + it.text())
            for ch in it.children(): walk(ch, depth + 1)
        for r in tree.roots(): walk(r, 0)
        with open(os.path.join(os.environ['CAP_OUT'], 'components-tree.txt'), 'w', encoding='utf-8') as f:
            f.write('\n'.join(items) + '\n')
        log('component tree items:', len(items))
        targets = []
        def find(it):
            if it.text().startswith('Additional script data') or it.text().startswith('Additional language data'):
                targets.append(it)
            for ch in it.children(): find(ch)
        for r in tree.roots(): find(r)
        for it in targets:
            label = it.text()
            it.ensure_visible(); it.expand(); time.sleep(0.5)
            # scroll so the expanded group starts at the top of the list
            try:
                kids = it.children()
                if kids: kids[min(len(kids)-1, 12)].ensure_visible()
                it.ensure_visible()
            except Exception as e:
                log('scroll', e)
            result.setdefault('groups', {})[label] = len(it.children())
            log(f'expanded {label!r}: {len(it.children())} children')
            shot(name('components-' + slugify(label.split('(')[0])), w.handle)
            if mode == 'all':
                before = space_text(); st0 = (it.state() >> 12) & 0xF
                it.ensure_visible(); r = it.rectangle(text_area_only=True)
                # real mouse click on the checkbox (state icon), which sits just left of the label
                tree.click_input(coords=(r.left - 9, (r.top + r.bottom) // 2)); time.sleep(0.8)
                st1 = (it.state() >> 12) & 0xF
                if st1 == st0:
                    log('mouse click did not change the state image; trying the space key')
                    it.select(); tree.set_focus(); tree.type_keys('{SPACE}'); time.sleep(0.8); st1 = (it.state() >> 12) & 0xF
                after = space_text()
                log(f'ticked {label!r}: state image {st0} -> {st1}; space {before!r} -> {after!r}')
                shot(name('components-' + slugify(label.split('(')[0]) + '-ticked'), w.handle)
            it.collapse()
        result['space_required_selected'] = space_text()
        log('space text (final selection):', result['space_required_selected'])
        if mode == 'all':
            shot(name('components-all-ticked'), w.handle)
        btn.click_input()
        continue

    if not btn.is_enabled():  # installing
        shot(name('installing'), w.handle)
        k = 0
        while not w.child_window(control_id=1, class_name='Button').is_enabled():
            time.sleep(2); k += 1
            if k in (5, 30, 150):
                shot(name('installing-progress'), w.handle)
            if k > 1800: raise SystemExit('install did not finish in 60 min')
        result['installing_seconds'] = round(time.time() - (install_click or time.time()), 1)
        log('installing finished after', result['installing_seconds'], 's since Install click')
        continue

    shot(name(slugify(header)), w.handle)
    if 'finish' in btext.lower():
        # record finish-page checkboxes, then click Finish
        for c in w.children(class_name='Button'):
            if c.control_id() not in (1, 2, 3) and c.is_visible():
                log('finish page option:', c.window_text(), 'checked=', c.get_check_state() if hasattr(c, 'get_check_state') else '?')
                try:
                    if c.get_check_state() == 1: c.uncheck()  # don't open README in a browser
                except Exception: pass
        btn.click()
        break
    if 'install' == btext.replace('&', '').strip().lower():
        install_click = time.time()
    btn.click()

try:
    app.wait_for_process_exit(timeout=60)
except Exception as e:
    log('process exit wait', e)
result['wizard_total_seconds_incl_screenshots'] = round(time.time() - t_start, 1)
result['pages'] = seen
d = r'C:\Program Files\Tesseract-OCR'
size, files = dir_size(d)
result['install_dir'] = d; result['installed_bytes'] = size; result['installed_files'] = files
td = os.path.join(d, 'tessdata')
result['traineddata_files'] = sorted(f for f in os.listdir(td) if f.endswith('.traineddata')) if os.path.isdir(td) else []
result['tessdata_bytes'] = dir_size(td)[0] if os.path.isdir(td) else 0
log(json.dumps({k: v for k, v in result.items() if k != 'traineddata_files'}, indent=1))
log('traineddata count:', len(result['traineddata_files']))
json.dump(result, open(os.path.join(os.environ['CAP_OUT'], 'result.json'), 'w'), indent=1)
