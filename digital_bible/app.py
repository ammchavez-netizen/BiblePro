from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from . import APP_NAME, __version__
from .control_window import ControlWindow
from .library import Library
from .settings import Settings, assets_dir, data_dir


def main(argv=None) -> int:
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
    win = ControlWindow(library, settings)
    win.show()
    win.restore_display()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
