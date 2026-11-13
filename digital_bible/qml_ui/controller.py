"""Main controller: verses, versions, display window, search, history and appearance, exposed to QML."""
from __future__ import annotations

import shutil
from pathlib import Path

from PySide6.QtCore import Property, QObject, QThread, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QColor, QFontDatabase, QGuiApplication
from PySide6.QtWidgets import QColorDialog, QFileDialog

from .. import APP_NAME, AUTHOR, AUTHOR_EMAIL, AUTHOR_LOCALE, DESCRIPTION, __version__
from ..canvas import Renderer, Slide
from ..display_window import DisplayWindow
from ..importer import import_files
from ..library import NT_BOOKS, OT_BOOKS, Library, split_key
from ..reference import BookResolver, ParseError, Ref, ref_from_key
from ..settings import Settings

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
HISTORY_MAX = 300


class ImportWorker(QObject):
    """Converts Bible files (.sqlite / .db3) in a background thread."""
    progress = Signal(int, int, str)
    finished = Signal(dict)
    failed = Signal(str)

    def __init__(self, src, dst: Path):
        super().__init__()
        self.src, self.dst = src, dst
        self.cancel = False

    @Slot()
    def run(self):
        try:
            summary = import_files(self.src, self.dst, progress=self.progress.emit, cancelled=lambda: self.cancel)
            self.finished.emit(summary)
        except Exception as exc:
            self.failed.emit(str(exc))


def _title(name: str) -> str:
    return name.title() if name.isupper() else name


