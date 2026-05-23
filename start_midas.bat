@echo off
pushd "D:\Claude Workspace\Midas"

start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\ChromeDebug"
timeout /t 3 /nobreak >nul

start "Midas" cmd /k "pushd D:\Claude^ Workspace\Midas && python -X utf8 -u main.py"

start /b "" ngrok http 5000 > nul 2>&1

start "Midas Dashboard" cmd /k "pushd D:\Claude^ Workspace\Midas && python -X utf8 -u dashboard.py"

python -X utf8 -u ngrok_notify.py
