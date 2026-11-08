# BiblePro

Version 1.0.0 — by Anthony Chavez (Locale of Dallas, Texas · addpro.dallas.tx@gmail.com)

BiblePro is an app for showing Bible verses on a screen or projector. It reuses the old .NET *Digital Bible* apps whole library of Bibles (182 versions in many languages) and its background images.


## Setup (Windows)

1. Install **Python 3.10+** from python.org. During setup, tick "Add python.exe to PATH".
2. Double-click **`run.bat`**. The first time, it creates a virtual environment and installs PySide6, which takes about a minute.

To build a standalone `.exe` (no Python needed on the target PC), run `build_exe.bat`, then copy the
`data\` folder next to `dist\BiblePro\BiblePro.exe` (build_exe.bat does this for you).

## Using it

**Typing references.** Book names work in English, Tagalog and Spanish, full or abbreviated:

```
Juan 3:16    jn 3:16    John 3:16-18    Mat 5:3-6:4    1 pe 5:7    I Pedro 5:7
Awit 23      Salmos 23:1    psalm 23    Jude 3
3:17   (same book)        18   (same chapter)
```

**Keyboard (control window)**

| Key | Action |
|---|---|
| Enter | Show the typed reference |
| PgDn / Ctrl+→ | Next verse |
| PgUp / Ctrl+← | Previous verse |
| Ctrl+K | Choose version |
| Ctrl+1…9 | Switch to favorite version 1–9 |
| Ctrl+F | Search text |
| Ctrl+B | Blank screen |
| Ctrl+D | Show/hide display |
| F11 | Display fullscreen on/off |

**Keyboard (display window):** → ↓ Space for next, ← ↑ for previous, F11/F/double-click for fullscreen,
Esc to return to a window, B to blank. If you start typing on the display, the
control window comes up with the reference box ready. Right-click the display to
choose a screen, always-on-top or borderless.

**Search** looks in the selected version. Every word must appear (so `love` also finds
`loved`), and accents don't matter. Put an exact phrase in "quotes". Verses that contain your
words as a phrase are listed first.

## Project layout

```
digital_bible/
  importer.py        decrypts + converts the old Bibles/*.db3 into data/
  library.py         versions, verses, navigation, search
  reference.py       reference parser ("jn 3:16" -> John 3:16)
  canvas.py          draws a slide (shared by the display and the preview)
  display_window.py  the audience window
  control_window.py  the operator window
  version_picker.py  version popup + favorites bar
  settings.py        data/settings.json
data/                created by the import (not in git): catalog.sqlite, bibles/, backgrounds/, settings.json
tests/               pytest tests for the parser/library (need an imported data/ folder)
```
