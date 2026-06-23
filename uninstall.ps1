# Uninstall AjazzDock: stop it, remove autostart, shortcuts, and the installed folder.
# Your settings in %APPDATA%\AjazzDock are kept unless you delete that folder.
Get-Process AjazzDock -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 600

try { Remove-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run' -Name 'AjazzDock' -ErrorAction Stop } catch {}

$startMenu = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\AjazzDock.lnk'
$desktop = Join-Path ([Environment]::GetFolderPath('Desktop')) 'AjazzDock.lnk'
Remove-Item $startMenu, $desktop -Force -ErrorAction SilentlyContinue

$installDir = Join-Path $env:LOCALAPPDATA 'AjazzDock'
Remove-Item $installDir -Recurse -Force -ErrorAction SilentlyContinue

Write-Host "AjazzDock uninstalled." -ForegroundColor Green
Write-Host "Settings remain in %APPDATA%\AjazzDock (delete that folder to remove them too)."
