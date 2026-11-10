# BiblePro

Version 1.0.0 — by Anthony Chavez (Locale of Dallas, Texas · addpro.dallas.tx@gmail.com)

BiblePro is a desktop app for projecting Bible verses on any screen, with different translations and an AI research assistant that answers questions using the Bible text itself.

It replaces the old .NET *Digital Bible* app and reuses its library of Bibles (182 versions in many
languages) and its background images, while fixing its main problems:

- The verse display is a normal window. It can be moved, resized, made fullscreen on any screen,
  or kept borderless, so you can still switch to other apps.
- Searching and typing references happen in a separate control window, not on the screen people see.
- Choosing a version is quick: a searchable version picker, favorites (ADBTAG, KJV, MESSAGE, NKJV
  by default) and Ctrl+1…9.

## Setup (Windows)

1. Install **Python 3.10+** from python.org. During setup, tick "Add python.exe to PATH".
2. Double-click **`run.bat`**. The first time, it creates a virtual environment (`.venv`) and installs
   PySide6, which takes about a minute.
3. Click **Import Bible Version…** and choose the old Digital Bible folder (the one that contains the
   `Bibles` and `Images` folders). BiblePro converts the Bibles into its own `data\` folder; the
   original `.db3` files are never changed.

### AI Mode setup (optional)

```bat
.venv\Scripts\python -m pip install -r requirements-ai.txt
```

This installs PyTorch, sentence-transformers, ChromaDB, the language detector, Google's Gemini library
and keyring (several GB). Then see [AI Mode](#ai-mode) below.

### Standalone .exe

Run **`build_exe.bat`**. It builds `dist\BiblePro\BiblePro.exe` (no Python needed on the target PC) and
copies the `data\` folder next to it. Start the program from `dist\BiblePro\`, not from `build\`.

To keep the .exe small, it **does not include meaning-based search** (PyTorch, bge-m3, ChromaDB).
In the .exe, AI Mode finds verses by keyword and Gemini still writes the answers. For the full AI
Mode, start BiblePro with `run.bat`.

## Using it

The main window has the reference box, version picker and a live preview on the left, and four
tabs on the right: **Search**, **History**, **Appearance** and **AI Mode**. The verse itself shows in
the separate display window.

**Typing references.** Book names work in English, Tagalog and Spanish, full or abbreviated:

```
Juan 3:16    jn 3:16    John 3:16-18    Mat 5:3-6:4    1 pe 5:7    I Pedro 5:7
Awit 23      Salmos 23:1    psalm 23    Jude 3
3:17   (same book)        18   (same chapter)
```

**Keyboard (main window)**

| Key | Action |
|---|---|
| Enter | Show the typed reference |
| PgDn / Ctrl+→ / Alt+→ | Next verse |
| PgUp / Ctrl+← / Alt+← | Previous verse |
| Ctrl+K | Choose version |
| Ctrl+1…9 | Switch to favorite version 1–9 |
| Ctrl+F | Search text |
| Ctrl+L / Esc | Go to the reference box |
| Ctrl+B | Blank screen |
| Ctrl+D | Show/hide display |
| F11 | Display fullscreen on/off |

**Keyboard (display window):** → ↓ Space for next, ← ↑ for previous, F11/F/double-click for fullscreen,
Esc to return to a window, B to blank. If you start typing on the display, the main window comes up
with the reference box ready. Right-click the display to choose a screen, always-on-top or
borderless (on by default).

**Search** looks in the selected version. Every word must appear (so `love` also finds `loved`), and
accents don't matter. Put an exact phrase in "quotes". Verses that contain your words as a phrase are
listed first.

**Appearance** sets the font, colors, background image or color, text size, margins and whether the
reference and version name show (top-left of the display).

The previous (classic) window is still available:

```bat
.venv\Scripts\python -m digital_bible --classic
```

## AI Mode

AI Mode answers questions about the Bible in any language, using only the Bible versions you choose
(Ang Dating Biblia and King James Version by default).

How an answer is made:

1. **Find passages (on this computer).** BiblePro combines exact references (e.g. "Romans 8:28"),
   keyword search, and meaning-based search with the **BAAI/bge-m3** model, which also matches across
   languages (an English question can find Tagalog verses).
2. **Write the answer (Google Gemini).** Only your question and the passages found are sent to Gemini.
   It must answer in the language you asked in and cite only those passages. Any citation that
   doesn't match a found passage is removed, so BiblePro never shows a reference it didn't retrieve.
3. **Check it.** Citations in the answer are links: click one to show that verse on the display.
   **Compare** shows the same verse in every installed translation.

Without an API key, without internet, or when the free quota is used up, AI Mode still answers with
the passages it found.

**First-time setup**

1. Install the AI components (see [Setup](#ai-mode-setup-optional)).
2. **AI Mode → Settings → Embedding model:** click **Download** next to BGE-M3 (about 2.3 GB, once).
3. **Build Index.** This embeds every verse of the selected versions (about 45 minutes per version).
   It can be cancelled and continues where it left off. Later, **Refresh Index** only processes
   Bibles that are new or changed.
4. Get a free Gemini API key at [aistudio.google.com](https://aistudio.google.com).
5. In **AI answers — Google Gemini**, click **Unlock to edit**, paste the key, click **Save**, then
   **Lock**. The section stays locked so the key and model can't be changed or removed by accident.
6. Click **Test Connection**. If the default model (`gemini-3.8-flash`) isn't available to your key,
   click **Scan Available Models** and choose one.

**Chat window.** Click **Pop out ⧉** to open the chat in its own window, the same size as BiblePro and
right beside it. It follows the main window when you move or resize it. **Dock back** returns it to
the AI Mode tab.

**Which Bibles are indexed.** *Bibles used by AI Mode* lists only the checked versions. Type a name or
language in the box, or click **Show all**, to add another one, then click **Refresh Index**.

**Your API key** is stored in Windows Credential Manager (service "BiblePro"), never in BiblePro's
files or logs.

**Command line** (useful for long indexing runs):

```bat
.venv\Scripts\python -m digital_bible.ai.cli status
.venv\Scripts\python -m digital_bible.ai.cli build
.venv\Scripts\python -m digital_bible.ai.cli search "What does the Bible say about forgiveness?"
.venv\Scripts\python -m digital_bible.ai.cli compare "John 3:16"
```

## The data folder

Everything BiblePro creates lives in `data\`, which is **not in git** (some translations, such as NIV
and ESV, are copyrighted):

```
data/
  catalog.sqlite     list of installed versions
  bibles/            converted Bibles (one .sqlite per version)
  backgrounds/       background images
  index/             AI Mode keyword index + ChromaDB vectors + indexing log
  models/            downloaded embedding models (bge-m3 ≈ 2.3 GB)
  settings.json      your settings (favorites, appearance, window positions, AI options)
  biblepro.log       error output when started with run.bat
