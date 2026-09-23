@echo off
title Sistema Escolar de Puntos por QR (Mobile & Desktop)
cd /d "%~dp0"
echo ========================================================
echo    INICIANDO SISTEMA ESCOLAR DE PUNTOS POR CODIGO QR
echo ========================================================
echo.
echo Horario escolar: Lunes a Viernes de 08:00 a 14:30
echo Clave de acceso Docente: 0000
echo.
echo Iniciando servidor en segundo plano...
start http://localhost:8000
python server.py
pause
