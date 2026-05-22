@echo off
title Midas Launcher

echo Starting Chrome Debug Port 9222...
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\ChromeDebug"

timeout /t 3 /nobreak >nul

echo Starting Midas...
start "Midas" cmd /k "cd /d "%~dp0" && python -X utf8 -u main.py"
