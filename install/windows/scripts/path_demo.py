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
console('cmd - tesseract not recognized', ['echo C:\\^> where tesseract', 'where tesseract', 'echo.', 'echo C:\\^> tesseract --version', 'tesseract --version'],
        'windows-path-01-cmd-not-recognized', launcher='explorer')
txt('windows-path-01-cmd-not-recognized', 'where tesseract & tesseract --version')
ps_console('PowerShell - tesseract not recognized', ['Write-Host "PS> tesseract --version"', 'tesseract --version'],
           'windows-path-02-powershell-not-recognized', launcher='explorer')
txt('windows-path-02-powershell-not-recognized', 'tesseract --version', shell='powershell.exe')
txt('windows-path-02-pwsh7-not-recognized', 'tesseract --version', shell='pwsh.exe')

# --- 2. Python: pytesseract without tesseract on PATH
pyfile = os.path.join(os.environ['TEMP'], 'ocr_test.py')
with open(pyfile, 'w') as f:
    f.write('import pytesseract\nfrom PIL import Image\n'
            f'print(pytesseract.image_to_string(Image.open(r"{SAMPLE}")))\n')
PY = sys.executable
console('Python - pytesseract', [f'echo C:\\^> "{PY}" ocr_test.py', f'"{PY}" "{pyfile}"'], 'windows-error-pytesseract-not-found', launcher='explorer')
txt('windows-error-pytesseract-not-found', f'"{PY}" "{pyfile}"')

# --- 3. the fix: Environment Variables dialog, edit system Path
fixed_by = None
try:
    from pywinauto import Application, Desktop
    minimize_all()
    subprocess.Popen(['rundll32.exe', 'sysdm.cpl,EditEnvironmentVariables'])
    h = find_window('Environment Variables', timeout=20)
    app = Application(backend='win32').connect(handle=h)
    dlg = app.window(handle=h); dlg.set_focus()
    shot('windows-path-03-environment-variables', h)
    lists = dlg.children(class_name='SysListView32')
    log('listviews:', [(l.control_id(), l.item_count()) for l in lists])
    sysl = lists[1]
    names = [sysl.get_item(i).text() for i in range(sysl.item_count())]
    idx = [x.lower() for x in names].index('path')
    sysl.get_item(idx).select(); sysl.get_item(idx).ensure_visible(); time.sleep(0.5)
    shot('windows-path-04-system-path-selected', h)
    edits = [b for b in dlg.children(class_name='Button') if b.window_text().replace('&', '').startswith('Edit')]
    log('edit buttons:', [(b.control_id(), b.window_text()) for b in edits])
    edits[-1].click()
    h2 = None
    for _ in range(20):
        time.sleep(0.5)
        for tw in Desktop(backend='win32').windows(process=app.process):
            if tw.handle != h and tw.is_visible() and tw.window_text():
                h2 = tw.handle
        if h2: break
    ed = app.window(handle=h2); ed.set_focus()
    log('edit dialog title:', ed.window_text())
    shot('windows-path-05-edit-path-before', h2)
    ed.child_window(title_re='&?New', class_name='Button').click(); time.sleep(0.6)
    ed.type_keys(r'C:\Program Files\Tesseract-OCR', with_spaces=True); ed.type_keys('{ENTER}'); time.sleep(0.6)
    shot('windows-path-06-edit-path-added', h2)
    ed.child_window(title='OK', class_name='Button').click(); time.sleep(1)
    shot('windows-path-07-environment-variables-after', h)
    dlg.child_window(title='OK', class_name='Button').click(); time.sleep(2)
    fixed_by = 'Environment Variables dialog (rundll32 sysdm.cpl,EditEnvironmentVariables), driven with pywinauto'
except Exception as e:
    log('GUI PATH edit failed:', repr(e))
    import winreg
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'SYSTEM\CurrentControlSet\Control\Session Manager\Environment', 0, winreg.KEY_ALL_ACCESS) as k:
        cur, typ = winreg.QueryValueEx(k, 'Path')
        winreg.SetValueEx(k, 'Path', 0, typ, cur.rstrip(';') + ';' + TD)
    broadcast_env_change()
    fixed_by = 'FALLBACK: registry write of system Path + WM_SETTINGCHANGE broadcast (GUI edit failed, see log)'
res['path_fixed_by'] = fixed_by
reg = registry_path()
res['registry_path_has_tesseract_after_fix'] = {k: ('tesseract' in v.lower()) for k, v in reg.items()}
log('fixed by:', fixed_by, res['registry_path_has_tesseract_after_fix'])

# --- 4. new console windows after the fix
console('cmd - after PATH fix', ['echo C:\\^> where tesseract', 'where tesseract', 'echo C:\\^> tesseract --version', 'tesseract --version',
                                 'echo C:\\^> tesseract --list-langs', 'tesseract --list-langs'],
        'windows-path-08-cmd-working', launcher='explorer')
console('cmd - OCR receipt', [f'echo C:\\^> tesseract receipt.png -', f'tesseract "{SAMPLE}" -'], 'windows-path-09-cmd-ocr-receipt', launcher='explorer')
newenv = dict(os.environ, PATH=reg['machine'] + ';' + reg['user'])
for nm, cl in (('windows-path-08-cmd-working', 'where tesseract & tesseract --version & tesseract --list-langs'),
               ('windows-path-09-cmd-ocr-receipt', f'tesseract "{SAMPLE}" -')):
    p = subprocess.run(['cmd.exe', '/d', '/c', cl], capture_output=True, text=True, env=newenv, encoding='utf-8', errors='replace')
    open(os.path.join(OUT, nm + '.txt'), 'w', encoding='utf-8').write(f'> {cl}\n(PATH re-read from registry)\n{p.stdout}{p.stderr}[exit code {p.returncode}]\n')
ps_console('PowerShell - after PATH fix', ['Write-Host "PS> tesseract --version"', 'tesseract --version'], 'windows-path-10-powershell-working', launcher='explorer')
console('Python - pytesseract after fix', [f'echo C:\\^> "{PY}" ocr_test.py', f'"{PY}" "{pyfile}"'], 'windows-path-11-pytesseract-working', launcher='explorer')

# --- 5. other real errors (tesseract now on PATH)
errs = [('missing language', f'tesseract "{SAMPLE}" - -l xyz'),
        ('wrong tessdata dir', f'tesseract "{SAMPLE}" - --tessdata-dir C:\\wrong\\tessdata'),
        ('TESSDATA_PREFIX pointing to wrong folder', f'set TESSDATA_PREFIX=C:\\Users& tesseract "{SAMPLE}" -'),
        ('input file missing', 'tesseract nosuchfile.png -')]
lines = []
for label, cl in errs:
    lines += [f'echo C:\\^> {cl.replace(SAMPLE, "receipt.png").replace("&", "^&")}', f'cmd /d /c "{cl}"', 'echo.']
console('Tesseract error messages', lines, 'windows-error-01-tessdata-and-language', launcher='explorer')
for label, cl in errs:
    p = subprocess.run(['cmd.exe', '/d', '/c', cl], capture_output=True, text=True, env=newenv, encoding='utf-8', errors='replace')
    with open(os.path.join(OUT, 'windows-error-01-tessdata-and-language.txt'), 'a', encoding='utf-8') as f:
        f.write(f'## {label}\n> {cl}\n{p.stdout}{p.stderr}[exit code {p.returncode}]\n\n')
json.dump(res, open(os.path.join(OUT, 'path-result.json'), 'w'), indent=1)
log('path demo done')
