@echo off
title SGO-IMBIO Server
cd /d "%~dp0"
echo Iniciando SGO-IMBIO en http://localhost:8080 ...
python server.py
pause
