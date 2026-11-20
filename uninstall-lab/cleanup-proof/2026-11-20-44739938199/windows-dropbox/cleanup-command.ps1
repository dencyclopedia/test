# Removes the leftovers of Dropbox marked "safe" on this page. Nothing else.
# Run in Terminal (Admin) / PowerShell as administrator.

# 1. Stop and delete services
Get-Service -Name 'DropboxUpdaterInternalService*' -ErrorAction SilentlyContinue | ForEach-Object {
  Stop-Service -Name $_.Name -Force -ErrorAction SilentlyContinue
  sc.exe delete $_.Name
}
Get-Service -Name 'DropboxUpdaterService*' -ErrorAction SilentlyContinue | ForEach-Object {
  Stop-Service -Name $_.Name -Force -ErrorAction SilentlyContinue
  sc.exe delete $_.Name
}

# 2. Delete scheduled tasks
Get-ScheduledTask -TaskPath '\DropboxSystem\DropboxUpdater\' -ErrorAction SilentlyContinue | Where-Object TaskName -like 'DropboxUpdaterTaskSystem*' | Unregister-ScheduledTask -Confirm:$false

# 3. Back up, then delete registry keys (backups go to your Desktop)
reg export 'HKLM\SOFTWARE\Classes\Dropbox.AutoplayEventHandler' "$env:USERPROFILE\Desktop\Dropbox-registry-backup-1.reg" /y
Remove-Item -Path 'HKLM:\SOFTWARE\Classes\Dropbox.AutoplayEventHandler' -Recurse
reg export 'HKLM\SOFTWARE\Classes\DropboxUpdate.Update3WebMachine' "$env:USERPROFILE\Desktop\Dropbox-registry-backup-2.reg" /y
Remove-Item -Path 'HKLM:\SOFTWARE\Classes\DropboxUpdate.Update3WebMachine' -Recurse
reg export 'HKLM\SOFTWARE\WOW6432Node\DropboxUpdate' "$env:USERPROFILE\Desktop\Dropbox-registry-backup-3.reg" /y
Remove-Item -Path 'HKLM:\SOFTWARE\WOW6432Node\DropboxUpdate' -Recurse

# 4. Delete leftover folders and files
Remove-Item -LiteralPath 'C:\Program Files (x86)\Dropbox' -Recurse -Force
Remove-Item -LiteralPath 'C:\Program Files\Dropbox' -Recurse -Force

# 5. Remove app packages
Get-AppxPackage -Name 'DropboxInc.Dropbox' | Remove-AppxPackage