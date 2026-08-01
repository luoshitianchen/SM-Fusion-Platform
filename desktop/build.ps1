$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
python -m pip install -r requirements.txt
python -m PyInstaller --noconfirm --clean --onefile --windowed --name SM-Fusion-Platform main.py
Write-Host "Desktop package created at desktop/dist/SM-Fusion-Platform.exe"
