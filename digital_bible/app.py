from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from . import APP_NAME, __version__
from .library import Library
from .settings import Settings, assets_dir, data_dir


def _ensure_streams():
    """pythonw.exe (used by run.bat and the .exe) has no console: sys.stdout/stderr are None,
    and libraries that print (download progress bars, warnings) would crash. Send that output
    to data/bibleq-ai.log instead."""
    if sys.stdout is not None and sys.stderr is not None:
        return
    try:
        log = open(data_dir() / "bibleq-ai.log", "a", encoding="utf-8", buffering=1)
    except OSError:
        import os
        log = open(os.devnull, "w", encoding="utf-8")
    if sys.stdout is None:
        sys.stdout = log
    if sys.stderr is None:
        sys.stderr = log


def main(argv=None) -> int:
    data_dir().mkdir(parents=True, exist_ok=True)
    _ensure_streams()
    if "--selftest" in (sys.argv if argv is None else argv):    # check the AI parts of a built .exe
        from .selftest import run
        return run()
    if sys.platform.startswith("win"):
        # Lets Windows show BibleQ-AI's own icon on the taskbar (not Python's).
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("BibleQAI.App")
        except Exception:
            pass
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv if argv is None else argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setOrganizationName(APP_NAME)
    app.setStyle("Fusion")
    icon = assets_dir() / "bibleq-ai.ico"
    if icon.exists():
        app.setWindowIcon(QIcon(str(icon)))

    ddir = data_dir()
    ddir.mkdir(parents=True, exist_ok=True)
    library = Library(ddir)
    settings = Settings(ddir / "settings.json")

    engine = _start_qml(app, library, settings)
    if engine is None:
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.critical(None, APP_NAME, "BibleQ-AI's window could not be loaded.\n"
                             "Details are in data\\bibleq-ai.log. Reinstalling PySide6 usually fixes this:\n"
                             ".venv\\Scripts\\python -m pip install --force-reinstall PySide6")
        return 1
    return app.exec()


TITLE_BAR = "#F6F9FF"        # same light blue as the top of the sidebar
TITLE_TEXT = "#1B2540"
TITLE_BORDER = "#E1E7F2"


def tint_title_bar(window) -> bool:
    """Color a window's title bar (Windows 11; other systems keep their default)."""
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        from ctypes import wintypes

        def colorref(hex_color: str) -> int:
            r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
            return r | (g << 8) | (b << 16)

        hwnd = wintypes.HWND(int(window.winId()))
        dwm = ctypes.windll.dwmapi
        ok = True
        for attr, color in ((35, TITLE_BAR), (36, TITLE_TEXT), (34, TITLE_BORDER)):   # caption, text, border
            val = wintypes.DWORD(colorref(color))
            ok &= dwm.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(val), ctypes.sizeof(val)) == 0
        return ok
    except Exception:
        return False


def qml_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", ".")) / "digital_bible" / "qml"
    return Path(__file__).resolve().parent / "qml"


def _start_qml(app, library, settings):
    """Load the Qt Quick interface. Returns the engine, or None if loading failed."""
    try:
        from PySide6.QtCore import QUrl
        from PySide6.QtQml import QQmlApplicationEngine

        from .qml_ui import preview_item  # noqa: F401  (registers SlidePreview for QML)
        from .qml_ui.ai_controller import AiController
        from .qml_ui.controller import Controller
    except Exception as exc:                                   # missing QtQuick modules etc.
        print(f"QML import failed: {exc}", file=sys.stderr)
        return None

    ctrl = Controller(library, settings)
    ai = AiController(library, settings, ctrl)
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("ctrl", ctrl)
    engine.rootContext().setContextProperty("aiCtrl", ai)
    icon = assets_dir() / "bibleq-ai.png"
    engine.rootContext().setContextProperty("iconUrl", QUrl.fromLocalFile(str(icon)).toString())
    engine.load(QUrl.fromLocalFile(str(qml_dir() / "Main.qml")))
    if not engine.rootObjects():
        return None
    # keep Python objects alive as long as the app runs
    app._biblepro = (engine, ctrl, ai)
    # title bars in the sidebar's light blue (Windows 11)
    root = engine.rootObjects()[0]
    tint_title_bar(root)
    from PySide6.QtGui import QWindow
    for w in root.findChildren(QWindow):            # the pop-out chat window
        w.visibleChanged.connect(lambda vis, w=w: vis and tint_title_bar(w))
    ctrl.showLast()
    ctrl.restore_display()
    return engine


if __name__ == "__main__":
    sys.exit(main())
