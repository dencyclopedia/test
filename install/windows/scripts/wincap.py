"""Shared helpers for Windows captures on GitHub Actions runners (Windows Server 2025).
Screenshots: full desktop (raw) and a crop of one window, as PNG."""
import ctypes, ctypes.wintypes as wt, json, os, subprocess, sys, time
from PIL import ImageGrab

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass
user32 = ctypes.windll.user32
OUT = os.environ.get('CAP_OUT', 'out')
os.makedirs(OUT, exist_ok=True)
LOG = os.path.join(OUT, 'log.txt')
T0 = time.time()

def log(*a):
    line = ' '.join(str(x) for x in a)
    stamp = time.strftime('%H:%M:%S', time.gmtime())
    print(f'[{stamp}] {line}', flush=True)
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(f'[{stamp} UTC +{time.time()-T0:7.1f}s] {line}\n')

def window_rect(hwnd):
    r = wt.RECT()
    # DWM extended frame bounds = visible window without the invisible resize border
    try:
        ctypes.windll.dwmapi.DwmGetWindowAttribute(hwnd, 9, ctypes.byref(r), ctypes.sizeof(r))
    except Exception:
        user32.GetWindowRect(hwnd, ctypes.byref(r))
    return r.left, r.top, r.right, r.bottom

def shot(name, hwnd=None, desktop=True):
    """Save <name>.png (window crop if hwnd given) and <name>-desktop.png (full screen)."""
    time.sleep(0.6)
    img = ImageGrab.grab(all_screens=True)
    files = []
    if desktop or not hwnd:
        p = os.path.join(OUT, f'{name}-desktop.png' if hwnd else f'{name}.png'); img.save(p); files.append(p)
    if hwnd:
        l, t, r, b = window_rect(hwnd)
        l, t = max(l, 0), max(t, 0); r, b = min(r, img.width), min(b, img.height)
        if r - l > 20 and b - t > 20:
            p = os.path.join(OUT, f'{name}.png'); img.crop((l, t, r, b)).save(p); files.append(p)
    log('screenshot', ', '.join(os.path.basename(f) for f in files))
    return files

def top_windows():
    res = []
    @ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
    def cb(h, _):
        if user32.IsWindowVisible(h):
            n = user32.GetWindowTextLengthW(h)
            buf = ctypes.create_unicode_buffer(n + 1); user32.GetWindowTextW(h, buf, n + 1)
            cls = ctypes.create_unicode_buffer(256); user32.GetClassNameW(h, cls, 256)
            pid = wt.DWORD(); user32.GetWindowThreadProcessId(h, ctypes.byref(pid))
            res.append((h, buf.value, cls.value, pid.value))
        return True
    user32.EnumWindows(cb, 0)
    return res

def minimize_all(keep=()):
    """Minimise every visible top-level window (incl. the runner's own console) except `keep` hwnds."""
    for h, title, cls, pid in top_windows():
        if h in keep or cls in ('Shell_TrayWnd', 'Progman', 'WorkerW', 'Shell_SecondaryTrayWnd'):
            continue
        if title:
            user32.ShowWindow(h, 6)  # SW_MINIMIZE
    time.sleep(1)

def find_window(substr, timeout=30):
    end = time.time() + timeout
    while time.time() < end:
        for h, title, cls, pid in top_windows():
            if substr.lower() in title.lower():
                return h
        time.sleep(0.5)
    return None

def bring_front(hwnd):
    user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.5)

