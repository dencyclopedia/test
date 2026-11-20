# Uninstall capture on a GitHub Actions Windows runner (Windows Server 2025, NOT Windows 11).
# Installs with winget, launches the app once, shows it in Settings and Control Panel, runs the
# app's own uninstaller (silently, via winget) and waits for it to really finish, then measures
# leftover files, registry keys, services, scheduled tasks and Run entries. Screenshots + recording.
param([string]$id, [string]$name, [string]$out)
$ErrorActionPreference = 'Continue'
New-Item -ItemType Directory -Force $out | Out-Null
$env:CAP_OUT = $out
$LOG = "$out\log.txt"
function log($m) { $l = "[$((Get-Date).ToUniversalTime().ToString('HH:mm:ss'))] $m"; Write-Host $l; Add-Content $LOG $l }
function ui { python uninstall-lab\scripts\uwin.py @args }
$regRoots = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall','HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall','HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall'
$dirs = @($env:ProgramFiles, ${env:ProgramFiles(x86)}, $env:ProgramData, $env:APPDATA, $env:LOCALAPPDATA, "$env:LOCALAPPDATA\Programs", "$env:USERPROFILE\AppData\LocalLow",
          "$env:APPDATA\Microsoft\Windows\Start Menu\Programs", "$env:ProgramData\Microsoft\Windows\Start Menu\Programs", "$env:PUBLIC\Desktop", "$env:USERPROFILE\Desktop", $env:USERPROFILE)
function snapList {
  foreach ($d in $dirs) { if (Test-Path $d) { Get-ChildItem -Force $d -ErrorAction SilentlyContinue | ForEach-Object { "FILE`t$($_.FullName)" } } }
  foreach ($k in 'HKCU:\SOFTWARE','HKLM:\SOFTWARE','HKLM:\SOFTWARE\WOW6432Node','HKCU:\SOFTWARE\Classes','HKLM:\SOFTWARE\Classes') { Get-ChildItem $k -ErrorAction SilentlyContinue | Where-Object { $_.PSChildName -notlike '.*' -or $k -notlike '*Classes' } | ForEach-Object { "REG`t$($_.Name)" } }
  foreach ($r in $regRoots) { Get-ChildItem $r -ErrorAction SilentlyContinue | ForEach-Object { "UNINSTALLKEY`t$($_.Name)" } }
  Get-Service | ForEach-Object { "SERVICE`t$($_.Name)" }
  Get-ScheduledTask -ErrorAction SilentlyContinue | ForEach-Object { "TASK`t$($_.TaskPath)$($_.TaskName)" }
  foreach ($rk in 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run','HKLM:\Software\Microsoft\Windows\CurrentVersion\Run','HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Run') {
    $p = Get-ItemProperty $rk -ErrorAction SilentlyContinue; if ($p) { $p.PSObject.Properties | Where-Object Name -notlike 'PS*' | ForEach-Object { "RUN`t$rk\$($_.Name)" } } }
  Get-AppxPackage -ErrorAction SilentlyContinue | ForEach-Object { "APPX`t$($_.PackageFullName)" }
}
function snapTo($file) { snapList | Sort-Object -Unique | Set-Content -Encoding utf8 $file }
function sizeOf($line) {
  $t, $p = $line -split "`t", 2
  if ($t -eq 'FILE' -and (Test-Path -LiteralPath $p)) { $kb = [math]::Round(((Get-ChildItem -LiteralPath $p -Recurse -Force -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum)/1KB); if (-not (Test-Path -LiteralPath $p -PathType Container)) { $kb = [math]::Round((Get-Item -LiteralPath $p -Force).Length/1KB) }; "$kb`t$line" } else { "`t$line" }
}
function newLines($a, $b) { $s = [Collections.Generic.HashSet[string]]::new([string[]](Get-Content $a)); Get-Content $b | Where-Object { -not $s.Contains($_) } }
function stillThere($lines, $snapFile) { $s = [Collections.Generic.HashSet[string]]::new([string[]](Get-Content $snapFile)); $lines | Where-Object { $s.Contains($_) } }
function uninstallerBusy { Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.Name -match '^(Au_|Un_A|Un_B|unins\d*|uninst|uninstall|Uninstall.*|Update|.*[Uu]ninstall.*)$' -or ($_.Name -eq 'msiexec' -and $_.Id -notin $script:msiBase) } }

