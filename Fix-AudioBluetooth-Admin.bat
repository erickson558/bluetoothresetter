@echo off
setlocal EnableExtensions
cd /d "%~dp0"

net session >nul 2>&1
if %errorlevel% neq 0 (
    powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%ComSpec%' -ArgumentList '/c','\"\"%~f0\"\"' -Verb RunAs"
    exit /b
)

set "SCRIPT_PATH=%~dp0scripts\Fix-AudioBluetooth.ps1"

if not exist "%SCRIPT_PATH%" (
    echo No se encontro el script PowerShell en "%SCRIPT_PATH%".
    pause
    exit /b 1
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_PATH%"
set "EXIT_CODE=%errorlevel%"

echo.
if "%EXIT_CODE%"=="0" (
    echo Reparacion completada.
) else (
    echo Reparacion completada con advertencias o errores. Revisa log.txt.
)

pause
exit /b %EXIT_CODE%
