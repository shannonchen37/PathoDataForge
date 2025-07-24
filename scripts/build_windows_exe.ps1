$ErrorActionPreference = "Stop"

python -m pip install -r requirements.txt
pyinstaller --noconsole --onefile --name iMoonLab-PathoDataForge main.py

Write-Host "Build complete: dist\iMoonLab-PathoDataForge.exe"
