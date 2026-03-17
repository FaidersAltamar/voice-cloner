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
echo Esto puede tardar 15-40 minutos la primera vez (torch, modelos RVC).
echo.
pause

echo.
echo Ejecutando instalacion...
echo.
powershell -ExecutionPolicy Bypass -File "%~dp0setup.ps1"
if errorlevel 1 (
    echo.
    echo Hubo problemas en la instalacion. Revisa los mensajes arriba.
    echo.
    set /p continuar="Intentar abrir la app de todos modos? (S/N): "
    if /i not "%continuar%"=="S" exit /b 1
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
