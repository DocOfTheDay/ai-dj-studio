@echo off
setlocal EnableDelayedExpansion
title AI DJ Studio — Windows Build Script

:: ═══════════════════════════════════════════════════════════════════
::  AI DJ Studio v2.0 — Automated Windows Build Script
::  
::  What this does (fully automated):
::   1. Checks Python 3.10+ is installed
::   2. Creates a clean virtual environment
::   3. Installs all required packages
::   4. Installs PyInstaller
::   5. Builds the Windows .exe using PyInstaller
::   6. Builds the installer Setup.exe using Inno Setup (if installed)
::   7. Opens the output folder when done
::
::  HOW TO USE:
::   Right-click build_windows.bat → Run as Administrator
::   (or just double-click — Admin not required for user install)
:: ═══════════════════════════════════════════════════════════════════

echo.
echo  ╔══════════════════════════════════════════════════════════════╗
echo  ║          AI DJ Studio v2.0 — Windows Build Script           ║
echo  ║          AMD Ryzen 7840HS Edition                           ║
echo  ╚══════════════════════════════════════════════════════════════╝
echo.

:: ── Step 1: Check Python ──────────────────────────────────────────
echo [1/7] Checking Python installation...
python --version 2>nul
if errorlevel 1 (
    echo.
    echo  ❌  Python not found!
    echo.
    echo  Please install Python 3.10 or newer from:
    echo  https://www.python.org/downloads/
    echo.
    echo  During installation, CHECK the box:
    echo  "Add Python to PATH"
    echo.
    pause
    exit /b 1
)
echo  ✅  Python found
echo.

:: ── Step 2: Check pip ─────────────────────────────────────────────
echo [2/7] Checking pip...
python -m pip --version 2>nul
if errorlevel 1 (
    echo  ❌  pip not found. Reinstall Python with pip included.
    pause
    exit /b 1
)
echo  ✅  pip found
echo.

:: ── Step 3: Create virtual environment ───────────────────────────
echo [3/7] Creating virtual environment (build_env)...
if exist build_env (
    echo  Virtual environment already exists, reusing...
) else (
    python -m venv build_env
    if errorlevel 1 (
        echo  ❌  Failed to create virtual environment
        pause
        exit /b 1
    )
)
echo  ✅  Virtual environment ready
echo.

:: ── Step 4: Activate and install packages ────────────────────────
echo [4/7] Installing required packages...
echo  (This may take 5-15 minutes on first run)
echo.
call build_env\Scripts\activate.bat

:: Upgrade pip first
python -m pip install --upgrade pip --quiet

:: Install audio packages
echo  Installing audio libraries...
pip install numpy scipy --quiet
pip install librosa --quiet
pip install soundfile --quiet
pip install pydub --quiet
pip install yt-dlp --quiet
pip install Pillow --quiet

if errorlevel 1 (
    echo.
    echo  ❌  Package installation failed!
    echo  Check your internet connection and try again.
    pause
    exit /b 1
)
echo  ✅  All packages installed
echo.

:: ── Step 5: Install PyInstaller ───────────────────────────────────
echo [5/7] Installing PyInstaller...
pip install pyinstaller --quiet
if errorlevel 1 (
    echo  ❌  PyInstaller installation failed
    pause
    exit /b 1
)
echo  ✅  PyInstaller ready
echo.

:: ── Step 6: Build EXE with PyInstaller ────────────────────────────
echo [6/7] Building Windows application...
echo  (This takes 3-8 minutes — please wait)
echo.

:: Clean previous build
if exist dist\AIDJStudio (
    echo  Cleaning previous build...
    rmdir /s /q dist\AIDJStudio 2>nul
)
if exist build (
    rmdir /s /q build 2>nul
)

:: Run PyInstaller with the spec file
pyinstaller ai_dj_studio.spec --clean --noconfirm

if errorlevel 1 (
    echo.
    echo  ❌  PyInstaller build failed!
    echo.
    echo  Common fixes:
    echo  1. Make sure ai_dj_complete.py is in this folder
    echo  2. Make sure assets\ folder exists with app_icon.ico
    echo  3. Run this script as Administrator
    echo.
    pause
    exit /b 1
)

echo.
echo  ✅  Application built: dist\AIDJStudio\AIDJStudio.exe
echo.

:: ── Step 7: Build installer with Inno Setup (if available) ────────
echo [7/7] Building installer package...
set INNO_PATH=
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (
    set INNO_PATH=C:\Program Files (x86)\Inno Setup 6\ISCC.exe
)
if exist "C:\Program Files\Inno Setup 6\ISCC.exe" (
    set INNO_PATH=C:\Program Files\Inno Setup 6\ISCC.exe
)

if "!INNO_PATH!"=="" (
    echo  ⚠️  Inno Setup not found — skipping installer creation
    echo.
    echo  To create the Setup.exe installer:
    echo  1. Download Inno Setup 6 from: https://jrsoftware.org/isinfo.php
    echo  2. Install it
    echo  3. Run this script again, OR run:
    echo     "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" ai_dj_installer.iss
    echo.
) else (
    mkdir installer_output 2>nul
    "!INNO_PATH!" ai_dj_installer.iss
    if errorlevel 1 (
        echo  ⚠️  Installer build failed (app still works without it)
    ) else (
        echo  ✅  Installer created: installer_output\AI_DJ_Studio_v2.0_Setup.exe
    )
)

:: ── Done ──────────────────────────────────────────────────────────
echo.
echo  ═══════════════════════════════════════════════════════════════
echo   BUILD COMPLETE!
echo  ═══════════════════════════════════════════════════════════════
echo.
echo   Application:  dist\AIDJStudio\AIDJStudio.exe
if exist installer_output\AI_DJ_Studio_v2.0_Setup.exe (
    echo   Installer:    installer_output\AI_DJ_Studio_v2.0_Setup.exe
)
echo.
echo   ⚠️  IMPORTANT: Also install FFmpeg!
echo   See FFMPEG_SETUP.txt for instructions.
echo.
echo   To run immediately: dist\AIDJStudio\AIDJStudio.exe
echo.

:: Open the dist folder
if exist dist\AIDJStudio (
    explorer dist\AIDJStudio
)

pause