$os = Get-CimInstance Win32_OperatingSystem
[ordered]@{ os = $os.Caption; build = $os.BuildNumber; runner_image = "$env:ImageOS $env:ImageVersion"; winget_id = $id; date_utc = (Get-Date -AsUTC -Format s) + 'Z'; run = $env:RUN_URL; git_sha = $env:GITHUB_SHA } | ConvertTo-Json | Set-Content "$out\meta.json"
log "start $id"
ui clean
snapTo "$out\snap-0-before.txt"
$script:msiBase = @(Get-Process msiexec -ErrorAction SilentlyContinue | ForEach-Object Id)

$ff = (Get-Command ffmpeg -ErrorAction SilentlyContinue).Source
if (-not $ff) { choco install ffmpeg -y --no-progress *> "$out\ffmpeg-install.txt"; $ff = 'C:\ProgramData\chocolatey\bin\ffmpeg.exe' }
$rec = Start-Process -FilePath $ff -ArgumentList '-y','-loglevel','error','-f','gdigrab','-framerate','8','-i','desktop','-t','300','-vf','scale=960:-2','-c:v','libx264','-preset','veryfast','-crf','30','-pix_fmt','yuv420p','-movflags','frag_keyframe+empty_moov',"$out\recording.mp4" -PassThru -WindowStyle Hidden -RedirectStandardError "$out\recording.log"

$sw = [Diagnostics.Stopwatch]::StartNew()
$j = Start-Job { param($id) winget install --id $id -e --silent --accept-package-agreements --accept-source-agreements --disable-interactivity 2>&1; "EXIT=$LASTEXITCODE" } -ArgumentList $id
if (-not (Wait-Job $j -Timeout 900)) { Stop-Job $j; log 'winget install TIMEOUT (900 s)' }
Receive-Job $j | Out-File "$out\winget-install.txt"
log "winget install: $((Select-String -Path "$out\winget-install.txt" -Pattern 'EXIT=').Line) seconds=$([math]::Round($sw.Elapsed.TotalSeconds))"
Start-Sleep 5
snapTo "$out\snap-1-installed.txt"
$entry = foreach ($r in $regRoots) { Get-ItemProperty "$r\*" -ErrorAction SilentlyContinue | Where-Object { $_.DisplayName -like "*$name*" -and $_.SystemComponent -ne 1 } }
$entry = $entry | Select-Object -First 1
$entry | Select-Object DisplayName, DisplayVersion, Publisher, InstallLocation, UninstallString, QuietUninstallString, EstimatedSize, DisplayIcon | ConvertTo-Json | Set-Content "$out\uninstall-registry-entry.json"
log "registry entry: $($entry.DisplayName) $($entry.DisplayVersion) | publisher: $($entry.Publisher) | uninstall: $($entry.UninstallString)"

# find the program the way a user would: the Start Menu / desktop shortcut it created
$created1 = newLines "$out\snap-0-before.txt" "$out\snap-1-installed.txt"
$sh = New-Object -ComObject WScript.Shell
$lnks = foreach ($l in $created1) { $t, $p = $l -split "`t", 2; if ($t -eq 'FILE') { if ($p -like '*.lnk') { $p } elseif (Test-Path $p -PathType Container) { Get-ChildItem -Recurse -Filter *.lnk $p -ErrorAction SilentlyContinue | ForEach-Object FullName } } }
$exe = $lnks | ForEach-Object { $sh.CreateShortcut($_).TargetPath } | Where-Object { $_ -like '*.exe' -and $_ -notmatch 'unins|uninstall|update|readme' -and (Test-Path $_) } | Select-Object -First 1
if (-not $exe -and $entry.DisplayIcon) { $exe = ($entry.DisplayIcon -split ',')[0].Trim('"') }
log "shortcuts: $($lnks -join ' | ') ; launching: $exe"
$stem = if ($exe) { [IO.Path]::GetFileNameWithoutExtension($exe) } else { '' }
if ($exe -and (Test-Path $exe)) { Start-Process $exe; Start-Sleep 30; ui app 01-app-first-launch $stem }
else { log 'no launchable exe found'; ui desktop 01-app-first-launch }
if ($stem) { Get-Process -Name $stem -ErrorAction SilentlyContinue | Stop-Process -Force }
if ($entry.InstallLocation) { Get-Process | Where-Object { $_.Path -and $_.Path -like "$($entry.InstallLocation.TrimEnd('\'))*" } | Stop-Process -Force -ErrorAction SilentlyContinue }
Start-Sleep 3
snapTo "$out\snap-2-after-first-run.txt"
$created = newLines "$out\snap-0-before.txt" "$out\snap-2-after-first-run.txt"

ui settings 02-settings-installed-apps $name
ui cpl 03-control-panel-programs $name

