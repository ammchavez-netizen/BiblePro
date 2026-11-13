"""The QML interface must load with zero QML errors, and its core actions must work.

Run:  python -m pytest tests   (needs an imported data/ folder)
"""
import os
import shutil
from pathlib import Path

import pytest

DATA = Path(__file__).resolve().parent.parent / "data"
pytestmark = pytest.mark.skipif(not (DATA / "catalog.sqlite").exists(), reason="run the import first")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")


@pytest.fixture(scope="module")
def qml_app(tmp_path_factory):
    from PySide6.QtCore import qInstallMessageHandler
    from PySide6.QtWidgets import QApplication

    import digital_bible.app as appmod
    from digital_bible.library import Library
    from digital_bible.settings import Settings

    d = tmp_path_factory.mktemp("qml")
    (d / "bibles").mkdir()
    for code in ("001", "002"):
        shutil.copy(DATA / "bibles" / f"{code}.sqlite", d / "bibles")
    shutil.copy(DATA / "catalog.sqlite", d)
    messages = []
    qInstallMessageHandler(lambda mode, ctx, msg: messages.append(msg))
    app = QApplication.instance() or QApplication([])
    lib = Library(d)
    engine = appmod._start_qml(app, lib, Settings(d / "settings.json"))
    for _ in range(20):
        app.processEvents()
    yield app, engine, messages
    app._biblepro[1].shutdown()


def _qml_errors(messages):
    return [m for m in messages if ".qml" in m]


def test_loads_without_qml_errors(qml_app):
    app, engine, messages = qml_app
    assert engine is not None and engine.rootObjects()
    assert _qml_errors(messages) == []


def test_navigation_and_versions(qml_app):
    app, _engine, messages = qml_app
    ctrl = app._biblepro[1]
    ctrl.go("Juan 3:16")
    assert ctrl.slideInfo["reference"] == "JUAN 3:16"
    ctrl.next()
    assert ctrl.slideInfo["reference"] == "JUAN 3:17"
    ctrl.setVersion("002")
    assert ctrl.currentVersion["abbr"] == "KJV" and ctrl.slideInfo["text"].startswith("For God sent not")
    ctrl.search("love one another", 0)
    assert ctrl.searchResults and "love one another" in ctrl.searchInfo
    for _ in range(10):
        app.processEvents()
    assert _qml_errors(messages) == []


def test_ai_tab_answers_offline(qml_app):
    import time
    app, _engine, messages = qml_app
    ai = app._biblepro[2]
    ai.ask("Ipaliwanag ang Juan 3:16")
    t0 = time.time()
    while ai.busy and time.time() - t0 < 60:
        app.processEvents()
        time.sleep(0.02)
    answer = ai.messages[-1]
    assert answer["language"] == "Tagalog"
    assert answer["sources"][0]["reference"] == "JUAN 3:16"
    assert _qml_errors(messages) == []


def test_ai_tab_settings_and_popout_load_cleanly(qml_app):
    from PySide6.QtCore import QObject
    app, engine, messages = qml_app
    ai = app._biblepro[2]
    win = engine.rootObjects()[0]
    win.findChild(QObject, "tabs").setProperty("currentIndex", 2)
    for _ in range(20):
        app.processEvents()
    assert win.findChild(QObject, "aiPage") is not None          # AI Mode tab: chat only
    win.setProperty("settingsPage", "ai")                          # Settings › AI Mode Settings
    win.setProperty("settingsOpen", True)
    for _ in range(20):
        app.processEvents()
    assert win.findChild(QObject, "aiSettingsPage") is not None
    win.findChild(QObject, "geminiSection").setProperty("unlocked", True)
    for _ in range(20):
        app.processEvents()
    ai.setChatPoppedOut(True)
    for _ in range(20):
        app.processEvents()
    chat = [w for w in app.topLevelWindows() if w.title() == "BibleQ-AI — AI Chat"]
    assert chat and chat[0].isVisible()
    assert (chat[0].width(), chat[0].height()) == (win.width(), win.height())
    ai.setChatPoppedOut(False)
    for _ in range(10):
        app.processEvents()
    assert not chat[0].isVisible()
    win.setProperty("settingsPage", "appearance")
    win.setProperty("settingsOpen", False)
    assert _qml_errors(messages) == []
