@echo off
REM Run Nyasha's Downloader from inside the app folder
pushd "%~dp0"
REM Start server in new PowerShell window
start "Nyasha Server" powershell -NoExit -Command "Set-Location -LiteralPath '%~dp0'; if (Test-Path ..\.venv\Scripts\Activate.ps1) { . ..\.venv\Scripts\Activate.ps1 }; python .\app.py"

REM Wait a moment then open the browser
timeout /t 3 /nobreak > nul
start "" "http://127.0.0.1:5001"
popd
