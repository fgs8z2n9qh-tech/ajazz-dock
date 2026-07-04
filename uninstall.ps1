# Uninstall Hexpad: stop it, remove autostart, shortcuts, and the installed folder.
# Your settings in %APPDATA%\AjazzDock are kept unless you delete that folder.
Get-Process Hexpad, AjazzDock -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 600

# autostart: scheduled task + retire any legacy Run-key entries (new + old id)
schtasks /delete /tn 'Hexpad' /f 2>$null | Out-Null
schtasks /delete /tn 'AjazzDock' /f 2>$null | Out-Null
try { Remove-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run' -Name 'Hexpad' -ErrorAction Stop } catch {}
try { Remove-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run' -Name 'AjazzDock' -ErrorAction Stop } catch {}

$shortcuts = @(
  (Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Hexpad.lnk'),
  (Join-Path ([Environment]::GetFolderPath('Desktop')) 'Hexpad.lnk'),
  (Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\AjazzDock.lnk'),
  (Join-Path ([Environment]::GetFolderPath('Desktop')) 'AjazzDock.lnk')
)
Remove-Item $shortcuts -Force -ErrorAction SilentlyContinue

Remove-Item (Join-Path $env:LOCALAPPDATA 'Hexpad') -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item (Join-Path $env:LOCALAPPDATA 'AjazzDock') -Recurse -Force -ErrorAction SilentlyContinue

Write-Host "Hexpad uninstalled." -ForegroundColor Green
Write-Host "Settings remain in %APPDATA%\AjazzDock (delete that folder to remove them too)."
