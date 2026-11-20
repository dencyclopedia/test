# Uninstall lab (feasibility)

Tests whether GitHub Actions runners can produce first-hand material for "how to uninstall X" guides:
real screenshots, a screen recording, and measured lists of the files, folders, registry keys,
services and tasks an app leaves behind after a normal uninstall.

- `scripts/mac_uninstall.sh`: macOS (`macos-latest`). Installs a Homebrew cask, launches it once, moves it to the Trash like a user, diffs the Library folders, then runs `brew uninstall --zap`.
- `scripts/win_uninstall.ps1`: Windows (`windows-latest` = Windows Server 2025, not Windows 11). Installs with winget, launches once, opens Settings > Installed apps and Control Panel, runs the app's own uninstaller, diffs files/registry/services/tasks.
- Results: `feasibility-2026-11-20/<os>-<app>/`. `leftovers-*.tsv` = size in KB, then the item.

Same honesty rules as the rest of this repo (see LAB.md): numbers come only from these scripts' raw output.
