@echo off
title SGO-IMBIO - Cloudflare Tunnel
color 1F
echo ========================================
echo   IMBIO-Pabellon - Cloudflare Tunnel
echo ========================================
echo.

REM Arranca el servidor Python en segundo plano
echo [1/2] Iniciando servidor SGO-IMBIO en puerto 8080...
start "SGO-IMBIO Server" /min python server.py
timeout /t 2 /nobreak >nul

REM Arranca Cloudflare Tunnel
echo [2/2] Abriendo tunel Cloudflare...
echo.
echo *** La URL https://xxx.trycloudflare.com aparecera abajo ***
echo *** Esa URL funciona 24/7 desde cualquier celular o PC   ***
echo.
cloudflared tunnel --url http://localhost:8080