# the app's own uninstaller: show its first screen, cancel, then run it for real (silent, via winget)
if ($entry.UninstallString) {
  $u = $entry.UninstallString
  if ($u -match '^"([^"]+)"\s*(.*)$') { $uexe = $matches[1]; $uargs = $matches[2] } elseif ($u -match '^(\S+\.exe)\s*(.*)$') { $uexe = $matches[1]; $uargs = $matches[2] } else { $uexe = $u; $uargs = '' }
  if ($uexe -match 'msiexec') { $uargs = $uargs -replace '/I', '/X' }
  if ($uargs) { $p = Start-Process $uexe -ArgumentList $uargs -PassThru -ErrorAction SilentlyContinue } else { $p = Start-Process $uexe -PassThru -ErrorAction SilentlyContinue }
  Start-Sleep 8; ui desktop 04-official-uninstaller-first-screen
  uninstallerBusy | Stop-Process -Force -ErrorAction SilentlyContinue; if ($p) { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue }
  Start-Sleep 3
}
$sw.Restart()
$j = Start-Job { param($id) winget uninstall --id $id -e --silent --accept-source-agreements --disable-interactivity 2>&1; "EXIT=$LASTEXITCODE" } -ArgumentList $id
if (-not (Wait-Job $j -Timeout 600)) { Stop-Job $j; log 'winget uninstall TIMEOUT' }
Receive-Job $j | Out-File "$out\winget-uninstall.txt"
# many uninstallers (NSIS, Squirrel) hand off to a copy of themselves and return early: wait for them
$w = 0; while ((uninstallerBusy) -and $w -lt 180) { Start-Sleep 3; $w += 3 }
Start-Sleep 5
log "standard uninstall: $((Select-String -Path "$out\winget-uninstall.txt" -Pattern 'EXIT=').Line) seconds=$([math]::Round($sw.Elapsed.TotalSeconds)) (waited $w s for background uninstaller)"
snapTo "$out\snap-3-after-uninstall.txt"
ui settings 05-settings-after-uninstall $name

# attribute: lines containing the app's name, publisher or package-id words; everything else is "other"
$tok = @($name) + ($id -split '[.\-]') + (("$($entry.Publisher) $($entry.DisplayName)") -split '[^A-Za-z0-9]+') | Where-Object { $_.Length -ge 4 -and $_ -notmatch '^(Microsoft|Corporation|Inc|LLC|Ltd|Software|Windows|Desktop|Media|Player|Technologies|Communications|x64|64-bit|Version)$' } | Sort-Object -Unique
log "attribution tokens: $($tok -join ' ')"
$isApp = { param($l) foreach ($t in $tok) { if ($l -like "*$t*") { return $true } }; return $false }
$byApp = $created | Where-Object { & $isApp $_ }
$other = $created | Where-Object { -not (& $isApp $_) }
$byApp | ForEach-Object { sizeOf $_ } | Set-Content "$out\created-by-app.tsv"
$other | ForEach-Object { sizeOf $_ } | Set-Content "$out\created-other-during-test.tsv"
$left = stillThere $byApp "$out\snap-3-after-uninstall.txt"
$left | ForEach-Object { sizeOf $_ } | Set-Content "$out\leftovers-after-uninstall.tsv"
$leftOther = stillThere $other "$out\snap-3-after-uninstall.txt"
$leftOther | ForEach-Object { sizeOf $_ } | Set-Content "$out\other-changes-still-present.tsv"
$kb = (Get-Content "$out\leftovers-after-uninstall.tsv" | ForEach-Object { ($_ -split "`t")[0] } | Where-Object { $_ -match '^\d+$' } | Measure-Object -Sum).Sum
log "app created $(@($byApp).Count) items (+$(@($other).Count) other changes during test). LEFTOVERS after standard uninstall: $(@($left).Count) items, $kb KB"

$firstDir = $left | Where-Object { $_ -like 'FILE*' } | Select-Object -First 1
if ($firstDir) { ui explorer 06-explorer-leftover ($firstDir -split "`t", 2)[1] }
ui desktop 07-final-desktop

[ordered]@{ os = 'Windows Server 2025'; winget_id = $id; display_name = $entry.DisplayName; version = $entry.DisplayVersion; publisher = $entry.Publisher
  uninstall_string = $entry.UninstallString; created_items = @($byApp).Count; leftover_items = @($left).Count; leftover_kb = $kb
  leftovers = @($left | ForEach-Object { $_ -replace "`t", ' ' }) } | ConvertTo-Json | Set-Content "$out\summary.json"
if ($rec -and -not $rec.HasExited) { Stop-Process -Id $rec.Id -ErrorAction SilentlyContinue; Start-Sleep 2 }
log "recording: $((Get-Item "$out\recording.mp4" -ErrorAction SilentlyContinue).Length) bytes"
log 'done'
