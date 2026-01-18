@echo off
title Chess Game Setup
color 0A
cls
echo ============================================
echo          Python Chess Game Setup
echo ============================================
echo.
echo Checking Python installation...
where python >nul 2>&1
if %errorlevel% neq 0 (
    color 0C
    echo Python is not installed or not in PATH.
    echo Please install Python 3.7 or newer from https://www.python.org
    goto end
)
python -c "import sys; sys.exit(0 if sys.version_info >= (3,7) else 1)"
if %errorlevel% neq 0 (
    color 0C
    echo Python 3.7 or newer is required.
    goto end
)
echo.
echo Installing Python dependencies from requirements.txt...
if exist requirements.txt (
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt
) else (
    echo requirements.txt not found. No dependencies to install.
)
echo.
echo Setup complete.
:end
echo.
echo Press any key to close this window.
pause >nul

