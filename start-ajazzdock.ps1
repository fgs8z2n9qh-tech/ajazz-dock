# Launch AjazzDock silently in the background (no console window).
$root = Split-Path -Parent $MyInvocation.MyCommand.Definition
$pyw = Join-Path $root ".venv\Scripts\pythonw.exe"
if (-not (Test-Path $pyw)) { $pyw = "pythonw.exe" }
Start-Process -FilePath $pyw -ArgumentList "-m", "dock" -WorkingDirectory $root -WindowStyle Hidden
Write-Host "AjazzDock started in the system tray."
