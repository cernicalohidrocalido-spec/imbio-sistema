@echo off
title SGO-IMBIO con ngrok
color 1F
echo ========================================
echo   IMBIO-Pabellon - Inicio con ngrok
echo ========================================
echo.

REM Verifica que ngrok este disponible
where ngrok >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] ngrok no encontrado.
    echo Descarga ngrok desde https://ngrok.com/download
    echo y ponlo en esta carpeta o en el PATH.
    pause
    exit /b 1
)

REM Arranca el servidor Python en segundo plano
echo [1/2] Iniciando servidor SGO-IMBIO en puerto 8080...
start "SGO-IMBIO Server" /min python server.py
timeout /t 2 /nobreak >nul

REM Arranca ngrok
echo [2/2] Abriendo tunel ngrok...
echo.
echo *** Copia la URL https://xxxx.ngrok-free.app que aparece ***
echo *** Esa URL funciona desde cualquier celular o PC       ***
echo.
ngrok http 8080
