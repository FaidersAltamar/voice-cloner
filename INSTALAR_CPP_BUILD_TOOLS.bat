@echo off
title Instalar C++ Build Tools
echo.
echo Este script instala Microsoft C++ Build Tools.
echo Solo necesario si el wheel precompilado de fairseq falla (p. ej. red).
echo.
echo IMPORTANTE: Ejecuta este archivo como Administrador
echo (clic derecho - Ejecutar como administrador)
echo.
echo La instalacion puede tardar 5-15 minutos.
echo.
pause

winget install -e --id Microsoft.VisualStudio.2022.BuildTools --override "--passive --wait --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended" --accept-package-agreements --accept-source-agreements

echo.
echo Si la instalacion fue exitosa, cierra esta ventana,
echo abre una NUEVA terminal y ejecuta INSTALAR_Y_EJECUTAR.bat
echo.
pause