class Controller(QObject):
    # notify signals
    slideChanged = Signal()
    referenceChanged = Signal()
    messageChanged = Signal()
    versionChanged = Signal()
    favoritesChanged = Signal()
    searchChanged = Signal()
    historyChanged = Signal()
    styleChanged = Signal()
    backgroundsChanged = Signal()
    displayChanged = Signal()
    libraryChanged = Signal()
    importChanged = Signal()
    # events for QML
    focusReference = Signal(str)          # text typed on the display window
    toast = Signal(str)

    def __init__(self, library: Library, settings: Settings):
        super().__init__()
        self.library, self.settings = library, settings
        self.settings["history"] = []          # each session starts with an empty history
        self.renderer = Renderer(library.data_dir / "backgrounds")
        self.resolver = BookResolver(library)
        self.version = settings["version"] if settings["version"] in library.by_code else (
            library.versions[0].code if library.versions else "")
        self.current_ref: Ref | None = None
        self.current_range: tuple[int, int] | None = None
        self.slide = Slide()
        self._blank = False
        self._reference_text = ""
        self._message = ""
        self._search_results: list = []
        self._search_info = ""
        self._import = {"running": False, "value": 0, "total": 0, "text": ""}
        self._thread = self._worker = None

        self._save_timer = QTimer(self, singleShot=True, interval=600)
        self._save_timer.timeout.connect(self.settings.save)

        self.display = DisplayWindow(self.renderer, self.settings.style)
        self.display.setWindowIcon(QGuiApplication.windowIcon())
        self.display.next_requested.connect(self.next)
        self.display.prev_requested.connect(self.prev)
        self.display.blank_toggled.connect(self.toggleBlank)
        self.display.typed.connect(self.focusReference.emit)
        self.display.focus_controls.connect(lambda: self.focusReference.emit(""))
        self.display.reset_size_requested.connect(self.resetDisplaySize)
        self.display.state_changed.connect(self._display_state_changed)
        d = settings.display
        if d["geometry"]:
            self.display.setGeometry(*d["geometry"])
        self.display.set_on_top(bool(d["on_top"]))

    # ================================================================ helpers
    def _save(self):
        self._save_timer.start()

    def visible_slide(self) -> Slide:
        return Slide(blank=True) if self._blank else self.slide

    def display_aspect(self) -> float:
        g = self.display.geometry()
        return (g.width() / g.height()) if self.display.isVisible() and g.height() else 16 / 9

    def _push(self):
        self.display.set_slide(self.visible_slide())
        self.slideChanged.emit()

    @staticmethod
    def _version_dict(v) -> dict:
        return {"code": v.code, "abbr": v.abbr, "name": _title(v.name), "language": v.language,
                "coverage": v.coverage, "info": v.info, "verses": v.verse_count}

    # ================================================================ properties
    def _get_ref_text(self):
        return self._reference_text
    referenceText = Property(str, _get_ref_text, notify=referenceChanged)

    def _get_message(self):
        return self._message
    message = Property(str, _get_message, notify=messageChanged)

    def _get_current_version(self):
        v = self.library.by_code.get(self.version)
        return self._version_dict(v) if v else {}
    currentVersion = Property("QVariantMap", _get_current_version, notify=versionChanged)

    def _get_versions(self):
        return [self._version_dict(v) for v in self.library.versions]
    versions = Property("QVariantList", _get_versions, notify=libraryChanged)

    def _get_languages(self):
        return self.library.languages()
    languages = Property("QVariantList", _get_languages, notify=libraryChanged)

    def _get_favorites(self):
        return [self._version_dict(self.library.by_code[c]) for c in self.settings["favorites"]
                if c in self.library.by_code]
    favorites = Property("QVariantList", _get_favorites, notify=favoritesChanged)

    def _get_favorite_codes(self):
        return list(self.settings["favorites"])
    favoriteCodes = Property("QVariantList", _get_favorite_codes, notify=favoritesChanged)

    def _get_has_library(self):
        return bool(self.library.versions)
    hasLibrary = Property(bool, _get_has_library, notify=libraryChanged)

    def _get_slide_info(self):
        return {"reference": self.slide.reference, "version": self.slide.version,
                "text": self.slide.text or self.slide.note}
    slideInfo = Property("QVariantMap", _get_slide_info, notify=slideChanged)

    def _get_blank(self):
        return self._blank
    blank = Property(bool, _get_blank, notify=slideChanged)

    def _get_results(self):
        return self._search_results
    searchResults = Property("QVariantList", _get_results, notify=searchChanged)

    def _get_search_info(self):
        return self._search_info
    searchInfo = Property(str, _get_search_info, notify=searchChanged)

    def _get_history(self):
        out = []
        for i, e in enumerate(self.settings["history"]):
            v = self.library.by_code.get(e["code"])
            if v:
                try:
                    text = " ".join(self.library.passage(v.code, e["start"], e["end"]).text.split())
                except Exception:
                    text = ""
                out.append({"index": i, "reference": self._ref_label(v, e["start"], e["end"]),
                            "abbr": v.abbr, "code": v.code, "text": text})
        return out
    history = Property("QVariantList", _get_history, notify=historyChanged)

    def _get_style(self):
        return dict(self.settings.style)
    style = Property("QVariantMap", _get_style, notify=styleChanged)

    def _get_backgrounds(self):
        d = self.library.data_dir / "backgrounds"
        if not d.exists():
            return []
        return [{"name": p.name, "label": p.stem, "url": QUrl.fromLocalFile(str(p)).toString()}
                for p in sorted(d.iterdir()) if p.suffix.lower() in IMAGE_EXT]
    backgrounds = Property("QVariantList", _get_backgrounds, notify=backgroundsChanged)

    def _get_fonts(self):
        return QFontDatabase.families()
    fonts = Property("QVariantList", _get_fonts, constant=True)

    def _get_display(self):
        screens = []
        primary = QGuiApplication.primaryScreen()
        for i, s in enumerate(QGuiApplication.screens(), 1):
            g = s.geometry()
            screens.append({"name": s.name(), "label": f"Screen {i}: {g.width()}×{g.height()}"
                            + ("  (main)" if s == primary else "")})
        return {"visible": self.display.isVisible(), "fullscreen": self.display.isFullScreen(),
                "onTop": self.display.on_top, "screens": screens,
                "aspect": self.display_aspect()}
    displayState = Property("QVariantMap", _get_display, notify=displayChanged)

    def _get_import(self):
        return dict(self._import)
    importState = Property("QVariantMap", _get_import, notify=importChanged)

    def _get_about(self):
        return {"app": APP_NAME, "version": __version__, "author": AUTHOR, "locale": AUTHOR_LOCALE,
                "email": AUTHOR_EMAIL, "description": DESCRIPTION, "versions": len(self.library.versions)}
    about = Property("QVariantMap", _get_about, constant=True)

    # ================================================================ navigation
    @Slot(str)
    def go(self, text: str):
        if not self.library.versions:
            return
        try:
            ref = self.resolver.parse(text, self.current_ref, self.version)
        except ParseError as e:
            self._set_message(str(e))
            return
        self._set_message("")
        self._show_range(ref.start_key, ref.end_key, record=True)

    @Slot(int)
    def showKey(self, key: int):
        if key:
            self._show_range(key, key, record=True)

    @Slot(int, str)
    def showKeyIn(self, key: int, code: str):
        """Open a verse in a given translation (used by AI citations)."""
        if code in self.library.by_code and code != self.version:
            self.setVersion(code)
        self.showKey(key)

    def _show_range(self, start: int, end: int, record: bool):
        passage = self.library.passage(self.version, start, end)
        self.current_range, self.current_ref = (start, end), ref_from_key(start)
        v = passage.version
        note = ""
        if not passage.text.strip():
            note = f"{passage.reference} is not in {v.abbr}" + (f" ({v.coverage})" if v.coverage else "")
        self._blank = False
        self.slide = Slide(text=passage.text.strip(), reference=passage.reference, version=v.name, note=note)
        self._push()
        self._reference_text = passage.reference.title()
        self.referenceChanged.emit()
        self.settings["last_ref"] = passage.reference
        if record:
            self._record_history(start, end)
        self._save()

    @Slot()
    def next(self):
        if self.current_range:
            k = self.library.text(self.version).next_key(self.current_range[1])
            if k:
                self._show_range(k, k, record=False)

    @Slot()
    def prev(self):
        if self.current_range:
            k = self.library.text(self.version).prev_key(self.current_range[0])
            if k:
                self._show_range(k, k, record=False)

    @Slot()
    def showLast(self):
        """Show the last verse at startup (without adding a history entry)."""
        if not self.library.versions:
            return
        try:
            ref = self.resolver.parse(self.settings["last_ref"] or "Genesis 1:1", None, self.version)
        except ParseError:
            ref = self.resolver.parse("Genesis 1:1", None, self.version)
        self._show_range(ref.start_key, ref.end_key, record=False)

    def _set_message(self, msg):
        self._message = msg
        self.messageChanged.emit()

    # ================================================================ versions
    @Slot(str)
    def setVersion(self, code: str):
        if code not in self.library.by_code:
            return
        self.version = code
        self.settings["version"] = code
        self.versionChanged.emit()
        self.favoritesChanged.emit()
        if self.current_range:
            self._show_range(*self.current_range, record=False)
        self._save()

    @Slot(str)
    def toggleFavorite(self, code: str):
        favs = list(self.settings["favorites"])
        favs.remove(code) if code in favs else favs.append(code)
        self.settings["favorites"] = favs
        self.favoritesChanged.emit()
        self._save()

    @Slot(int)
    def favoriteN(self, n: int):
        favs = [c for c in self.settings["favorites"] if c in self.library.by_code]
        if 1 <= n <= len(favs):
            self.setVersion(favs[n - 1])

    # ================================================================ search
    @Slot(str, int)
    def search(self, query: str, scope: int):
        q = query.strip()
        self._search_results, self._search_info = [], ""
        if q and self.version:
            books = {1: OT_BOOKS, 2: NT_BOOKS}.get(scope)
            if scope == 3 and self.current_ref:
                books = [self.current_ref.book]
            vt = self.library.text(self.version)
            keys, total = vt.search(q, books=books, limit=1000)
            v = vt.version
            for k in keys:
                b, c, vs = split_key(k)
                self._search_results.append({"key": k, "reference": f"{v.book_name(b)} {c}:{vs}",
                                             "text": vt.get(k)})
            shown = f" — showing first {len(keys)}" if total > len(keys) else ""
            self._search_info = f"{total:,} verses in {v.abbr} contain “{q}”{shown}"
        self.searchChanged.emit()

    # ================================================================ history
    @staticmethod
    def _ref_label(v, start, end):
        b, c, vs = split_key(start)
        _, c2, v2 = split_key(end)
        s = f"{v.book_name(b)} {c}:{vs}"
        if end != start:
            s += f"-{v2}" if c2 == c else f"-{c2}:{v2}"
        return s

    def _record_history(self, start, end):
        h = [e for e in self.settings["history"]
             if not (e["start"] == start and e["end"] == end and e["code"] == self.version)]
        h.insert(0, {"code": self.version, "start": start, "end": end})
        self.settings["history"] = h[:HISTORY_MAX]
        self.historyChanged.emit()

    @Slot(int)
    def openHistory(self, index: int):
        h = self.settings["history"]
        if 0 <= index < len(h):
            e = h[index]
            if e["code"] != self.version:
                self.setVersion(e["code"])
            self._show_range(e["start"], e["end"], record=False)

    @Slot()
    def clearHistory(self):
        self.settings["history"] = []
        self.historyChanged.emit()
        self._save()

    # ================================================================ appearance
    @Slot(str, "QVariant")
    def setStyleValue(self, key: str, value):
        if isinstance(value, float) and value.is_integer() and key in ("max_size", "margin", "dim"):
            value = int(value)
        self.settings.style[key] = value
        self.display.set_style(self.settings.style)
        self.styleChanged.emit()
        self._push()
        self._save()

    @Slot(str)
    def pickColor(self, key: str):
        c = QColorDialog.getColor(QColor(self.settings.style.get(key, "#ffffff")), None, "Choose color")
        if c.isValid():
            self.setStyleValue(key, c.name())

    @Slot()
    def addBackground(self):
        path, _ = QFileDialog.getOpenFileName(None, "Choose background image", str(Path.home()),
                                              "Images (*.jpg *.jpeg *.png *.bmp *.webp)")
        if not path:
            return
        d = self.library.data_dir / "backgrounds"
        d.mkdir(parents=True, exist_ok=True)
        target = d / Path(path).name
        if Path(path).resolve() != target.resolve():
            shutil.copy2(path, target)
        self.backgroundsChanged.emit()
        self.setStyleValue("bg_mode", "image")
        self.setStyleValue("background", target.name)

    # ================================================================ display window
    @Slot(bool)
    def setDisplayVisible(self, on: bool):
        if on:
            self.display.show()
            self.display.raise_()
        else:
            self.display.hide()
        self.settings.display["visible"] = on
        self._push()
        self.displayChanged.emit()
        self._save()

    @Slot(str)
    def fullscreenOn(self, screen_name: str):
        self.display.show()
        self.display.move_to_screen(screen_name)
        self.settings.display["screen"] = screen_name
        self.displayChanged.emit()

    def background_size(self) -> tuple[int, int]:
        """Pixel size of the background image in use (1920×1080 when there is none)."""
        st = self.settings.style
        if st.get("bg_mode", "image") == "image":
            path = self.renderer.background_path(st)
            if path is not None and path.exists():
                from PySide6.QtGui import QImageReader
                sz = QImageReader(str(path)).size()      # reads the header only
                if sz.isValid() and sz.width() > 0 and sz.height() > 0:
                    return sz.width(), sz.height()
        return 1920, 1080

    @Slot()
    def resetDisplaySize(self):
        """Verse window back to a quarter of the screen, in the background image's shape."""
        self.display.show()
        msg = self.display.reset_size(*self.background_size())
        self.settings.display["visible"] = True
        self.displayChanged.emit()
        self.toast.emit(msg)

    @Slot()
    def leaveFullscreen(self):
        self.display.leave_fullscreen()
        self.displayChanged.emit()

    @Slot()
    def toggleFullscreen(self):
        self.display.show()
        self.display.toggle_fullscreen()
        self.displayChanged.emit()

    @Slot(bool)
    def setOnTop(self, on: bool):
        self.display.set_on_top(on)
        self.displayChanged.emit()

    @Slot()
    def toggleBlank(self):
        self._blank = not self._blank
        self._push()

    def _display_state_changed(self):
        d = self.settings.display
        d["fullscreen"] = self.display.isFullScreen()
        d["on_top"] = self.display.on_top
        g = self.display.windowed_geometry()
        d["geometry"] = [g.x(), g.y(), g.width(), g.height()]
        if self.display.isFullScreen():
            d["screen"] = self.display.current_screen_name()
        self.displayChanged.emit()
        self.slideChanged.emit()
        self._save()

    def restore_display(self):
        d = self.settings.display
        names = [s.name() for s in QGuiApplication.screens()]
        if d["visible"]:
            self.setDisplayVisible(True)
            if d["fullscreen"] and d.get("screen") in names:
                self.display.move_to_screen(d["screen"])
            elif d["fullscreen"] and len(names) > 1:
                self.display.move_to_screen(names[1])

    # ================================================================ window state
    @Slot(result="QVariantList")
    def windowGeometry(self):
        """Saved main-window position, or [] if it would be off every screen
        (e.g. settings copied from a PC with a different monitor layout)."""
        g = list(self.settings["control_geometry"] or [])
        if len(g) != 4:
            return []
        from PySide6.QtCore import QRect
        r = QRect(*g)
        for scr in QGuiApplication.screens():
            vis = scr.availableGeometry().intersected(r)
            if vis.width() >= 200 and vis.height() >= 150:
                return g
        return []

    @Slot(int, int, int, int)
    def saveWindowGeometry(self, x, y, w, h):
        self.settings["control_geometry"] = [x, y, w, h]
        self.settings.save()

    @Slot()
    def shutdown(self):
        if self._thread is not None and self._thread.isRunning():
            self._worker.cancel = True
            self._thread.quit()
            self._thread.wait(10000)
        self.settings["history"] = []          # history is only for this session
        self.settings.save()
        self.display.close()

    # ================================================================ import / files
    @Slot()
    def importVersionFiles(self):
        """Settings › Import Bible version: add one or more .sqlite / .db3 Bible files."""
        if self._import.get("running"):
            return
        start = self.settings.data.get("import_dir") or str(Path.home() / "Documents")
        files, _ = QFileDialog.getOpenFileNames(
            None, "Import Bible Version", start, "Bible versions (*.sqlite *.db3);;All files (*)")
        if not files:
            return
        self.settings["import_dir"] = str(Path(files[0]).parent)
        self._save()
        self._start_import(ImportWorker([Path(f) for f in files], self.library.data_dir))

    def _start_import(self, worker: ImportWorker):
        self._import = {"running": True, "value": 0, "total": 0, "text": "Starting import…"}
        self.importChanged.emit()
        self._thread = QThread(self)
        self._worker = worker
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._import_progress)       # QObject slots -> UI thread
        self._worker.finished.connect(self._import_done)
        self._worker.failed.connect(self._import_failed)
        self._thread.start()

    @Slot()
    def cancelImport(self):
        if self._worker is not None:
            self._worker.cancel = True

    @Slot(int, int, str)
    def _import_progress(self, i, total, msg):
        self._import = {"running": True, "value": i, "total": total, "text": f"{msg} ({i} of {total})"}
        self.importChanged.emit()

    def _import_end(self, text):
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait(5000)
        self._import = {"running": False, "value": 0, "total": 0, "text": text}
        self.importChanged.emit()

    @Slot(dict)
    def _import_done(self, summary):
        self.library.reload()
        self.resolver = BookResolver(self.library)
        if self.version not in self.library.by_code and self.library.versions:
            self.version = "001" if "001" in self.library.by_code else self.library.versions[0].code
        n = len(summary["imported"])
        text = f"Imported {n} Bible version{'' if n == 1 else 's'}"
        text += f" and {summary['images']} background images." if summary.get("images") else "."
        if summary.get("skipped"):
            text += f" {len(summary['skipped'])} already in the library."
        if summary["failed"]:
            text += " Not imported: " + "; ".join(f"{name} ({why})" for name, why in summary["failed"][:3])
        self._import_end(text)
        for sig in (self.libraryChanged, self.versionChanged, self.favoritesChanged,
                    self.backgroundsChanged, self.historyChanged):
            sig.emit()
        self.showLast()

    @Slot(str)
    def _import_failed(self, msg):
        self._import_end(f"Import failed: {msg}")
