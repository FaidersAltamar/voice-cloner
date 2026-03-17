# Voice Cloner - Instalacion automatica completa
# Instala Python, Git, FFmpeg si faltan, luego todas las dependencias
# Ejecutar: powershell -ExecutionPolicy Bypass -File setup.ps1

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot

function Write-Step { param($msg) Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Write-Ok { param($msg) Write-Host "  [OK] $msg" -ForegroundColor Green }
function Write-Warn { param($msg) Write-Host "  [!] $msg" -ForegroundColor Yellow }

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "   Voice Cloner - Instalacion automatica" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

# 1. Python
Write-Step "Comprobando Python..."
$pythonCmd = $null
foreach ($cmd in @("python", "python3", "py")) {
    try {
        $v = & $cmd --version 2>&1
        if ($LASTEXITCODE -eq 0) { $pythonCmd = $cmd; break }
    } catch {}
}
if (-not $pythonCmd) {
    Write-Warn "Python no encontrado. Intentando instalar con winget..."
    try {
        winget install Python.Python.3.11 --accept-package-agreements --accept-source-agreements 2>$null
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
        Start-Sleep -Seconds 2
    } catch {}
    $pythonCmd = "python"
}
if (-not (Get-Command $pythonCmd -ErrorAction SilentlyContinue)) {
    Write-Host "Python no encontrado. Instalalo desde: https://www.python.org/" -ForegroundColor Red
    Write-Host "Marca 'Add Python to PATH' durante la instalacion." -ForegroundColor Yellow
    exit 1
}
Write-Ok "Python listo"

# 2. Git
Write-Step "Comprobando Git..."
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Warn "Git no encontrado. Intentando instalar con winget..."
    try { winget install Git.Git --accept-package-agreements --accept-source-agreements 2>$null } catch {}
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
}
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Warn "Git no instalado. Algunas funciones pueden fallar."
} else {
    Write-Ok "Git listo"
}

# 3. FFmpeg
Write-Step "Comprobando FFmpeg..."
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    Write-Warn "FFmpeg no encontrado. Intentando instalar con winget..."
    try { winget install Gyan.FFmpeg --accept-package-agreements --accept-source-agreements 2>$null } catch {}
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
}
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    Write-Warn "FFmpeg no instalado. Necesario para audio."
} else {
    Write-Ok "FFmpeg listo"
}

# 4. Dependencias basicas (pydub, flask para la app)
Write-Step "Instalando dependencias basicas..."
& $pythonCmd -m pip install --upgrade pip -q
& $pythonCmd -m pip install pydub flask -q
Write-Ok "Dependencias basicas instaladas"

# 5. RVC setup (descarga modelos, instala deps de RVC)
Write-Step "Configurando RVC (descarga modelos, primera vez puede tardar)..."
$RvcPath = Join-Path $ProjectRoot "rvc-no-gui"
if (-not (Test-Path $RvcPath)) {
    Write-Host "  Clonando rvc-no-gui..." -ForegroundColor Yellow
    git clone https://github.com/nakshatra-garg/rvc-no-gui.git $RvcPath
}
if (-not (Test-Path (Join-Path $RvcPath "pipeline.py"))) {
    Write-Host "  Error: rvc-no-gui no tiene pipeline.py. Verifica la carpeta." -ForegroundColor Red
} else {
    # Usar Start-Process para evitar NativeCommandError cuando Python escribe a stderr
    $p = Start-Process -FilePath $pythonCmd -ArgumentList "pipeline.py","setup" -WorkingDirectory $RvcPath -Wait -NoNewWindow -PassThru
    if ($p.ExitCode -ne 0) {
        Write-Warn "RVC setup fallo (codigo $($p.ExitCode)). Ejecuta manualmente: cd rvc-no-gui; python pipeline.py setup"
    } else {
        Write-Ok "RVC configurado"
    }
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "   Instalacion completada" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "Ejecuta: EJECUTAR_APP.bat" -ForegroundColor Cyan
Write-Host ""
