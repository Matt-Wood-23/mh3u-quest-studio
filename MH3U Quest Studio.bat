@echo off
REM MH3U Quest Studio launcher: needs Python 3.10+ with tkinter
cd /d "%~dp0"

py -3 -c "import sys, tkinter; sys.exit(sys.version_info < (3, 10))" >nul 2>nul
if not errorlevel 1 (
    start "" pyw -3 quest_studio.py
    exit /b 0
)

python -c "import sys, tkinter; sys.exit(sys.version_info < (3, 10))" >nul 2>nul
if not errorlevel 1 (
    python quest_studio.py
    if errorlevel 1 pause
    exit /b 0
)

echo MH3U Quest Studio needs Python 3.10 or newer:
echo   https://www.python.org/downloads/
echo Tick "Add python.exe to PATH" in the installer, then run this again.
pause
