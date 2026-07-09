@echo off
setlocal
set "APP_DIR=P:\nyashas_downloader"
set "VENV=P:\Inventory System\.venv\Scripts\Activate.ps1"

REM Start server in a new PowerShell window
start "Nyasha Server" powershell -NoExit -ExecutionPolicy Bypass -Command "Set-Location -LiteralPath '%APP_DIR%'; if (Test-Path '%VENV%') { . '%VENV%' }; python '.\app.py'"

REM Wait a moment then open the browser
timeout /t 3 /nobreak > nul
start "" "http://127.0.0.1:5001"
