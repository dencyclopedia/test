"""UI helpers for uninstall captures on a GitHub Actions Windows runner (Windows Server 2025).
usage: python uwin.py <action> <shot-name> [arg]
  clean                      minimize the runner's console windows (no screenshot)
  app <name> <exe-stem>      screenshot the app's main window (+ full desktop)
  settings <name> <query>    Settings > Apps > Installed apps, type <query> in "Search apps", screenshot
  cpl <name> <query>         Control Panel > Programs and Features, type <query> in its search box, screenshot
  explorer <name> <path>     open Explorer with <path> selected, screenshot
  desktop <name>             full desktop only
"""
import ctypes, os, subprocess, sys, time
sys.path.insert(0, os.path.join('install', 'windows', 'scripts'))
from wincap import shot, top_windows, log  # noqa: E402

user32 = ctypes.windll.user32

def clean():
    n = 0
    for h, title, cls, pid in top_windows():
        if cls in ('CASCADIA_HOSTING_WINDOW_CLASS', 'ConsoleWindowClass') or title.startswith(('C:\\ProgramData\\GitHub', 'Administrator:')):
            user32.ShowWindow(h, 6); n += 1   # SW_MINIMIZE
    time.sleep(0.5)
    return n

def find(pred, timeout=20):
    end = time.time() + timeout
    while time.time() < end:
        for h, title, cls, pid in top_windows():
            if title and pred(title, cls, pid):
                return h
        time.sleep(0.5)
    return None

def front(h):
    user32.ShowWindow(h, 9)   # SW_RESTORE
    user32.keybd_event(0x12, 0, 0, 0); user32.SetForegroundWindow(h); user32.keybd_event(0x12, 0, 2, 0)
    time.sleep(0.8)

def uia_type(win_title_re, edit_name_re, text):
    from pywinauto import Desktop
    w = Desktop(backend='uia').window(title_re=win_title_re)
    w.wait('visible', timeout=25)
    e = w.child_window(title_re=edit_name_re, control_type='Edit')
    e.wait('visible', timeout=15)
    e.click_input(); e.type_keys(text, with_spaces=True)
    time.sleep(3)
    return w.handle

def main():
    action, name = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else '')
    arg = sys.argv[3] if len(sys.argv) > 3 else ''
    clean()
    if action == 'clean':
        return
    if action == 'app':
        import psutil
        stems = {arg.lower()}
        pids = {p.pid for p in psutil.process_iter(['name']) if (p.info['name'] or '').lower().removesuffix('.exe') in stems}
        h = find(lambda t, c, pid: pid in pids and c not in ('IME', 'MSCTFIME UI'), timeout=15)
        if h:
            front(h); shot(name, h)
        else:
            log(f'no window found for {arg}; desktop only'); shot(name)
    elif action == 'settings':
        subprocess.Popen(['cmd', '/c', 'start', '', 'ms-settings:appsfeatures']); time.sleep(6)
        try:
            h = uia_type('Settings', 'Search apps', arg); front(h); shot(name, h)
        except Exception as ex:
            log('settings search failed:', repr(ex)); h = find(lambda t, c, p: t == 'Settings', 5); shot(name, h)
        subprocess.run(['taskkill', '/IM', 'SystemSettings.exe', '/F'], capture_output=True)
    elif action == 'cpl':
        subprocess.Popen(['control.exe', 'appwiz.cpl']); time.sleep(5)
        try:
            h = uia_type('Programs and Features', 'Search Programs and Features', arg); front(h); shot(name, h)
        except Exception as ex:
            log('control panel search failed:', repr(ex)); h = find(lambda t, c, p: 'Programs and Features' in t, 5); shot(name, h)
        if h: user32.PostMessageW(h, 0x0010, 0, 0)   # WM_CLOSE
    elif action == 'explorer':
        subprocess.Popen(['explorer.exe', f'/select,{arg}']); time.sleep(4)
        h = find(lambda t, c, p: c == 'CabinetWClass', 10)
        if h: front(h)
        shot(name, h)
        if h: user32.PostMessageW(h, 0x0010, 0, 0)
    elif action == 'desktop':
        shot(name)

if __name__ == '__main__':
    main()
