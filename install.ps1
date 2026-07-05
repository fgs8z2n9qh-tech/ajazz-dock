# Install Hexpad to a stable per-user location with Start Menu + Desktop shortcuts.
# The app runs elevated (to read CPU temperature), so this installer self-elevates to stop a
# running (elevated) instance and register an elevated autostart task. Run build.ps1 first.
# NB: your settings live in %APPDATA%\AjazzDock and are NOT touched by this rebrand.
$root = Split-Path -Parent $MyInvocation.MyCommand.Definition
$src = Join-Path $root 'dist\Hexpad'                 # onedir build: a folder, not a single .exe
if (-not (Test-Path (Join-Path $src 'Hexpad.exe'))) {
  Write-Host "dist\Hexpad\Hexpad.exe not found - run ./build.ps1 first." -ForegroundColor Red
  exit 1
}

# ---- self-elevate (needed to stop an elevated instance + create the /rl highest task) ----
$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltinRole]::Administrator)) {
  Write-Host "Requesting administrator rights (UAC) to install..." -ForegroundColor Cyan
  Start-Process powershell -Verb RunAs -ArgumentList @(
    '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$($MyInvocation.MyCommand.Definition)`"")
  exit
}

# Stop any running instance (new OR the old AjazzDock build) so we can overwrite / clean up.
Get-Process Hexpad, AjazzDock -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 800

$installDir = Join-Path $env:LOCALAPPDATA 'Hexpad'
# Clear any previous install (an old single-exe onefile build, or a stale onedir) so no orphan
# files linger, then copy the whole onedir folder in. (Settings live in %APPDATA%, untouched.)
if (Test-Path $installDir) { Remove-Item $installDir -Recurse -Force -ErrorAction SilentlyContinue }
New-Item -ItemType Directory -Force -Path $installDir | Out-Null
Copy-Item (Join-Path $src '*') $installDir -Recurse -Force

$exe = Join-Path $installDir 'Hexpad.exe'
$ico = Join-Path $root 'assets\hexpad.ico'
$icoInstalled = Join-Path $installDir 'hexpad.ico'
if (Test-Path $ico) { Copy-Item $ico $icoInstalled -Force }

# Create shortcuts (Start Menu + Desktop).
$ws = New-Object -ComObject WScript.Shell
function New-AppShortcut($path) {
  $lnk = $ws.CreateShortcut($path)
  $lnk.TargetPath = $exe
  $lnk.WorkingDirectory = $installDir
  if (Test-Path $icoInstalled) { $lnk.IconLocation = $icoInstalled }
  $lnk.Description = 'Hexpad - AKP03 stream dock controller'
  $lnk.Save()
}
$startMenu = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Hexpad.lnk'
$desktop = Join-Path ([Environment]::GetFolderPath('Desktop')) 'Hexpad.lnk'
New-AppShortcut $startMenu
New-AppShortcut $desktop

# Autostart: an elevated Scheduled Task at logon (an HKCU Run entry can't auto-elevate).
Remove-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run' -Name 'Hexpad' -ErrorAction SilentlyContinue
schtasks /create /tn 'Hexpad' /tr ('"{0}" --tray' -f $exe) /sc onlogon /rl highest /f | Out-Null

# ---- retire the old "AjazzDock" install (rebrand cleanup; the %APPDATA%\AjazzDock config STAYS) ----
schtasks /delete /tn 'AjazzDock' /f 2>$null | Out-Null
Remove-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run' -Name 'AjazzDock' -ErrorAction SilentlyContinue
$oldStart = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\AjazzDock.lnk'
$oldDesk = Join-Path ([Environment]::GetFolderPath('Desktop')) 'AjazzDock.lnk'
Remove-Item $oldStart, $oldDesk -Force -ErrorAction SilentlyContinue
$oldDir = Join-Path $env:LOCALAPPDATA 'AjazzDock'
Remove-Item $oldDir -Recurse -Force -ErrorAction SilentlyContinue   # only the old exe folder; config is in %APPDATA%

Write-Host ""
Write-Host "Installed:        $exe" -ForegroundColor Green
Write-Host "Start Menu:       $startMenu"
Write-Host "Desktop shortcut: $desktop"
Write-Host "Autostart:        Scheduled Task 'Hexpad' (elevated, at logon)"
Write-Host "Old AjazzDock install/shortcuts/task removed; your settings in %APPDATA%\AjazzDock kept."

# Launch the installed app (already elevated -> no second UAC prompt).
Start-Process -FilePath $exe
Write-Host "Launched Hexpad from the installed location." -ForegroundColor Green
Start-Sleep -Milliseconds 1500
