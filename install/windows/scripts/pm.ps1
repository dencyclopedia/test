# Package-manager install capture (winget | choco | scoop) on a GitHub Actions Windows runner.
param([Parameter(Mandatory)][string]$pm, [string]$out = "out")
New-Item -ItemType Directory -Force $out | Out-Null
$log = Join-Path $out "log.txt"
function L($x) { $s = ($x | Out-String).TrimEnd(); Write-Host $s; Add-Content -Path $log -Value $s -Encoding utf8 }
function Run($label, [scriptblock]$sb) {
  L "`n### $label"; L "PS> $($sb.ToString().Trim())"
  $sw = [Diagnostics.Stopwatch]::StartNew()
  $o = & $sb 2>&1 | Out-String
  $sw.Stop(); L $o.TrimEnd(); L "[exit $LASTEXITCODE, $([math]::Round($sw.Elapsed.TotalSeconds,1)) s]"
  return [math]::Round($sw.Elapsed.TotalSeconds,1)
}
function FreshCheck($label) {
  # like a newly opened cmd window: PATH (and TESSDATA_PREFIX) re-read from the registry
  L "`n### $label (new cmd process, PATH re-read from registry Machine+User)"
  $p = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User')
  $td = [Environment]::GetEnvironmentVariable('TESSDATA_PREFIX','User'); if (-not $td) { $td = [Environment]::GetEnvironmentVariable('TESSDATA_PREFIX','Machine') }
  $env:FRESHPATH = $p; $env:FRESHTD = $td
  $o = cmd /d /c 'set "PATH=%FRESHPATH%"& (if defined FRESHTD set "TESSDATA_PREFIX=%FRESHTD%")& echo C:\^> where tesseract& where tesseract& echo C:\^> tesseract --version& tesseract --version' 2>&1 | Out-String
  L $o.TrimEnd()
}
$res = [ordered]@{ pm = $pm }
L "captured $(Get-Date -AsUTC -Format s)Z on $((Get-CimInstance Win32_OperatingSystem).Caption) build $([Environment]::OSVersion.Version.Build)"
L "CPU: $((Get-CimInstance Win32_Processor).Name) cores: $([Environment]::ProcessorCount)"
FreshCheck "before install"
$regBefore = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User')
$fs0 = (Get-PSDrive C).Free

switch ($pm) {
 {$_ -in 'winget','winget-tesseract-ocr'} {
  $id = if ($pm -eq 'winget') { 'UB-Mannheim.TesseractOCR' } else { 'tesseract-ocr.tesseract' }
  L "winget package id: $id"
  Run "winget version" { winget --version } | Out-Null
  Run "winget search" { winget search tesseract --accept-source-agreements --disable-interactivity } | Out-Null
  Run "winget show" { winget show --id $id -e --accept-source-agreements --disable-interactivity } | Out-Null
  Run "winget show versions" { winget show --id $id -e --versions --disable-interactivity } | Out-Null
  $res.install_seconds = Run "winget install" { winget install --id $id -e --silent --accept-package-agreements --accept-source-agreements --disable-interactivity }
  $res.install_exit = $LASTEXITCODE
  Run "winget list" { winget list --id $id -e --disable-interactivity } | Out-Null
  $dir = 'C:\Program Files\Tesseract-OCR'
 }
 'choco' {
  Run "choco version" { choco --version } | Out-Null
  Run "choco search" { choco search tesseract --limit-output } | Out-Null
  Run "choco info" { choco info tesseract } | Out-Null
  $res.install_seconds = Run "choco install" { choco install tesseract -y --no-progress }
  $res.install_exit = $LASTEXITCODE
  Run "choco list" { choco list tesseract } | Out-Null
  $dir = 'C:\Program Files\Tesseract-OCR'
  if (-not (Test-Path $dir)) { $dir = (Get-ChildItem 'C:\Program Files*','C:\ProgramData\chocolatey\lib' -Directory -Filter '*esseract*' -ErrorAction SilentlyContinue | Select -First 1).FullName }
  Run "choco shims" { Get-ChildItem C:\ProgramData\chocolatey\bin -Filter '*tess*' | Select Name,Length } | Out-Null
 }
 'scoop' {
  $res.scoop_setup_seconds = Run "install scoop (as admin needs -RunAsAdmin)" { iex "& {$(irm get.scoop.sh)} -RunAsAdmin" }
  $env:Path = "$env:USERPROFILE\scoop\shims;$env:Path"
  Run "scoop version" { scoop --version } | Out-Null
  Run "scoop search" { scoop search tesseract } | Out-Null
  Run "scoop info" { scoop info tesseract } | Out-Null
  $res.install_seconds = Run "scoop install" { scoop install tesseract }
  $res.install_exit = $LASTEXITCODE
  Run "scoop info after" { scoop info tesseract } | Out-Null
  Run "list-langs right after install" { tesseract --list-langs } | Out-Null
  Run "OCR right after install (no language data yet)" { tesseract samples\receipt.png - } | Out-Null
  Run "scoop info tesseract-languages" { scoop info tesseract-languages } | Out-Null
  $res.languages_install_seconds = Run "scoop install tesseract-languages" { scoop install tesseract-languages }
  $res.languages_bytes = (Get-ChildItem "$env:USERPROFILE\scoop\apps\tesseract-languages" -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum
  Run "list-langs count after tesseract-languages" { (tesseract --list-langs | Select-Object -Skip 1 | Measure-Object).Count } | Out-Null
  $dir = "$env:USERPROFILE\scoop\apps\tesseract\current"
 }
}
$res.install_dir = $dir
if ($dir -and (Test-Path $dir)) {
  $item = Get-Item $dir; if ($item.LinkType) { $dir = $item.Target | Select -First 1; L "($($res.install_dir) is a $($item.LinkType) -> $dir)" }
  $res.installed_bytes = (Get-ChildItem $dir -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum
  $res.traineddata = @(Get-ChildItem $dir -Recurse -Filter *.traineddata | ForEach-Object Name)
  $exe = Get-ChildItem $dir -Recurse -Filter tesseract.exe | Select -First 1
  Run "--version (full path)" { & $exe.FullName --version } | Out-Null
  Run "--list-langs (full path)" { & $exe.FullName --list-langs } | Out-Null
  Run "OCR receipt (full path)" { & $exe.FullName samples\receipt.png - } | Out-Null
}
$res.free_space_delta_bytes = $fs0 - (Get-PSDrive C).Free
$regAfter = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User')
$res.path_entries_added = @(($regAfter -split ';') | Where-Object { $_ -and (($regBefore -split ';') -notcontains $_) })
$res.registry_path_has_tesseract_dir = [bool]($regAfter -match 'tesseract')
L "PATH entries added by the install: $($res.path_entries_added -join ' | ')"
FreshCheck "after install"
if ($pm -eq 'winget') {
  # WSL2 on the runner (nested virtualisation is not available on GitHub-hosted runners; record what happens)
  Run "wsl --status" { wsl.exe --status } | Out-Null
  Run "wsl --list --verbose" { wsl.exe --list --verbose } | Out-Null
}
$res | ConvertTo-Json -Depth 4 | Set-Content (Join-Path $out "result.json")
L ($res | ConvertTo-Json -Depth 4)
$global:LASTEXITCODE = 0
