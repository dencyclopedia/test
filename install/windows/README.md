# Windows install captures

**Machine:** GitHub Actions `windows-latest` = **Windows Server 2025 Datacenter, build 26100** (runner image `win25-vs2026 20261103.298.1`), 4 vCPU,
screen 1024x768, running as an administrator account (`runneradmin`). It is a server SKU, not Windows 11. Workflow:
[`.github/workflows/install-windows.yml`](../../.github/workflows/install-windows.yml); final run [44259655152](https://github.com/dencyclopedia/test/actions/runs/44259655152) (see `RUN.txt`).
The UB Mannheim research came from [`install-ubm-research.yml`](../../.github/workflows/install-ubm-research.yml).

Screenshots are real `ImageGrab` captures of the runner's interactive desktop. Each shot exists twice: `name.png` = the window only (cropped by its DWM frame
rectangle), `name-desktop.png` = the whole 1024x768 screen, uncropped. The runner's own console window was minimised first. The wizard was driven with
pywinauto 0.6.9 ([`scripts/gui_install.py`](scripts/gui_install.py)), the PATH steps with [`scripts/path_demo.py`](scripts/path_demo.py).
Console windows were opened **through Explorer** (like starting a terminal from the Start menu), so they read PATH from the registry, not from the script.
On this image the console host is Windows Terminal.

## Where UB Mannheim's 5.5.x installer is (`ub-mannheim/`, captured 2026-11-18)

