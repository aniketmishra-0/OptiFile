@echo off
echo ==================================================
echo      Building OptiFile Desktop for Windows        
echo ==================================================

:: Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Error: Python is not installed or not in your PATH.
    echo Please install Python from https://www.python.org/
    echo IMPORTANT: Make sure to check the box "Add Python to PATH" during setup!
    echo.
    pause
    exit /b 1
)

:: 1. Install dependencies
echo [1/3] Installing and upgrading required packages...
python -m pip install --upgrade pip
python -m pip install Pillow pypdf pillow-heif pyinstaller

:: 2. Compile application using PyInstaller
echo [2/3] Compiling app.py into standalone Windows executable...
python -m PyInstaller --noconfirm --onefile --windowed --name="OptiFile" --clean app.py

:: 3. Verify output
if exist "dist\OptiFile.exe" (
    echo ==================================================
    echo 🎉 Build Successful!
    echo You can find your standalone executable at:
    echo 👉 dist\OptiFile.exe
    echo ==================================================
) else (
    echo ❌ Error: Standalone executable was not found in "dist\"
    echo Please check the error messages above.
    echo.
    pause
    exit /b 1
)
pause