```

**Moving to another PC.** Clone the project, run `run.bat` once, install `requirements-ai.txt`, and copy
the whole `data\` folder from the old PC (close BiblePro first). The index and model come with it, so
nothing needs to be imported, downloaded or embedded again. Copying is safe even if file dates change:
BiblePro compares file contents, not dates. The Gemini API key is not in `data\`, so enter it again on
the new PC. Window positions from a different monitor setup are moved back onto the screen
automatically.

## Project layout

```
digital_bible/
  app.py             starts the app (new interface, or --classic)
  importer.py        decrypts + converts the old Bibles/*.db3 into data/
  library.py         versions, verses, navigation, search
  reference.py       reference parser ("jn 3:16" -> John 3:16)
  canvas.py          draws a slide (shared by the display and the preview)
  display_window.py  the audience window
  control_window.py  the classic operator window
  version_picker.py  version popup + favorites bar (classic window)
  settings.py        data/settings.json
  qml/               the new interface (Main.qml, pages/, components/)
  qml_ui/            Python side of the new interface (controller.py, ai_controller.py)
  ai/
    sources.py       reads the Bible databases for indexing
    keyword_index.py SQLite FTS5 keyword index
    embeddings.py    bge-m3 / e5 embedding models (download + encode)
    vector_store.py  ChromaDB vector storage
    indexer.py       build / refresh / cancel / resume the index
    retriever.py     hybrid search (references + keywords + meaning)
    language.py      detects the question's language
    generator.py     Gemini client, grounded prompt, citation checking
    cli.py           command-line tool
assets/              app icon (biblepro.ico / .png / .svg)
tests/               pytest tests (most need an imported data/ folder)
run.bat              start BiblePro (creates .venv the first time)
build_exe.bat        build dist\BiblePro\BiblePro.exe
requirements.txt     core: PySide6
requirements-ai.txt  AI Mode packages
```

Run the tests with:

```bat
.venv\Scripts\python -m pip install pytest
.venv\Scripts\python -m pytest tests
```
