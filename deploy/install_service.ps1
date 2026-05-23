# Install Finance Tracker as a Windows service using NSSM
# Run as Administrator
# Prerequisites: nssm.exe on PATH, Python installed

param(
    [string]$ServiceName = "FinanceTracker",
    [string]$AppDir = "C:\fintracker",
    [string]$PythonExe = "python",
    [int]$Port = 8000
)

$runner = Join-Path $AppDir "deploy\waitress_runner.py"

Write-Host "Installing '$ServiceName' service..."
nssm install $ServiceName $PythonExe $runner
nssm set $ServiceName AppDirectory $AppDir
nssm set $ServiceName AppEnvironmentExtra "PORT=$Port"
nssm set $ServiceName Start SERVICE_AUTO_START
nssm set $ServiceName AppStdout (Join-Path $AppDir "logs\service.log")
nssm set $ServiceName AppStderr (Join-Path $AppDir "logs\service_err.log")

New-Item -ItemType Directory -Force -Path (Join-Path $AppDir "logs") | Out-Null

Write-Host "Starting service..."
nssm start $ServiceName

Write-Host "Done. Finance Tracker runs on http://localhost:$Port"
Write-Host "Add a Windows Firewall rule to allow LAN access:"
Write-Host "  netsh advfirewall firewall add rule name='FinanceTracker' dir=in action=allow protocol=TCP localport=$Port"
