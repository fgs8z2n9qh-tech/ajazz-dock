# Install AjazzDock to a stable per-user location with Start Menu + Desktop shortcuts.
# Run build.ps1 first to produce dist\AjazzDock.exe.
$root = Split-Path -Parent $MyInvocation.MyCommand.Definition
$src = Join-Path $root 'dist\AjazzDock.exe'
if (-not (Test-Path $src)) {
  Write-Host "dist\AjazzDock.exe not found - run ./build.ps1 first." -ForegroundColor Red
  exit 1
}

$installDir = Join-Path $env:LOCALAPPDATA 'AjazzDock'
New-Item -ItemType Directory -Force -Path $installDir | Out-Null

# Stop any running instance so we can overwrite the exe.
Get-Process AjazzDock -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 700

$exe = Join-Path $installDir 'AjazzDock.exe'
Copy-Item $src $exe -Force
$ico = Join-Path $root 'assets\ajazzdock.ico'
$icoInstalled = Join-Path $installDir 'ajazzdock.ico'
if (Test-Path $ico) { Copy-Item $ico $icoInstalled -Force }

# Create shortcuts (Start Menu + Desktop).
$ws = New-Object -ComObject WScript.Shell
function New-AppShortcut($path) {
  $lnk = $ws.CreateShortcut($path)
  $lnk.TargetPath = $exe
  $lnk.WorkingDirectory = $installDir
  if (Test-Path $icoInstalled) { $lnk.IconLocation = $icoInstalled }
  $lnk.Description = 'AjazzDock - AKP03 controller'
  $lnk.Save()
}
$startMenu = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\AjazzDock.lnk'
$desktop = Join-Path ([Environment]::GetFolderPath('Desktop')) 'AjazzDock.lnk'
New-AppShortcut $startMenu
New-AppShortcut $desktop

# Point autostart at the installed exe.
$runKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
Set-ItemProperty -Path $runKey -Name 'AjazzDock' -Value ('"{0}" --tray' -f $exe) -Force

Write-Host ""
Write-Host "Installed:        $exe" -ForegroundColor Green
Write-Host "Start Menu:       $startMenu"
Write-Host "Desktop shortcut: $desktop"
Write-Host "Autostart ->      $exe"

# Launch the installed app.
Start-Process -FilePath $exe
Write-Host "Launched AjazzDock from the installed location." -ForegroundColor Green
