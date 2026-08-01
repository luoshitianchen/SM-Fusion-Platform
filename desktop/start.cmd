@echo off
setlocal
cd /d "%~dp0"
if exist "SM-Fusion-Platform.exe" (
  start "" "SM-Fusion-Platform.exe"
  exit /b 0
)
echo SM-Fusion-Platform.exe was not found.
exit /b 1
