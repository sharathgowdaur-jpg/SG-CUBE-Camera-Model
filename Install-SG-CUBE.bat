@echo off
title SG CUBE 2.5.0 Windows Installer
setlocal enabledelayedexpansion

echo ============================================================
echo        SG CUBE 2.5.0 — OFFICIAL WINDOWS INSTALLER          
echo ============================================================
echo.

cd /d "%~dp0"

REM Find best available Python runtime
if exist "%LOCALAPPDATA%\Programs\SG-CUBE\runtime\Scripts\python.exe" (
    set "PYTHON_EXE=%LOCALAPPDATA%\Programs\SG-CUBE\runtime\Scripts\python.exe"
) else if exist "%~dp0runtime\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0runtime\Scripts\python.exe"
) else if exist "%~dp0.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

echo Executing SG CUBE automated deployment engine...
"%PYTHON_EXE%" "%~dp0install_sg_cube.py"

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Installation failed or encountered warnings.
    pause
    exit /b %ERRORLEVEL%
)

echo.
pause
