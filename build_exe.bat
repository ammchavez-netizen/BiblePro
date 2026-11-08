@echo off
rem Builds dist\BiblePro\BiblePro.exe and copies the data folder next to it.
rem Run the program from dist\BiblePro\ (NOT from build\ - that folder is temporary).
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv
    ".venv\Scripts\python" -m pip install -r requirements.txt
)
".venv\Scripts\python" -m pip install pyinstaller
".venv\Scripts\pyinstaller" --noconfirm --clean --windowed --name BiblePro --icon "assets\biblepro.ico" --add-data "assets;assets" launcher.py || (pause & exit /b 1)

rem Remove PyInstaller's temporary build folder so its non-working exe isn't opened by mistake.
if exist "build" rmdir /s /q "build"
if exist "BiblePro.spec" del /q "BiblePro.spec"

rem Copy Bibles, backgrounds and settings next to the exe.
if exist "data" (
    echo Copying data folder...
    robocopy "data" "dist\BiblePro\data" /E /NFL /NDL /NJH /NJS >nul
)

echo.
echo Done. Start the program with:
echo   %~dp0dist\BiblePro\BiblePro.exe
explorer "dist\BiblePro"
pause