def console(title, batch_lines, name, wait_marker=True, launcher='direct', timeout=180, cwd=None):
    """Open a NEW console window running a .bat file, wait until it finishes, screenshot it, close it.
    launcher='direct': child of this process (inherits this process's environment);
    launcher='explorer': started by explorer.exe, i.e. like a terminal opened from the Start menu,
    which picks up PATH changes broadcast with WM_SETTINGCHANGE."""
    cwd = cwd or os.getcwd()
    marker = os.path.join(os.environ.get('TEMP', '.'), f'done-{name}.txt')
    if os.path.exists(marker): os.remove(marker)
    bat = os.path.join(os.environ.get('TEMP', '.'), f'{name}.bat')
    with open(bat, 'w', encoding='utf-8') as f:
        f.write('@echo off\r\nchcp 65001 >nul\r\n' + f'title {title}\r\ncd /d "{cwd}"\r\n' + '\r\n'.join(batch_lines) + f'\r\necho done> "{marker}"\r\n')
    minimize_all()
    if launcher == 'explorer':
        subprocess.Popen(['explorer.exe', bat])
    else:
        subprocess.Popen(['cmd.exe', '/k', bat], creationflags=subprocess.CREATE_NEW_CONSOLE, cwd=cwd)
    end = time.time() + timeout
    while time.time() < end and not os.path.exists(marker):
        time.sleep(1)
    log(f'console {name}: finished={os.path.exists(marker)} launcher={launcher}')
    time.sleep(1.5)
    h = find_window(title, timeout=10)
    if h: bring_front(h)
    files = shot(name, h)
    if h: user32.PostMessageW(h, 0x0010, 0, 0)  # WM_CLOSE
    time.sleep(1)
    return files

def ps_console(title, ps_lines, name, launcher='direct', timeout=180, exe='powershell.exe'):
    """Same as console() but for Windows PowerShell 5.1 (the PowerShell every Windows install has)."""
    marker = os.path.join(os.environ.get('TEMP', '.'), f'done-{name}.txt')
    if os.path.exists(marker): os.remove(marker)
    ps1 = os.path.join(os.environ.get('TEMP', '.'), f'{name}.ps1')
    with open(ps1, 'w', encoding='utf-8-sig') as f:
        f.write(f'$Host.UI.RawUI.WindowTitle = "{title}"\r\nSet-Location "{os.getcwd()}"\r\n' + '\r\n'.join(ps_lines) + f'\r\n"done" | Out-File "{marker}"\r\n')
    minimize_all()
    args = [exe, '-NoExit', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ps1]
    if launcher == 'explorer':
        bat = ps1[:-4] + '-launch.bat'
        with open(bat, 'w') as f: f.write('@start "" ' + ' '.join(f'"{a}"' for a in args) + '\r\n')
        subprocess.Popen(['explorer.exe', bat])
    else:
        subprocess.Popen(args, creationflags=subprocess.CREATE_NEW_CONSOLE)
    end = time.time() + timeout
    while time.time() < end and not os.path.exists(marker):
        time.sleep(1)
    log(f'ps console {name}: finished={os.path.exists(marker)}')
    time.sleep(1.5)
    h = find_window(title, timeout=10)
    if h: bring_front(h)
    files = shot(name, h)
    if h: user32.PostMessageW(h, 0x0010, 0, 0)
    time.sleep(1)
    return files

def dir_size(path):
    total, n = 0, 0
    for root, dirs, files in os.walk(path):
        for fn in files:
            try:
                total += os.path.getsize(os.path.join(root, fn)); n += 1
            except OSError:
                pass
    return total, n

def registry_path():
    import winreg
    vals = {}
    for hive, key, label in ((winreg.HKEY_LOCAL_MACHINE, r'SYSTEM\CurrentControlSet\Control\Session Manager\Environment', 'machine'),
                             (winreg.HKEY_CURRENT_USER, r'Environment', 'user')):
        try:
            with winreg.OpenKey(hive, key) as k:
                vals[label] = winreg.QueryValueEx(k, 'Path')[0]
        except OSError:
            vals[label] = ''
    return vals

def broadcast_env_change():
    r = ctypes.c_ulong()
    user32.SendMessageTimeoutW(0xFFFF, 0x001A, 0, 'Environment', 0x0002, 5000, ctypes.byref(r))
