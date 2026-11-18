"""After the GUI install (default components): show the PATH problem and its fix, plus real errors.
Every console screenshot is a NEW window; its text output is also written to <name>.txt."""
import json, os, subprocess, sys, time
os.environ.setdefault('CAP_OUT', 'out')
from wincap import log, shot, console, ps_console, minimize_all, find_window, bring_front, registry_path, broadcast_env_change, user32
OUT = os.environ['CAP_OUT']
TD = r'C:\Program Files\Tesseract-OCR'
SAMPLE = os.path.abspath(r'samples\receipt.png')
res = {}

def txt(name, cmdline, shell='cmd'):
    """Run the same commands without a window to keep exact text (stdout+stderr)."""
    if shell == 'cmd':
        p = subprocess.run(['cmd.exe', '/d', '/c', cmdline], capture_output=True, text=True, encoding='utf-8', errors='replace')
    else:
        p = subprocess.run([shell, '-NoProfile', '-Command', cmdline], capture_output=True, text=True, encoding='utf-8', errors='replace')
    out = f'> {cmdline}\n{p.stdout}{p.stderr}[exit code {p.returncode}]\n'
    with open(os.path.join(OUT, name + '.txt'), 'a', encoding='utf-8') as f: f.write(out)
    log(f'{name}: exit {p.returncode}')
    return p

reg = registry_path()
res['registry_path_has_tesseract_after_gui_install'] = {k: ('tesseract' in v.lower()) for k, v in reg.items()}
log('registry PATH contains Tesseract-OCR after GUI install:', res['registry_path_has_tesseract_after_gui_install'])

# --- 1. the "not recognized" errors (a fresh console started from Explorer = like the Start menu)
console('cmd - tesseract not recognized', ['echo %CD%^> where tesseract', 'where tesseract', 'echo.', 'echo %CD%^> tesseract --version', 'tesseract --version'],
        'windows-path-01-cmd-not-recognized', launcher='explorer')
txt('windows-path-01-cmd-not-recognized', 'where tesseract & tesseract --version')
ps_console('PowerShell - tesseract not recognized', ['Write-Host "PS $PWD> tesseract --version"', 'tesseract --version'],
           'windows-path-02-powershell-not-recognized', launcher='explorer')
txt('windows-path-02-powershell-not-recognized', 'tesseract --version', shell='powershell.exe')
txt('windows-path-02-pwsh7-not-recognized', 'tesseract --version', shell='pwsh.exe')

# --- 2. Python: pytesseract without tesseract on PATH
pyfile = os.path.join(os.environ['TEMP'], 'ocr_test.py')
with open(pyfile, 'w') as f:
    f.write('import pytesseract\nfrom PIL import Image\n'
            f'print(pytesseract.image_to_string(Image.open(r"{SAMPLE}")))\n')
PY = sys.executable
console('Python - pytesseract', [f'echo %CD%^> "{PY}" "{pyfile}"', f'"{PY}" "{pyfile}"'], 'windows-error-pytesseract-not-found', launcher='explorer')
txt('windows-error-pytesseract-not-found', f'"{PY}" "{pyfile}"')

# --- 3. the fix: Environment Variables dialog. Try the System Path first (what most guides say);
# if Windows refuses (runner's system Path is longer than the dialog's 2047-char limit), cancel and
# add it to the User Path instead. Everything that happens is screenshotted and logged.
fixed_by = None
res['system_path_length_chars'] = len(registry_path()['machine'])
res['user_path_length_chars'] = len(registry_path()['user'])
log('system Path length:', res['system_path_length_chars'], 'user Path length:', res['user_path_length_chars'])
from pywinauto import Application, Desktop

def other_windows(app, exclude):
    return [tw for tw in Desktop(backend='win32').windows(process=app.process) if tw.handle not in exclude and tw.is_visible()]

def edit_path(app, dlg, h, which, prefix):
    """which: 0 = user variables list, 1 = system variables list. Returns True if the edit dialog accepted it."""
    lists = dlg.children(class_name='SysListView32')
    lv = lists[which]
    names = [lv.get_item(i).text() for i in range(lv.item_count())]
    idx = [x.lower() for x in names].index('path')
    lv.get_item(idx).ensure_visible(); lv.get_item(idx).click_input(); time.sleep(0.6)
    shot(f'{prefix}-a-path-selected', h)
    edits = [b for b in dlg.children(class_name='Button') if b.window_text().replace('&', '').startswith('Edit')]
    edits.sort(key=lambda b: b.rectangle().top)  # upper = user, lower = system
    edits[which].click_input()
    h2 = None
    for _ in range(20):
        time.sleep(0.5)
        ow = other_windows(app, (h,))
        if ow: h2 = ow[0].handle; break
    ed = app.window(handle=h2); ed.set_focus()
    log(f'[{prefix}] edit dialog:', ed.window_text())
    shot(f'{prefix}-b-edit-before', h2)
    ed.child_window(title_re='&?New', class_name='Button').click_input(); time.sleep(0.6)
    ed.type_keys(r'C:\Program Files\Tesseract-OCR', with_spaces=True); ed.type_keys('{ENTER}'); time.sleep(0.6)
    shot(f'{prefix}-c-edit-added', h2)
    ed.child_window(title='OK', class_name='Button').click_input(); time.sleep(1.5)
    refused = False
    for tw in other_windows(app, (h, h2)):
        texts = [c.window_text() for c in tw.descendants() if c.window_text().strip()]
        log(f'[{prefix}] message box {tw.window_text()!r}: {texts}')
        with open(os.path.join(OUT, f'{prefix}-d-message-box.txt'), 'a', encoding='utf-8') as f:
            f.write(f'{tw.window_text()}\n' + '\n'.join(texts) + '\n')
        shot(f'{prefix}-d-message-box', tw.handle)
        refused = True
        btns = [b for b in tw.children(class_name='Button') if b.is_visible()]
        (btns[0].click_input() if btns else tw.type_keys('{ENTER}')); time.sleep(1.2)
    if ed.exists() and ed.is_visible():
        log(f'[{prefix}] edit dialog still open -> Cancel')
        ed.child_window(title='Cancel', class_name='Button').click_input(); time.sleep(1)
        return False
    return not refused

