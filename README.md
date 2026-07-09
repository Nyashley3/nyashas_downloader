# Nyasha's Downloader

## Run it automatically on Windows

1. Install Python dependencies:
   - `"p:/Inventory System/.venv/Scripts/python.exe" -m pip install -r requirements.txt`
2. Start it in the background with PowerShell:
   - `powershell -NoProfile -ExecutionPolicy Bypass -File .\run_service.ps1`
3. For a more permanent setup, use Windows Task Scheduler to launch `run_service.ps1` at logon.

## Public hosting (recommended)

This app is ready to be deployed to Render for free.

### Deploy to Render
1. Push this folder to GitHub.
2. Create a new Render Web Service.
3. Connect the GitHub repository.
4. Render will detect the Python app and use the provided config.
5. Once deployed, Render gives you a public URL that your mom can open from anywhere.

### Phone-friendly access

The app is designed to work in a mobile browser because the UI is responsive. Once it is hosted publicly, your mom can open the URL on her phone with no setup.
