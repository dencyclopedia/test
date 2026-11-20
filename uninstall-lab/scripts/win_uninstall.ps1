# Feasibility test: install an app with winget, run it, uninstall it the normal way
# (Settings / the app's own uninstaller), and measure what is left behind.
# Screenshots via install/windows/scripts/wincap.py, screen recording via ffmpeg gdigrab.
param([string]$id, [string]$name, [string]$out)
$ErrorActionPreference = 'Continue'
New-Item -ItemType Directory -Force $out | Out-Null
$env:CAP_OUT = $out
$LOG = "$out\log.txt"
function log($m) { $l = "[$((Get-Date).ToUniversalTime().ToString('HH:mm:ss'))] $m"; Write-Host $l; Add-Content $LOG $l }
function shot($n) { python -c "import sys; sys.path.insert(0, r'install\windows\scripts'); from wincap import shot; shot('$n')" }
$regRoots = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall','HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall','HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall'
function snapTo($file) { snapList | Sort-Object -Unique | Set-Content -Encoding utf8 $file }
function snapList {
  foreach ($d in @($env:ProgramFiles, ${env:ProgramFiles(x86)}, $env:ProgramData, $env:APPDATA, $env:LOCALAPPDATA, "$env:LOCALAPPDATA\Programs", "$env:USERPROFILE\AppData\LocalLow",
                   "$env:APPDATA\Microsoft\Windows\Start Menu\Programs", "$env:ProgramData\Microsoft\Windows\Start Menu\Programs", "$env:PUBLIC\Desktop", "$env:USERPROFILE\Desktop")) {
    if (Test-Path $d) { Get-ChildItem -Force $d -ErrorAction SilentlyContinue | ForEach-Object { "FILE`t$($_.FullName)" } } }
  foreach ($k in 'HKCU:\SOFTWARE','HKLM:\SOFTWARE','HKLM:\SOFTWARE\WOW6432Node') { Get-ChildItem $k -ErrorAction SilentlyContinue | ForEach-Object { "REG`t$($_.Name)" } }
  foreach ($r in $regRoots) { Get-ChildItem $r -ErrorAction SilentlyContinue | ForEach-Object { "UNINSTALLKEY`t$($_.Name)" } }
  Get-Service | ForEach-Object { "SERVICE`t$($_.Name)" }
  Get-ScheduledTask -ErrorAction SilentlyContinue | ForEach-Object { "TASK`t$($_.TaskPath)$($_.TaskName)" }
  Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run','HKLM:\Software\Microsoft\Windows\CurrentVersion\Run' -ErrorAction SilentlyContinue | ForEach-Object { $_.PSObject.Properties | Where-Object Name -notlike 'PS*' | ForEach-Object { "RUN`t$($_.Name)" } }
}
function sizeOf($line) {
  $t, $p = $line -split "`t", 2
  if ($t -eq 'FILE' -and (Test-Path $p)) { $kb = [math]::Round(((Get-ChildItem -Recurse -Force $p -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum)/1KB); "$kb`t$line" } else { "`t$line" }
}
function diffNew($a, $b) { Compare-Object (Get-Content $a) (Get-Content $b) | Where-Object SideIndicator -eq '=>' | ForEach-Object InputObject }
function diffBoth($a, $b) { Compare-Object (Get-Content $a) (Get-Content $b) -IncludeEqual -ExcludeDifferent | ForEach-Object InputObject }

$os = Get-CimInstance Win32_OperatingSystem
[ordered]@{ os = $os.Caption; build = $os.BuildNumber; runner_image = "$env:ImageOS $env:ImageVersion"; winget_id = $id; date_utc = (Get-Date -AsUTC -Format s) + 'Z'; run = $env:RUN_URL; git_sha = $env:GITHUB_SHA } | ConvertTo-Json | Set-Content "$out\meta.json"
log "start $id"
snapTo "$out\snap-0-before.txt"

# screen recording (ffmpeg gdigrab) for the whole session
$ff = (Get-Command ffmpeg -ErrorAction SilentlyContinue).Source
if (-not $ff) { choco install ffmpeg -y --no-progress *> "$out\ffmpeg-install.txt"; $ff = (Get-Command ffmpeg -ErrorAction SilentlyContinue).Source; if (-not $ff) { $ff = 'C:\ProgramData\chocolatey\bin\ffmpeg.exe' } }
log "ffmpeg: $ff"
$rec = Start-Process -FilePath $ff -ArgumentList '-y','-loglevel','error','-f','gdigrab','-framerate','8','-i','desktop','-t','170','-vf','scale=960:-2','-c:v','libx264','-preset','veryfast','-crf','30','-pix_fmt','yuv420p',"$out\recording.mp4" -PassThru -WindowStyle Hidden -RedirectStandardError "$out\recording.log"

$sw = [Diagnostics.Stopwatch]::StartNew()
winget install --id $id -e --silent --accept-package-agreements --accept-source-agreements --disable-interactivity *> "$out\winget-install.txt"
log "winget install exit=$LASTEXITCODE seconds=$([math]::Round($sw.Elapsed.TotalSeconds))"
snapTo "$out\snap-1-installed.txt"
$entry = foreach ($r in $regRoots) { Get-ItemProperty "$r\*" -ErrorAction SilentlyContinue | Where-Object DisplayName -like "*$name*" }
$entry = $entry | Select-Object -First 1
$entry | Select-Object DisplayName, DisplayVersion, Publisher, InstallLocation, UninstallString, QuietUninstallString, EstimatedSize, DisplayIcon | ConvertTo-Json | Set-Content "$out\uninstall-registry-entry.json"
log "registry entry: $($entry.DisplayName) $($entry.DisplayVersion) | uninstall: $($entry.UninstallString)"

# launch it once like a user would
$exe = $null
if ($entry.DisplayIcon) { $exe = ($entry.DisplayIcon -split ',')[0].Trim('"') }
if (-not $exe -or -not (Test-Path $exe) -or $exe -notlike '*.exe') { $exe = (Get-ChildItem -Recurse -Filter '*.exe' $entry.InstallLocation -ErrorAction SilentlyContinue | Where-Object Name -notmatch 'unins|update|crash' | Select-Object -First 1).FullName }
log "launching: $exe"
if ($exe) { Start-Process $exe; Start-Sleep 25; shot '01-app-first-launch' }
Get-Process | Where-Object { $_.Path -and $entry.InstallLocation -and $_.Path -like "$($entry.InstallLocation.TrimEnd('\'))*" } | Stop-Process -Force -ErrorAction SilentlyContinue
Get-Process -Name ([IO.Path]::GetFileNameWithoutExtension("$exe")) -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep 3
snapTo "$out\snap-2-after-first-run.txt"
diffNew "$out\snap-0-before.txt" "$out\snap-2-after-first-run.txt" | ForEach-Object { sizeOf $_ } | Set-Content "$out\created-by-install-and-first-run.tsv"
log "items created by install + first run: $((Get-Content "$out\created-by-install-and-first-run.tsv").Count)"

# where a normal user goes: Settings > Apps > Installed apps, and Control Panel
Start-Process 'ms-settings:appsfeatures'; Start-Sleep 8; shot '02-settings-installed-apps'
Get-Process SystemSettings -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Process 'appwiz.cpl'; Start-Sleep 6; shot '03-control-panel-programs'
Get-Process | Where-Object MainWindowTitle -like '*Programs and Features*' | Stop-Process -Force -ErrorAction SilentlyContinue

# the app's own uninstaller: first screen (interactive), then the real run (silent)
if ($entry.UninstallString) {
  $u = $entry.UninstallString
  if ($u -match '^"([^"]+)"\s*(.*)$') { $uexe = $matches[1]; $uargs = $matches[2] } elseif ($u -match '^(\S+\.exe)\s*(.*)$') { $uexe = $matches[1]; $uargs = $matches[2] } else { $uexe = $u; $uargs = '' }
  if ($uexe -match 'msiexec') { $uargs = $uargs -replace '/I', '/X' }
  $p = Start-Process $uexe -ArgumentList $uargs -PassThru -ErrorAction SilentlyContinue; Start-Sleep 8; shot '04-official-uninstaller-first-screen'
  if ($p) { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue }; Get-Process | Where-Object { $_.Path -like '*unins*' } | Stop-Process -Force -ErrorAction SilentlyContinue
}
$sw.Restart()
winget uninstall --id $id -e --silent --accept-source-agreements --disable-interactivity *> "$out\winget-uninstall.txt"
log "standard uninstall (winget -> app's own uninstaller, silent) exit=$LASTEXITCODE seconds=$([math]::Round($sw.Elapsed.TotalSeconds))"
Start-Sleep 5
snapTo "$out\snap-3-after-uninstall.txt"
$created = "$out\created-lines.txt"; diffNew "$out\snap-0-before.txt" "$out\snap-2-after-first-run.txt" | Set-Content $created
diffBoth $created "$out\snap-3-after-uninstall.txt" | ForEach-Object { sizeOf $_ } | Set-Content "$out\leftovers-after-uninstall.tsv"
$left = Get-Content "$out\leftovers-after-uninstall.tsv"
log "LEFTOVERS after standard uninstall: $($left.Count) items; files KB total: $(($left | ForEach-Object { ($_ -split "`t")[0] } | Where-Object { $_ } | Measure-Object -Sum).Sum)"
$firstDir = ($left | Where-Object { $_ -match "`tFILE`t" } | Select-Object -First 1) -split "`t" | Select-Object -Last 1
if ($firstDir -and (Test-Path $firstDir)) { Start-Process explorer.exe "/select,`"$firstDir`""; Start-Sleep 5; shot '05-explorer-leftover-folder' }
shot '06-final-desktop'
Start-Sleep 2
if ($rec -and -not $rec.HasExited) { Wait-Process -Id $rec.Id -Timeout 200 -ErrorAction SilentlyContinue }
log "recording: $((Get-Item "$out\recording.mp4" -ErrorAction SilentlyContinue).Length) bytes"
log 'done'
