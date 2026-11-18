# Real error messages captured during the install tests

Every message below is copied from a captured file (path given). Nothing was typed in by hand.
Machines: GitHub Actions `windows-latest` = Windows Server 2025 Datacenter build 26100 (not Windows 11); `macos-latest` = macOS 26.7.2 arm64 (Apple M1, virtual);
`macos-15-intel` = macOS 15.7.9 x86_64; `ubuntu-24.04` runner with clean Docker containers for each Linux distribution.

## 1. Command not found after installing (PATH)

**Windows, cmd.exe**, new window opened through Explorer after the UB Mannheim GUI install (also after `winget install UB-Mannheim.TesseractOCR` and `winget install tesseract-ocr.tesseract`):
```
INFO: Could not find files for the given pattern(s).
'tesseract' is not recognized as an internal or external command,
operable program or batch file.
```
Captured: `windows/gui-default/windows-path-01-cmd-not-recognized.png` + `.txt`; `windows/winget/log.txt`, `windows/winget-tesseract-ocr/log.txt` ("after install" section).

**Windows PowerShell 5.1** (`powershell.exe`):
```
tesseract : The term 'tesseract' is not recognized as the name of a cmdlet, function, script file, or operable
program. Check the spelling of the name, or if a path was included, verify that the path is correct and try again.
At line:1 char:1
+ tesseract --version
+ ~~~~~~~~~
    + CategoryInfo          : ObjectNotFound: (tesseract:String) [], CommandNotFoundException
    + FullyQualifiedErrorId : CommandNotFoundException
```
Captured: `windows/gui-default/windows-path-02-powershell-not-recognized.png` + `.txt`.

**PowerShell 7** (`pwsh.exe`):
```
tesseract: The term 'tesseract' is not recognized as a name of a cmdlet, function, script file, or executable program.
Check the spelling of the name, or if a path was included, verify that the path is correct and try again.
```
Captured: `windows/gui-default/windows-path-02-pwsh7-not-recognized.txt`.

**Cause:** the UB Mannheim installer (5.5.3.20260724 and 5.4.0.20240606) and both winget packages do not touch PATH (registry Machine and User Path checked: `windows/gui-default/path-result.json`, `windows/winget*/result.json`).
**Fix that worked:** add `C:\Program Files\Tesseract-OCR` to Path in *Environment Variables* and open a new terminal (`windows/gui-default/windows-path-05-user-path-*.png`, then `windows-path-07-cmd-working.png`).
Chocolatey adds it to the machine Path itself; Scoop adds `%USERPROFILE%\scoop\shims` to the user Path (`windows/choco/log.txt`, `windows/scoop/log.txt`).

**Linux shells before installing** (from the transcripts): `sh: 1: tesseract: not found` (Debian, Ubuntu, conda image), `sh: line 1: tesseract: command not found` (Fedora, Arch, openSUSE), `sh: tesseract: not found` (Alpine). Captured: `linux/results/<distro>/session.cast`.

## 2. Windows refuses to edit a long system Path

```
This environment variable is too large. This dialog allows setting values up to 2047 characters long.
```
Dialog title "System Properties". Captured: `windows/gui-default/windows-path-04-system-path-d-message-box.png` + `.txt`.
**Cause:** on this runner the system Path is 2,508 characters (`windows/gui-default/path-result.json`), over the dialog's 2,047 limit. A normal desktop usually has a much shorter Path, so most users will not see this.
**Fix that worked here:** Cancel, then add the folder to the **user** Path (103 characters) in the same dialog (`windows-path-05-user-path-a..c.png`, `windows-path-06-environment-variables-after.png`). A new cmd window then found `C:\Program Files\Tesseract-OCR\tesseract.exe` (`windows-path-07-cmd-working.png`).

## 3. Language data missing or in the wrong place

Same text on every OS; only the path differs.

`-l xyz` (language not installed), Windows:
```
Error opening data file C:\Program Files\Tesseract-OCR/tessdata/xyz.traineddata
Please make sure the TESSDATA_PREFIX environment variable is set to your "tessdata" directory.
Failed loading language 'xyz'
Tesseract couldn't load any languages!
Could not initialize tesseract.
```
Captured: `windows/gui-default/windows-error-01-tessdata-and-language.png` + `.txt`; macOS (`-l fra` before `tesseract-lang`): `macos/brew-macos-latest/macos-terminal-04-error-missing-language.png` + `.log` (path `/opt/homebrew/share/tessdata/fra.traineddata`);
Linux: every `linux/results/*/session.cast` (e.g. Ubuntu 22.04: `/usr/share/tesseract-ocr/4.00/tessdata/xyz.traineddata`).
**Fix:** install the language (`brew install tesseract-lang`, `apt-get install tesseract-ocr-<lang>`, tick it in the Windows installer) — after `brew install tesseract-lang`, `-l eng+fra` worked (`macos-terminal-06-ocr-french-after-lang.log`).

