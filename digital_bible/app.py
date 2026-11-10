from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from . import APP_NAME, __version__
from .control_window import ControlWindow
from .library import Library
from .settings import Settings, assets_dir, data_dir


def _ensure_streams():
    """pythonw.exe (used by run.bat and the .exe) has no console: sys.stdout/stderr are None,
    and libraries that print (download progress bars, warnings) would crash. Send that output
    to data/biblepro.log instead."""
    if sys.stdout is not None and sys.stderr is not None:
        return
    try:
        log = open(data_dir() / "biblepro.log", "a", encoding="utf-8", buffering=1)
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
    if sys.platform.startswith("win"):
        # Lets Windows show BiblePro's own icon on the taskbar (not Python's).
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("BiblePro.App")
        except Exception:
            pass
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv if argv is None else argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setOrganizationName(APP_NAME)
    app.setStyle("Fusion")
    icon = assets_dir() / "biblepro.ico"
    if icon.exists():
        app.setWindowIcon(QIcon(str(icon)))

    ddir = data_dir()
    ddir.mkdir(parents=True, exist_ok=True)
    library = Library(ddir)
    settings = Settings(ddir / "settings.json")

    args = sys.argv if argv is None else argv
    if "--classic" not in args:
        engine = _start_qml(app, library, settings)
        if engine is not None:
            return app.exec()
        print("QML interface could not be loaded; using the classic window.", file=sys.stderr)

    win = ControlWindow(library, settings)
    win.show()
    win.restore_display()
    return app.exec()


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
    icon = assets_dir() / "biblepro.png"
    engine.rootContext().setContextProperty("iconUrl", QUrl.fromLocalFile(str(icon)).toString())
    engine.load(QUrl.fromLocalFile(str(qml_dir() / "Main.qml")))
    if not engine.rootObjects():
        return None
    # keep Python objects alive as long as the app runs
    app._biblepro = (engine, ctrl, ai)
    ctrl.showLast()
    ctrl.restore_display()
    return engine


if __name__ == "__main__":
    sys.exit(main())
