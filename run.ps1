# Run Nyasha's Downloader from inside the app folder
try {
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
} catch {
    $scriptDir = Get-Location
}

# Activate venv from repo root if present and start server
$serverCommand = "Set-Location -LiteralPath '$scriptDir'; if (Test-Path '..\\.venv\\Scripts\\Activate.ps1') { . '..\\.venv\\Scripts\\Activate.ps1' }; python .\\app.py"
Start-Process -FilePath powershell -ArgumentList "-NoExit", "-Command", $serverCommand

# wait briefly for server to start then open browser
Start-Sleep -Seconds 3
Start-Process "http://127.0.0.1:5001"
