"""Open a fresh console from Explorer (like the Start menu) and screenshot `where tesseract` + version.
usage: fresh_console_shot.py <name> [extra command ...]"""
import os, sys
os.environ.setdefault('CAP_OUT', 'out')
from wincap import console
name = sys.argv[1]
extra = sys.argv[2:]
lines = ['echo C:\\^> where tesseract', 'where tesseract', 'echo C:\\^> tesseract --version', 'tesseract --version']
for c in extra:
    lines += [f'echo C:\\^> {c}', c]
console(f'{name} - fresh cmd window', lines, name, launcher='explorer')