| Place | What is there |
|---|---|
| [UB-Mannheim/tesseract wiki](https://github.com/UB-Mannheim/tesseract/wiki) (Home.md, last edited 2026-07-24) | "The latest installers can be downloaded here: **tesseract-ocr-w64-setup-5.5.3.20260724.exe** (64 bit)" — the link points to `https://github.com/tesseract-ocr/tesseract/releases/download/5.5.3/tesseract-ocr-w64-setup-5.5.3.20260724.exe`, i.e. an asset of the **upstream tesseract-ocr/tesseract 5.5.3 release**. History list: 2026-07-24 5.5.3, 2024-11-11 5.5.0, 2024-06-06 5.4.0 … |
| `tesseract-ocr/tesseract` releases | 5.5.3 has the asset `tesseract-ocr-w64-setup-5.5.3.20260724.exe`, **26,573,224 bytes**, uploaded 2026-07-24T20:14:41Z, SHA-256 `bee9e3434bd94fd65387d9be28cd467a41f61b1275383b55b0f59a1331270ae4` (GitHub digest and our download agree), 562,782 downloads. 5.5.0 has `tesseract-ocr-w64-setup-5.5.0.20241111.exe`, 21,381,872 bytes, SHA-256 `f3fc4236425b690c8be756f35793f77394ee004be0a6460a440c754d892f68bc`. **5.5.4 (2026-10-28) has no Windows installer asset.** |
| `UB-Mannheim/tesseract` GitHub releases | Only 4 releases. "Latest" is still **v5.4.0.20240606** (`tesseract-ocr-w64-setup-5.4.0.20240606.exe`, 50,175,248 bytes, SHA-256 `c885fff6998e0608ba4bb8ab51436e1c6775c2bafc2559a19b423e18678b60c9`). No pre-release newer than that. |
| Tag `v5.5.3.20260724` in UB-Mannheim/tesseract | An annotated tag by Stefan Weil, 2026-07-24T18:42:03Z, message "Tesseract 5.5.3.20260724", on commit `9f6f6896…`. **There is no GitHub release for this tag** (`releases/tags/v5.5.3.20260724` -> "Not Found"), so no assets there. |
| digi.bib.uni-mannheim.de/tesseract/ | Directory listing; newest installer is `tesseract-ocr-w64-setup-5.4.0.20240606.exe` (2024-06-06), same bytes/SHA as the GitHub 5.4.0 asset. Nothing 5.5.x. |
| winget | `UB-Mannheim.TesseractOCR` = **5.4.0.20240606** (installer URL = the UB-Mannheim 5.4.0 asset). A second id **`tesseract-ocr.tesseract` = 5.5.3** (installer URL = the upstream 5.5.3 asset). winget v1.11.510. |
| Chocolatey | `tesseract` **5.5.3.20260724** [Approved], published 2026-07-25, 458,157 total downloads. (`tesseract-ocr` 5.3.3.20240207 is a different, older package.) Chocolatey v2.7.5. |
| Scoop (main bucket) | `tesseract` **5.5.3.20260724**, `tesseract-languages` 4.1.0. |

All UB Mannheim installers are Authenticode-signed by "Universität Mannheim" (osslsigncode, `ub-mannheim/log.txt`). On the runner,
`Get-AuthenticodeSignature` reported **UnknownError** for the 5.5.3 file: "A required certificate is not within its validity period when verifying against
the current system clock or the timestamp in the signed file." (`gui-default/download.txt`). The installer manifest asks for `requestedExecutionLevel level="highestAvailable"`.

## UB Mannheim installer 5.5.3.20260724, GUI walkthrough

Folders: `gui-default/` (components left as they are) and `gui-all/` (both "Additional script data (download)" and "Additional language data (download)" ticked). Each is a fresh runner.

| | default components | all scripts + languages |
|---|---|---|
| Wizard pages | language (9 choices) -> Welcome -> License -> Choose Users -> Choose Components -> Install Location -> Start Menu -> Installing -> Installation Complete -> Finish | same |
| "Space required" on the components page | 96.9 MB | 728.7 MB |
| Component tree | 167 entries; "Additional script data (download)" has 37, "Additional language data (download)" 122 (`components-tree.txt`) | same |
| Installing page duration (from clicking Install to Next enabled) | **4.0 s** | **20.7 s** (downloads every language from the internet during install) |
| Wizard total incl. screenshot pauses | 28.1 s | 47.0 s |
| `C:\Program Files\Tesseract-OCR` afterwards | **116.4 MB**, 133 files, 2 traineddata (eng, osd) | **800.9 MB**, 292 files, 124 traineddata |
| PATH changed? | **No** (registry Machine and User Path checked) | No |

Timings are single runs on a data-centre network; the "all" time is dominated by downloads. Earlier runs of the same workflow measured 2.0 s / 28.7 s and
24.7 s for the same steps (older `RUN`s in git history), so expect variation.

Screenshots (`gui-default/`): `windows-installer-01-language` … `-12-completing-tesseract-ocr-setup`; `gui-all/` adds the ticked component pages
(`-07-…-script-data-ticked`, `-09-…-language-data-ticked`, `-10-components-all-ticked`) and the download progress (`-14-installing-progress`: "Downloading fry language file").

## PATH: the problem and the fix (`gui-default/windows-path-*`)

1. `windows-path-01-cmd-not-recognized`: new cmd window -> `where tesseract` = "INFO: Could not find files…", `tesseract --version` = "'tesseract' is not recognized…".
2. `windows-path-02-powershell-not-recognized`: same in Windows PowerShell 5.1 (`.txt` has 5.1; `windows-path-02-pwsh7-not-recognized.txt` has PowerShell 7).
3. `windows-error-pytesseract-not-found`: Python + pytesseract 0.3.13 -> `TesseractNotFoundError`.
4. `windows-path-03` … `-04-system-path-*`: `rundll32 sysdm.cpl,EditEnvironmentVariables`, System variables -> Path -> Edit -> New -> `C:\Program Files\Tesseract-OCR` -> OK
   -> **"This environment variable is too large. This dialog allows setting values up to 2047 characters long."** The runner's system Path is 2,508 characters, so
   Windows refused. (A typical desktop's system Path is shorter; this is a property of the runner image.)
5. `windows-path-05-user-path-*`: Cancel, then the same steps on the **user** Path (103 characters) -> accepted; `-06-environment-variables-after`.
6. `windows-path-07-cmd-working`: new cmd window -> `where tesseract` = `C:\Program Files\Tesseract-OCR\tesseract.exe`, `--version` = 5.5.3.20260724 / leptonica-1.87.0, `--list-langs` = eng, osd.
7. `-08-cmd-ocr-receipt` (OCR of `samples/receipt.png`), `-09-powershell-working`, `-10-pytesseract-working`.
8. `windows-error-01-tessdata-and-language`: `-l xyz`, `--tessdata-dir C:\wrong\tessdata`, `TESSDATA_PREFIX=C:\Users`, missing input file (each run via `cmd /d /c` so the `set` stays local).

## Package managers (`winget/`, `winget-tesseract-ocr/`, `choco/`, `scoop/`), one fresh runner each

| | Version installed | install command time | `C:\…` size | Languages | PATH after install (new shell) |
|---|---|---|---|---|---|
| `winget install --id UB-Mannheim.TesseractOCR -e --silent` | 5.4.0.20240606 | 8.9 s | 249.4 MB (`C:\Program Files\Tesseract-OCR`) | eng, osd | **not set** -> "not recognized" |
| `winget install --id tesseract-ocr.tesseract -e --silent` | 5.5.3.20260724 | 10.0 s | 116.4 MB | eng, osd | **not set** -> "not recognized" |
| `choco install tesseract -y` | 5.5.3.20260724 | 17.2 s | 116.4 MB | eng, osd | **set** (choco: "PATH environment variable does not have C:\Program Files\Tesseract-OCR in it. Adding...") |
| `scoop install tesseract` | 5.5.3.20260724 | 7.8 s (+ 7zip dependency) | 101.3 MB (`~\scoop\apps\tesseract\5.5.3.20260724`) | **none** -> OCR fails until `scoop install tesseract-languages` (10.4 s, 700.4 MB, 162 languages) | **set** (`~\scoop\shims` on user Path; also sets user `TESSDATA_PREFIX`) |

Values from each folder's `result.json` / `log.txt`; "new shell" = a cmd process with PATH re-read from the registry, plus a screenshot of a window started
through Explorer (`windows-<pm>-fresh-console.png`). Scoop itself had to be installed first (`irm get.scoop.sh` with `-RunAsAdmin`, 24.4 s) because the runner session is admin.
Admin rights could not be tested the other way round: every runner session is an administrator.

## WSL2 (`wsl/`)

WSL works on this runner: WSL 3.0.3.0, kernel 6.18.54.1-microsoft-standard-WSL2. `wsl --install -d Ubuntu-24.04 --no-launch` took 30.1 s; inside it
`apt-get update` 8.6 s, `apt-get install -y tesseract-ocr` 5.9 s (9,144 kB download, 23.7 MB on disk — the WSL Ubuntu image already has most libraries),
giving Tesseract **5.3.4** / leptonica 1.82.0 with eng + osd. The receipt OCR through `/mnt/d/...` worked. Windows' own `where tesseract` still finds nothing:
the WSL install is not on the Windows PATH. Screenshot: `wsl/windows-wsl-ubuntu-tesseract.png`.

## Not done / limits

- Not tested on Windows 10/11 desktop editions, without admin rights, or with a browser download (SmartScreen / Mark-of-the-Web).
- Chocolatey and Scoop download sizes were not captured (their output doesn't print them).
- The 32-bit installer no longer exists (wiki: "32 bit installer is no longer provided" since 2023-04-01).