try:
    minimize_all()
    subprocess.Popen(['rundll32.exe', 'sysdm.cpl,EditEnvironmentVariables'])
    h = find_window('Environment Variables', timeout=20)
    app = Application(backend='win32').connect(handle=h)
    dlg = app.window(handle=h); dlg.set_focus()
    shot('windows-path-03-environment-variables', h)
    ok_sys = edit_path(app, dlg, h, 1, 'windows-path-04-system-path')
    log('system Path accepted by dialog:', ok_sys)
    target = 'system'
    if not ok_sys:
        ok_user = edit_path(app, dlg, h, 0, 'windows-path-05-user-path')
        log('user Path accepted by dialog:', ok_user)
        target = 'user' if ok_user else None
    dlg.set_focus()
    shot('windows-path-06-environment-variables-after', h)
    dlg.child_window(title='OK', class_name='Button').click_input(); time.sleep(3)
    reg = registry_path()
    if target and 'tesseract' in reg['machine' if target == 'system' else 'user'].lower():
        fixed_by = f'Environment Variables dialog ({target} Path), driven with pywinauto'
    else:
        raise RuntimeError('no Path in the registry has a Tesseract-OCR entry after the dialog')
except Exception as e:
    log('GUI PATH edit failed:', repr(e))
    import winreg
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'SYSTEM\CurrentControlSet\Control\Session Manager\Environment', 0, winreg.KEY_ALL_ACCESS) as k:
        cur, typ = winreg.QueryValueEx(k, 'Path')
        if 'tesseract' not in cur.lower():
            winreg.SetValueEx(k, 'Path', 0, typ, cur.rstrip(';') + ';' + TD)
    broadcast_env_change()
    fixed_by = 'FALLBACK: registry write of system Path + WM_SETTINGCHANGE broadcast (GUI edit failed, see log)'
res['path_fixed_by'] = fixed_by
reg = registry_path()
res['registry_path_has_tesseract_after_fix'] = {k: ('tesseract' in v.lower()) for k, v in reg.items()}
log('fixed by:', fixed_by, res['registry_path_has_tesseract_after_fix'])

# --- 4. new console windows after the fix
console('cmd - after PATH fix', ['echo %CD%^> where tesseract', 'where tesseract', 'echo %CD%^> tesseract --version', 'tesseract --version',
                                 'echo %CD%^> tesseract --list-langs', 'tesseract --list-langs'],
        'windows-path-07-cmd-working', launcher='explorer')
console('cmd - OCR receipt', [f'echo %CD%^> tesseract "{SAMPLE}" -', f'tesseract "{SAMPLE}" -'], 'windows-path-08-cmd-ocr-receipt', launcher='explorer')
newenv = dict(os.environ, PATH=reg['machine'] + ';' + reg['user'])
for nm, cl in (('windows-path-07-cmd-working', 'where tesseract & tesseract --version & tesseract --list-langs'),
               ('windows-path-08-cmd-ocr-receipt', f'tesseract "{SAMPLE}" -')):
    p = subprocess.run(['cmd.exe', '/d', '/c', cl], capture_output=True, text=True, env=newenv, encoding='utf-8', errors='replace')
    open(os.path.join(OUT, nm + '.txt'), 'w', encoding='utf-8').write(f'> {cl}\n(PATH re-read from registry)\n{p.stdout}{p.stderr}[exit code {p.returncode}]\n')
ps_console('PowerShell - after PATH fix', ['Write-Host "PS $PWD> tesseract --version"', 'tesseract --version'], 'windows-path-09-powershell-working', launcher='explorer')
console('Python - pytesseract after fix', [f'echo %CD%^> "{PY}" "{pyfile}"', f'"{PY}" "{pyfile}"'], 'windows-path-10-pytesseract-working', launcher='explorer')

# --- 5. other real errors (tesseract now on PATH)
errs = [('missing language', f'tesseract "{SAMPLE}" - -l xyz'),
        ('wrong tessdata dir', f'tesseract "{SAMPLE}" - --tessdata-dir C:\\wrong\\tessdata'),
        ('TESSDATA_PREFIX pointing to wrong folder', f'set TESSDATA_PREFIX=C:\\Users& tesseract "{SAMPLE}" -'),
        ('input file missing', 'tesseract nosuchfile.png -')]
lines = []
for label, cl in errs:
    lines += [f'echo %CD%^> {cl.replace("&", "^&")}', f'cmd /d /c "{cl}"', 'echo.']
console('Tesseract error messages', lines, 'windows-error-01-tessdata-and-language', launcher='explorer')
for label, cl in errs:
    p = subprocess.run(['cmd.exe', '/d', '/c', cl], capture_output=True, text=True, env=newenv, encoding='utf-8', errors='replace')
    with open(os.path.join(OUT, 'windows-error-01-tessdata-and-language.txt'), 'a', encoding='utf-8') as f:
        f.write(f'## {label}\n> {cl}\n{p.stdout}{p.stderr}[exit code {p.returncode}]\n\n')
json.dump(res, open(os.path.join(OUT, 'path-result.json'), 'w'), indent=1)
log('path demo done')
