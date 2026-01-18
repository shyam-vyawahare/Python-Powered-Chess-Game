@echo off
title Chess Game - GUI Version
color 0A
cls

echo ========================================
echo    Chess Game - Visual Interface
echo ========================================
echo.

cd /d "%~dp0"

echo Checking Python 3.11 installation...
py -3.11 --version >nul 2>&1
if errorlevel 1 goto python_missing

echo [OK] Python 3.11 detected
echo.

echo Checking GUI dependencies (pygame)...
py -3.11 -m pip show pygame >nul 2>&1
if errorlevel 1 (
    echo Installing pygame...
    py -3.11 -m pip install --upgrade pip
    py -3.11 -m pip install pygame
)

echo.
echo [STARTING] Launching Chess Game GUI...
echo ========================================
echo.

py -3.11 -m chess_game.main

echo.
echo Game closed.
goto end

:python_missing
color 0C
echo [ERROR] Python 3.11 not found by launcher.
echo Install Python 3.11 (64-bit) from python.org
goto end

:end
echo.
echo Press any key to close this window.
pause >nul
