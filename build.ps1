# Build a single-file Windows executable with PyInstaller.
# Usage: .\build.ps1
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtualenv..." -ForegroundColor Cyan
    python -m venv .venv
}

& .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install pyinstaller

$IconArg = @()
if (Test-Path "assets\tray_icon.ico") {
    $IconArg = @("--icon", "assets\tray_icon.ico")
}

$AssetsArg = @()
if (Test-Path "assets") {
    $AssetsArg = @("--add-data", "assets;assets")
}

pyinstaller `
    --noconfirm `
    --windowed `
    --onefile `
    --name "JoystickShortcuts" `
    @IconArg `
    @AssetsArg `
    main.py

Write-Host ""
Write-Host "Build done: dist\JoystickShortcuts.exe" -ForegroundColor Green
