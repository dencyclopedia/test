#!/usr/bin/env python3
"""Disk space of a default Tesseract install vs one with every language, read from the install captures.

Writes tools/images/raw/install/install-sizes.csv (read by the site's chart generator,
ops/tools/charts/specs/install.json). Every number is parsed from a captured file; nothing is typed in.

  Windows installer   install/windows/gui-default/result.json, gui-all/result.json  (installed_bytes, sum of file sizes)
  Scoop               install/windows/scoop/result.json  (installed_bytes; + languages_bytes of tesseract-languages)
  Homebrew (arm64)    install/macos/brew-macos-latest/macos-terminal-01/-05 *.log  (Homebrew's own "files, N MB" line)
  apt (Ubuntu 24.04)  install/linux/results/ubuntu-24.04/session.log  ("After this operation, N MB" for
                      tesseract-ocr, then for tesseract-ocr-all with tesseract-ocr already installed)
MB = 10^6 bytes, as each tool prints it.

usage: python3 tools/images/figures/install_sizes.py
"""
import csv
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
I = os.path.join(REPO, "install")
OUT = os.path.join(REPO, "tools", "images", "raw", "install", "install-sizes.csv")


def rj(p):
    return json.load(open(os.path.join(I, p)))


def grep(p, rx, n=None):
    t = re.sub(r"\x1b\[[0-9;]*m", "", open(os.path.join(I, p), encoding="utf-8", errors="replace").read())
    m = re.findall(rx, t)
    return [float(x) for x in m] if n is None else float(m[n])


rows = []
d, a = rj("windows/gui-default/result.json"), rj("windows/gui-all/result.json")
rows += [("win-default", "Windows installer · default", round(d["installed_bytes"] / 1e6, 1), "windows/gui-default/result.json"),
         ("win-all", "Windows installer · all languages", round(a["installed_bytes"] / 1e6, 1), "windows/gui-all/result.json")]
s = rj("windows/scoop/result.json")
rows += [("scoop-default", "Scoop · tesseract", round(s["installed_bytes"] / 1e6, 1), "windows/scoop/result.json"),
         ("scoop-all", "Scoop · + tesseract-languages", round((s["installed_bytes"] + s["languages_bytes"]) / 1e6, 1), "windows/scoop/result.json")]
b = grep("macos/brew-macos-latest/macos-terminal-01-brew-install-tesseract.log", r"Cellar/tesseract/[\d.]+: \d+ files, ([\d.]+)MB", 0)
bl = grep("macos/brew-macos-latest/macos-terminal-05-brew-install-tesseract-lang.log", r"Cellar/tesseract-lang/[\d.]+: \d+ files, ([\d.]+)MB", 0)
rows += [("brew-default", "Homebrew · tesseract", b, "macos/brew-macos-latest/macos-terminal-01-brew-install-tesseract.log"),
         ("brew-all", "Homebrew · + tesseract-lang", round(b + bl, 1), "macos/brew-macos-latest/macos-terminal-05-brew-install-tesseract-lang.log")]
after = grep("linux/results/ubuntu-24.04/session.log", r"After this operation, ([\d.]+) MB of additional")
# order in the transcript: tesseract-ocr, libtesseract-dev (--assume-no), tesseract-ocr-all (--assume-no)
rows += [("apt-default", "apt · tesseract-ocr", after[0], "linux/results/ubuntu-24.04/session.log"),
         ("apt-all", "apt · + tesseract-ocr-all", round(after[0] + after[2], 1), "linux/results/ubuntu-24.04/session.log")]
with open(OUT, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["key", "label", "mb", "source"])
    w.writerows(rows)
print(open(OUT).read())
