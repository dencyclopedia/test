# WSL2 on a GitHub Actions Windows runner: install Ubuntu 24.04, then apt install tesseract inside it.
param([string]$out = "out")
New-Item -ItemType Directory -Force $out | Out-Null
$log = Join-Path $out "log.txt"
function L($x) { $s = (($x | Out-String) -replace "`0", '').TrimEnd(); Write-Host $s; Add-Content -Path $log -Value $s -Encoding utf8 }
function Run($label, [scriptblock]$sb) {
  L "`n### $label"; L "PS> $($sb.ToString().Trim())"
  $sw = [Diagnostics.Stopwatch]::StartNew(); $o = (& $sb 2>&1 | Out-String) -replace "`0", ''; $sw.Stop()
  L $o.TrimEnd(); L "[exit $LASTEXITCODE, $([math]::Round($sw.Elapsed.TotalSeconds,1)) s]"
  return [math]::Round($sw.Elapsed.TotalSeconds,1)
}
$res = [ordered]@{}
L "captured $(Get-Date -AsUTC -Format s)Z on $((Get-CimInstance Win32_OperatingSystem).Caption) build $([Environment]::OSVersion.Version.Build)"
Run "wsl --version" { wsl.exe --version } | Out-Null
Run "wsl --status" { wsl.exe --status } | Out-Null
$res.distro_install_seconds = Run "wsl --install -d Ubuntu-24.04 --no-launch" { wsl.exe --install -d Ubuntu-24.04 --no-launch }
Run "wsl --list --verbose" { wsl.exe --list --verbose } | Out-Null
Run "uname -a (inside WSL)" { wsl.exe -d Ubuntu-24.04 -u root -- uname -a } | Out-Null
Run "os-release (inside WSL)" { wsl.exe -d Ubuntu-24.04 -u root -- head -4 /etc/os-release } | Out-Null
$res.apt_update_seconds = Run "apt-get update" { wsl.exe -d Ubuntu-24.04 -u root -- apt-get update }
$res.apt_install_seconds = Run "apt-get install -y tesseract-ocr" { wsl.exe -d Ubuntu-24.04 -u root -- env DEBIAN_FRONTEND=noninteractive apt-get install -y tesseract-ocr }
Run "tesseract --version (inside WSL)" { wsl.exe -d Ubuntu-24.04 -u root -- tesseract --version } | Out-Null
Run "tesseract --list-langs (inside WSL)" { wsl.exe -d Ubuntu-24.04 -u root -- tesseract --list-langs } | Out-Null
$res.ocr_seconds = Run "OCR the sample through /mnt/d (inside WSL)" { wsl.exe -d Ubuntu-24.04 -u root -- tesseract "$(wsl.exe -d Ubuntu-24.04 -u root -- wslpath -a ($PWD.Path -replace '\\','/'))/samples/receipt.png" - }
Run "Windows side: where tesseract (WSL install is not visible to Windows)" { cmd /c "where tesseract" } | Out-Null
$res | ConvertTo-Json | Set-Content (Join-Path $out "result.json"); L ($res | ConvertTo-Json)
$global:LASTEXITCODE = 0
