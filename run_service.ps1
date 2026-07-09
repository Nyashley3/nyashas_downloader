$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repo
"p:/Inventory System/.venv/Scripts/python.exe" -m pip install -r requirements.txt
"p:/Inventory System/.venv/Scripts/python.exe" app.py
