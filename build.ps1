$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
Set-Location $root
python -m pip install -r requirements.txt
python -m pip install -r requirements-build.txt
python -m PyInstaller --noconfirm --clean --windowed --name Intranet --onedir --icon assets/intranet.ico main.py
$iscc = "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
if (-not (Test-Path $iscc)) { throw "ISCC.exe not found. Install Inno Setup 6." }
& $iscc installer.iss
if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed with exit code $LASTEXITCODE" }
