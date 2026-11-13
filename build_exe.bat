@echo off
rem Builds dist\BibleQ-AI\BibleQ-AI.exe and copies the data folder next to it.
rem Run the program from dist\BibleQ-AI\ (NOT from build\ - that folder is temporary).
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv
    ".venv\Scripts\python" -m pip install -r requirements.txt
)
".venv\Scripts\python" -m pip install pyinstaller
rem SMALL build: the large AI libraries (PyTorch, sentence-transformers, ChromaDB) are left out,
rem so AI Mode in this .exe finds verses by keyword (Gemini answers still work).
rem For meaning-based search too, use build_exe_full.bat instead.
".venv\Scripts\pyinstaller" --noconfirm --clean --windowed --name BibleQ-AI --icon "assets\bibleq-ai.ico" ^
    --add-data "assets;assets" --add-data "digital_bible\qml;digital_bible\qml" ^
    --exclude-module torch --exclude-module sentence_transformers --exclude-module transformers ^
    --exclude-module chromadb --exclude-module onnxruntime ^
    launcher.py || (pause & exit /b 1)

rem Remove PyInstaller's temporary build folder so its non-working exe isn't opened by mistake.
if exist "build" rmdir /s /q "build"
if exist "BibleQ-AI.spec" del /q "BibleQ-AI.spec"

rem Copy Bibles, backgrounds and settings next to the exe.
if exist "data" (
    echo Copying data folder...
    robocopy "data" "dist\BibleQ-AI\data" /E /XD "data\models" /NFL /NDL /NJH /NJS >nul
)

echo.
echo Done. Start the program with:
echo   %~dp0dist\BibleQ-AI\BibleQ-AI.exe
explorer "dist\BibleQ-AI"
pause
