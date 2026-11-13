@echo off
rem ===========================================================================
rem  Builds the FULL BibleQ-AI: dist-full\BibleQ-AI\BibleQ-AI.exe
rem  including AI Mode's meaning-based search (PyTorch, sentence-transformers,
rem  the bge-m3 model, ChromaDB) and Gemini answers. No Python needed on the
rem  target PC. The folder is large (about 4-6 GB with the bge-m3 model).
rem
rem  For the small build without meaning-based search, use build_exe.bat.
rem  Run the program from dist-full\BibleQ-AI\ (NOT from build-full\).
rem ===========================================================================
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Creating the Python environment...
    python -m venv .venv || (echo Python 3.10+ is required: https://www.python.org/downloads/ & pause & exit /b 1)
)
echo Installing / checking packages (the AI packages are large; the first time takes a while)...
".venv\Scripts\python" -m pip install --upgrade pip >nul
".venv\Scripts\python" -m pip install -r requirements.txt -r requirements-ai.txt pyinstaller || (pause & exit /b 1)

echo.
echo Building BibleQ-AI.exe with AI meaning-based search (this takes several minutes)...
rem  --collect-*      : packages that load code or data files by name at run time
rem  --copy-metadata  : packages that check other packages' versions when they start
rem  keyring backends : so the Gemini API key is read from Windows Credential Manager
".venv\Scripts\pyinstaller" --noconfirm --clean --windowed --name BibleQ-AI --icon "%~dp0assets\bibleq-ai.ico" ^
    --distpath dist-full --workpath build-full --specpath build-full ^
    --add-data "%~dp0assets;assets" --add-data "%~dp0digital_bible\qml;digital_bible\qml" ^
    --collect-all chromadb --collect-all chromadb_rust_bindings ^
    --collect-all lingua ^
    --collect-all sentence_transformers ^
    --collect-submodules transformers.models.xlm_roberta --collect-submodules transformers.models.bert ^
    --collect-data transformers --collect-data tokenizers ^
    --hidden-import keyring.backends.Windows --hidden-import win32ctypes.core ^
    --collect-submodules google.genai ^
    --recursive-copy-metadata transformers --recursive-copy-metadata sentence-transformers ^
    --copy-metadata torch --copy-metadata tokenizers --copy-metadata huggingface-hub ^
    --copy-metadata safetensors --copy-metadata chromadb --copy-metadata keyring ^
    --copy-metadata google-genai --copy-metadata lingua-language-detector ^
    --exclude-module tkinter --exclude-module matplotlib --exclude-module IPython ^
    --exclude-module torch.utils.tensorboard --exclude-module pytest ^
    launcher.py || (pause & exit /b 1)

rem PyInstaller's temporary folder (its exe there does not work).
if exist "build-full" rmdir /s /q "build-full"

rem Copy everything in data\ next to the exe: Bibles, backgrounds, settings,
rem the AI index and the bge-m3 model (data\models), so nothing needs to be
rem indexed or downloaded on the new PC.
rem (No brackets inside this block's echo text: a ")" would end the block early and stop the script.)
if exist "data" (
    echo Copying the data folder - Bibles, backgrounds, AI model and index...
    robocopy "data" "dist-full\BibleQ-AI\data" /E /XF "bibleq-ai.log" "biblepro.log" "selftest.txt" /NFL /NDL /NJH /NJS >nul
    if errorlevel 8 echo WARNING: some files in data could not be copied. Copy the data folder by hand.
) else (
    echo WARNING: there is no data folder here, so the exe will start without Bibles.
)

echo.
echo Checking that AI Mode works inside the new BibleQ-AI.exe...
start "" /wait "dist-full\BibleQ-AI\BibleQ-AI.exe" --selftest
if exist "dist-full\BibleQ-AI\data\selftest.txt" (
    type "dist-full\BibleQ-AI\data\selftest.txt"
) else (
    echo The self-test did not run. See dist-full\BibleQ-AI\data\bibleq-ai.log
)

echo.
echo Done. Start the program with:
echo   %~dp0dist-full\BibleQ-AI\BibleQ-AI.exe
echo Copy the whole dist-full\BibleQ-AI folder to use it on another PC.
explorer "dist-full\BibleQ-AI"
pause
