@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

echo.
echo   StyrAI partner demonstration
echo   -----------------------------
echo   Preparing the local AI governance control plane...
echo.

where py >nul 2>&1
if %errorlevel% equ 0 (
  py -3 launch_styrai.py
  set "STYRAI_STATUS=!errorlevel!"
  goto :finished
)

where python >nul 2>&1
if %errorlevel% equ 0 (
  python launch_styrai.py
  set "STYRAI_STATUS=!errorlevel!"
  goto :finished
)

echo Python was not found. Install Python 3.11 or newer from python.org,
echo then double-click this file again.
set "STYRAI_STATUS=1"

:finished
echo.
if not "%STYRAI_STATUS%"=="0" echo StyrAI stopped with an error. See START_HERE.md for help.
pause
exit /b %STYRAI_STATUS%
