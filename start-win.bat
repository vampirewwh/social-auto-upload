@echo off
setlocal
TITLE social-auto-upload Web
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-web.ps1"
endlocal
