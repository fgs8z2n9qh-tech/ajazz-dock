# Build AjazzDock into a single standalone Windows .exe (no Python needed to run).
$root = Split-Path -Parent $MyInvocation.MyCommand.Definition
$vpy = Join-Path $root ".venv\Scripts\python.exe"

Write-Host "Installing PyInstaller..." -ForegroundColor Cyan
& $vpy -m pip install --quiet --upgrade pyinstaller

Write-Host "Generating app icon..." -ForegroundColor Cyan
& $vpy "$root\tools\make_icon.py"

Write-Host "Building AjazzDock.exe..." -ForegroundColor Cyan
& $vpy -m PyInstaller --noconfirm --clean --onefile --windowed --name AjazzDock `
  --icon "$root\assets\ajazzdock.ico" `
  --collect-all hid `
  --collect-all pycaw `
  --collect-all comtypes `
  --collect-submodules keyboard `
  --collect-submodules mouse `
  --collect-all sounddevice `
  --collect-all soundfile `
  --exclude-module tkinter `
  --exclude-module PySide6.QtQml --exclude-module PySide6.QtQuick `
  --exclude-module PySide6.Qt3DCore --exclude-module PySide6.QtMultimedia `
  --distpath "$root\dist" --workpath "$root\build" --specpath "$root" `
  "$root\run.py"

if (Test-Path "$root\dist\AjazzDock.exe") {
  Write-Host "`nBuilt: $root\dist\AjazzDock.exe" -ForegroundColor Green
} else {
  Write-Host "`nBuild failed - see PyInstaller output above." -ForegroundColor Red
}
