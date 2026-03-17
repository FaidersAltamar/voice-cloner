@echo off
title Subir a GitHub
cd /d "%~dp0"

echo ========================================
echo   Subir Voice Cloner a GitHub
echo ========================================
echo.

REM Comprobar si ya esta autenticado
gh auth status 2>nul
if errorlevel 1 (
    echo Primero debes iniciar sesion en GitHub.
    echo Se abrira el navegador o pedira codigo.
    echo.
    gh auth login
    if errorlevel 1 (
        echo Error al autenticar.
        pause
        exit /b 1
    )
)

echo.
echo Creando repositorio y subiendo codigo...
echo.

gh repo create voice-cloner --public --source=. --remote=origin --push

if errorlevel 1 (
    echo.
    echo Si el repo ya existe, intenta solo hacer push:
    echo   git push -u origin main
    echo.
    pause
    exit /b 1
)

echo.
echo ========================================
echo   Listo. Repo creado en GitHub.
echo ========================================
pause
