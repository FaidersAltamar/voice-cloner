# Voice Cloner - One-Click Setup
# Run: powershell -ExecutionPolicy Bypass -File setup.ps1

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot

Write-Host "=== Voice Cloner Setup ===" -ForegroundColor Cyan
Write-Host ""

# Check Python
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "Python not found. Please install Python 3.10 from https://www.python.org/" -ForegroundColor Red
    exit 1
}

# Clone rvc-no-gui if not exists
$RvcPath = Join-Path $ProjectRoot "rvc-no-gui"
if (-not (Test-Path $RvcPath)) {
    Write-Host "Cloning rvc-no-gui (headless RVC)..." -ForegroundColor Yellow
    git clone https://github.com/nakshatra-garg/rvc-no-gui.git $RvcPath
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Git clone failed. Is Git installed?" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "rvc-no-gui already exists." -ForegroundColor Green
}

# Install dependencies
Write-Host "Installing dependencies (pydub, flask)..." -ForegroundColor Yellow
python -m pip install pydub flask -q

# Run RVC setup (downloads pretrained models)
Write-Host "Running RVC setup (downloads models, first time only)..." -ForegroundColor Yellow
Push-Location $RvcPath
python pipeline.py setup 2>$null
Pop-Location

Write-Host ""
Write-Host "=== Setup Complete ===" -ForegroundColor Green
Write-Host ""
Write-Host "Start the web interface:" -ForegroundColor Cyan
Write-Host "  python app.py"
Write-Host ""
Write-Host "Then open: http://localhost:7860"
Write-Host ""
