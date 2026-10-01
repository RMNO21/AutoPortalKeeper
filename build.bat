@echo off
setlocal
echo ===================================================
echo Building AutoPortal Keeper with Native Windows CSC
echo Developed by Raman Tondro (@RMNO21)
echo ===================================================

set "CSC=C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"

if not exist "%CSC%" (
    echo [ERROR] csc.exe compiler not found at %CSC%
    pause
    exit /b 1
)

if not exist "release" mkdir release

echo [*] Compiling release\Uninstall.exe ...
"%CSC%" /target:winexe /out:"release\Uninstall.exe" /r:System.Windows.Forms.dll /r:System.Drawing.dll src\Uninstaller.cs
if %errorlevel% neq 0 (
    echo [ERROR] Failed to compile Uninstall.exe
    pause
    exit /b 1
)

echo [*] Compiling release\Setup.exe ...
"%CSC%" /target:winexe /out:"release\Setup.exe" /r:System.Windows.Forms.dll /r:System.Drawing.dll /r:System.Security.dll /r:Microsoft.CSharp.dll src\Installer.cs
if %errorlevel% neq 0 (
    echo [ERROR] Failed to compile Setup.exe
    pause
    exit /b 1
)

echo [*] Copying python engine ...
copy /Y "src\portal_keeper.py" "release\portal_keeper.py" >nul

echo ===================================================
echo [SUCCESS] Build completed successfully into release\
echo ===================================================