`--tessdata-dir C:\wrong\tessdata`:
```
Error opening data file C:\wrong\tessdata/eng.traineddata
...
Failed loading language 'eng'
```
`set TESSDATA_PREFIX=C:\Users` (folder without eng.traineddata):
```
Error opening data file C:\Users/eng.traineddata
...
```
Captured: `windows/gui-default/windows-error-01-tessdata-and-language.txt`; Linux equivalents (`--tessdata-dir /nonexistent`, `TESSDATA_PREFIX=/tmp`) in every Linux transcript.
**Fix:** point `--tessdata-dir` / `TESSDATA_PREFIX` at the folder that contains `eng.traineddata` (the folder printed by `tesseract --list-langs`), or unset it.

**Package installs that ship no language at all** (OCR fails right after a "successful" install with the `eng.traineddata` message above):
- Alpine: `apk add tesseract-ocr` -> `List of available languages in "/usr/share/tessdata/" (0):` and `Error opening data file /usr/share/tessdata/eng.traineddata`. Fix: `apk add tesseract-ocr-data-eng` (`linux/results/alpine/session.cast`).
- Scoop: `scoop install tesseract` -> `Error opening data file C:\Users\runneradmin\scoop\persist\tesseract\tessdata/eng.traineddata`. Fix: `scoop install tesseract-languages` (162 languages, 700.4 MB) (`windows/scoop/log.txt`).
- MacPorts: `sudo port install tesseract` -> `List of available languages in "/opt/local/share/tessdata/" (0):` and `Error opening data file /opt/local/share/tessdata/eng.traineddata`. Fix: `sudo port install tesseract-eng` (`macos/macports/macports.txt`).

## 4. Python: pytesseract cannot find the binary

```
pytesseract.pytesseract.TesseractNotFoundError: tesseract is not installed or it's not in your PATH. See README file for more information.
```
(preceded by `FileNotFoundError: [WinError 2] The system cannot find the file specified` on Windows and `FileNotFoundError: [Errno 2] No such file or directory: 'tesseract'` on macOS).
Captured: Windows `windows/gui-default/windows-error-pytesseract-not-found.png` + `.txt` (Tesseract installed, PATH not set); macOS `macos/brew-macos-latest/macos-terminal-07-error-pytesseract-not-found.png` + `.log` (PATH without `/opt/homebrew/bin`).
**Fix that worked:** put the Tesseract folder on PATH (Windows: `windows-path-10-pytesseract-working.png`; macOS: same script with the normal PATH, second command in the `.log`).

## 5. Input file not found

```
Error, cannot read input file nosuchfile.png: No such file or directory
Error during processing.
```
Captured: `windows/gui-default/windows-error-01-tessdata-and-language.txt`; Linux transcripts (`/samples/missing.png`).

## 6. Ubuntu 22.04 resolution warning (Tesseract 4.1.1)

```
Warning: Invalid resolution 0 dpi. Using 70 instead.
Estimating resolution as 246
```
Printed before the OCR text of `samples/receipt.png` on Ubuntu 22.04 only (`linux/results/ubuntu-22.04/session.cast`); the text was still recognised.

## 7. Things that are not errors but surprise people

- **Arch:** `pacman -S --noconfirm tesseract` without naming a data package would pick `tesseract-data-afr` (Afrikaans) as the tessdata provider (`pacman -Sp` output in `linux/results/archlinux/session.cast`).
- **winget:** `UB-Mannheim.TesseractOCR` still installs 5.4.0.20240606; the newer 5.5.3 build is under the id `tesseract-ocr.tesseract` (`windows/winget/log.txt`, search results).
- **Authenticode on the 5.5.3 installer:** `Get-AuthenticodeSignature` on the runner returned `UnknownError` with "A required certificate is not within its validity period when verifying against the current system clock or the timestamp in the signed file." (signer CN=Universität Mannheim) (`windows/gui-default/download.txt`). The installer was downloaded with `Invoke-WebRequest` (no Mark-of-the-Web), so whether SmartScreen warns on a browser download was **not** tested.
- **Intel Mac:** on `macos-15-intel` (Homebrew 6.0.18) `brew install tesseract` started compiling dependencies from source (`readline`, `sqlite`, `xz`, `lz4`, `python@3.15`, `icu4c@79` ... each "built in" minutes); the formula JSON taken before `brew update` listed a bottle only for `sonoma`. After the 30-minute limit of that capture it was still compiling (`macos/brew-macos-15-intel/macos-terminal-01-brew-install-tesseract.png`), so the next Terminal commands printed `tesseract not found` (`which`) and `command not found: tesseract` (zsh) (`macos-terminal-02-version.log`). See `macos/README.md`.
