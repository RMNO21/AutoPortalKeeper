@echo off
title AutoPortal Keeper - Live Diagnostic & Debug Console
color 0A
echo =========================================================
echo    AutoPortal Keeper - Live Debug & Diagnostic Console
echo           Developed by Raman Tondro (@RMNO21)
echo =========================================================
echo.
echo Running diagnostic test in real-time...
echo Logs are also continuously saved to: debug.log
echo Press Ctrl+C anytime to stop.
echo.

cd /d "%~dp0"
python portal_keeper.py
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Python script encountered an error or was interrupted.
)
pause
