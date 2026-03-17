@echo off
title Voice Cloner - Instalacion y Ejecucion
cd /d "%~dp0"

echo.
echo ============================================
echo   Voice Cloner - Instalacion automatica
echo ============================================
echo.
echo Si es la primera vez, instalara todo lo necesario.
echo (Python, Git, FFmpeg, dependencias, modelos RVC)
echo.
echo Esto puede tardar 5-15 minutos la primera vez.
echo.
pause

echo.
echo Ejecutando instalacion...
echo.
powershell -ExecutionPolicy Bypass -File "%~dp0setup.ps1"
if errorlevel 1 (
    echo.
    echo Error en la instalacion.
    pause
    exit /b 1
)

echo.
echo Iniciando Voice Cloner...
echo.
python voice_cloner_app.py
if errorlevel 1 (
    echo.
    echo Error al ejecutar. Prueba: python voice_cloner_app.py
    pause
)
