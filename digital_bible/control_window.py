"""Operator window: type a verse, pick a version, search, history, display options."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QRectF, QSize, QStringListModel, Qt, QThread, QTimer, Signal, Slot
from PySide6.QtGui import QAction, QColor, QGuiApplication, QIcon, QKeySequence, QPainter, QPixmap, QShortcut
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QCheckBox, QColorDialog, QComboBox,
                               QCompleter, QFileDialog, QFontComboBox, QFormLayout, QFrame,
                               QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QMainWindow, QMessageBox, QProgressDialog,
                               QPushButton, QSizePolicy, QSlider, QSpinBox, QTabWidget,
                               QToolButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from . import APP_NAME, AUTHOR, AUTHOR_EMAIL, AUTHOR_LOCALE, __version__
from .canvas import Renderer, Slide
from .display_window import DisplayWindow
from .importer import import_legacy
from .library import NT_BOOKS, OT_BOOKS, Library, split_key
from .reference import BookResolver, ParseError, Ref, ref_from_key
from .settings import Settings
from .version_picker import FavoritesBar, VersionPicker

HISTORY_MAX = 300


class Preview(QWidget):
    """Small live copy of the display window."""

    def __init__(self, renderer: Renderer, parent=None):
        super().__init__(parent)
        self.renderer = renderer
        self.slide = Slide()
        self.style_ = {}
        self.aspect = 16 / 9
        self.setMinimumHeight(150)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set(self, slide: Slide, style: dict, aspect: float):
        self.slide, self.style_, self.aspect = slide, style, max(0.3, aspect)
        self.update()

    def paintEvent(self, _ev):
        p = QPainter(self)
        r = QRectF(self.rect())
        w = min(r.width(), r.height() * self.aspect)
        h = w / self.aspect
        target = QRectF(r.x() + (r.width() - w) / 2, r.y() + (r.height() - h) / 2, w, h)
        p.fillRect(r, self.palette().window())
        self.renderer.paint(p, target, self.slide, self.style_)
        p.setPen(QColor(120, 120, 120))
        p.drawRect(target.adjusted(0, 0, -1, -1))
        p.end()


class ImportWorker(QObject):
    progress = Signal(int, int, str)
    finished = Signal(dict)
    failed = Signal(str)

    def __init__(self, src: Path, dst: Path):
        super().__init__()
        self.src, self.dst = src, dst
        self.cancel = False

    @Slot()
    def run(self):
        try:
            summary = import_legacy(self.src, self.dst, progress=self.progress.emit,
                                    cancelled=lambda: self.cancel)
            self.finished.emit(summary)
        except Exception as exc:
            self.failed.emit(str(exc))


class ControlWindow(QMainWindow):
    def __init__(self, library: Library, settings: Settings):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.library = library
        self.settings = settings
        self.renderer = Renderer(library.data_dir / "backgrounds")
        self.resolver = BookResolver(library)
        self.version = settings["version"] if settings["version"] in library.by_code else (
            library.versions[0].code if library.versions else "")
        self.current_ref: Ref | None = None
        self.current_range: tuple[int, int] | None = None
        self.blank = False
        self.slide = Slide()
        self._import_dlg = None
        self._thread = None
        self._worker = None

        self._save_timer = QTimer(self, singleShot=True, interval=600)
        self._save_timer.timeout.connect(self._save_now)

        self.display = DisplayWindow(self.renderer, self.settings.style)
        self.display.next_requested.connect(self.next_verse)
        self.display.prev_requested.connect(self.prev_verse)
        self.display.blank_toggled.connect(self.toggle_blank)
        self.display.typed.connect(self._typed_on_display)
        self.display.focus_controls.connect(self._focus_controls)
        self.display.state_changed.connect(self._display_state_changed)

        self._build_ui()
        self._build_menu()
        self._build_shortcuts()
        self._restore_windows()
        self._refresh_library_dependent()

        if library.is_empty:
            QTimer.singleShot(200, self._first_run)
        else:
            QTimer.singleShot(0, lambda: self.go(self.settings["last_ref"] or "Genesis 1:1", record=False))

    # ================================================================== UI
    def _build_ui(self):
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(10, 10, 10, 6)
        root.setSpacing(8)

        # --- reference entry row
        row = QHBoxLayout()
        self.prev_btn = QToolButton(text="◀")
        self.prev_btn.setToolTip("Previous verse  (PgUp / Ctrl+←)")
        self.prev_btn.clicked.connect(self.prev_verse)
        self.ref_edit = QLineEdit()
        self.ref_edit.setPlaceholderText("Type a verse and press Enter — e.g.  Juan 3:16   jn 3:16-18   1 pe 5:7   23 (verse in this chapter)")
        self.ref_edit.setClearButtonEnabled(True)
        f = self.ref_edit.font()
        f.setPointSizeF(f.pointSizeF() * 1.35)
        self.ref_edit.setFont(f)
        self.ref_edit.setMinimumHeight(36)
        self.ref_edit.returnPressed.connect(lambda: self.go(self.ref_edit.text()))
        self.completer_model = QStringListModel()
        comp = QCompleter(self.completer_model, self)
        comp.setCaseSensitivity(Qt.CaseInsensitive)
        comp.setFilterMode(Qt.MatchStartsWith)
        comp.setCompletionMode(QCompleter.InlineCompletion)
        self.ref_edit.setCompleter(comp)
        self.next_btn = QToolButton(text="▶")
        self.next_btn.setToolTip("Next verse  (PgDn / Ctrl+→)")
        self.next_btn.clicked.connect(self.next_verse)
        go_btn = QPushButton("Show")
        go_btn.setDefault(True)
        go_btn.clicked.connect(lambda: self.go(self.ref_edit.text()))
        for b in (self.prev_btn, self.next_btn):
            b.setMinimumSize(52, 40)
            f = b.font()
            f.setPointSizeF(f.pointSizeF() * 1.9)
            b.setFont(f)
        row.addWidget(self.prev_btn)
        row.addWidget(self.ref_edit, 1)
        row.addWidget(self.next_btn)
        row.addWidget(go_btn)
        root.addLayout(row)

        self.message = QLabel(" ")
        self.message.setStyleSheet("color: #c0392b;")
        root.addWidget(self.message)

        # --- version row
        vrow = QHBoxLayout()
        self.version_btn = QPushButton()
        self.version_btn.setToolTip("Change Bible version  (Ctrl+K)")
        self.version_btn.setStyleSheet("text-align: left; padding: 6px 10px; font-weight: 600;")
        self.version_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.version_btn.clicked.connect(self.open_version_picker)
        vrow.addWidget(QLabel("Version:"))
        vrow.addWidget(self.version_btn, 1)
        root.addLayout(vrow)
        frow = QHBoxLayout()
        frow.addWidget(QLabel("Favorites:"))
        self.fav_bar = FavoritesBar()
        self.fav_bar.chosen.connect(self.set_version)
        frow.addWidget(self.fav_bar, 1)
        root.addLayout(frow)

        # --- preview
        prev_box = QGroupBox("On screen now")
        pl = QVBoxLayout(prev_box)
        self.preview = Preview(self.renderer)
        pl.addWidget(self.preview)
        brow = QHBoxLayout()
        self.show_display_btn = QPushButton("Show display")
        self.show_display_btn.setCheckable(True)
        self.show_display_btn.toggled.connect(self._set_display_visible)
        self.fullscreen_btn = QPushButton("Fullscreen on…")
        self.fullscreen_menu_btn = self.fullscreen_btn
        self.fullscreen_btn.clicked.connect(self._fullscreen_menu)
        self.blank_btn = QPushButton("Blank")
        self.blank_btn.setCheckable(True)
        self.blank_btn.setToolTip("Black screen  (Ctrl+B, or B on the display)")
        self.blank_btn.toggled.connect(self.set_blank)
        brow.addWidget(self.show_display_btn)
        brow.addWidget(self.fullscreen_btn)
        brow.addStretch(1)
        brow.addWidget(self.blank_btn)
        pl.addLayout(brow)
        root.addWidget(prev_box, 3)

        # --- tabs
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_search_tab(), "Search")
        self.tabs.addTab(self._build_history_tab(), "History")
        self.tabs.addTab(self._build_style_tab(), "Appearance")
        root.addWidget(self.tabs, 4)

        self.setCentralWidget(central)
        self.resize(760, 860)

    def _build_search_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        row = QHBoxLayout()
        self.search_edit = QLineEdit(placeholderText='Search words…  (all words must match; use "quotes" for an exact phrase)')
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.returnPressed.connect(self.run_search)
        self.search_scope = QComboBox()
        self.search_scope.addItems(["Whole Bible", "Old Testament", "New Testament", "Current book"])
        sbtn = QPushButton("Search")
        sbtn.clicked.connect(self.run_search)
        row.addWidget(self.search_edit, 1)
        row.addWidget(self.search_scope)
        row.addWidget(sbtn)
        lay.addLayout(row)
        self.search_info = QLabel("Results come from the selected version. Double-click (or Enter) a result to show it.")
        self.search_info.setWordWrap(True)
        lay.addWidget(self.search_info)
        self.results = QTreeWidget()
        self.results.setHeaderLabels(["Reference", "Text"])
        self.results.setRootIsDecorated(False)
        self.results.setUniformRowHeights(True)
        self.results.setAlternatingRowColors(True)
        self.results.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.results.header().setSectionResizeMode(1, QHeaderView.Stretch)
        self.results.itemActivated.connect(lambda it, _c: self.show_key(it.data(0, Qt.UserRole)))
        lay.addWidget(self.results)
        return w

    def _build_history_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        self.history_list = QListWidget()
        self.history_list.itemActivated.connect(self._history_activated)
        lay.addWidget(self.history_list)
        row = QHBoxLayout()
        row.addWidget(QLabel("Double-click to show again (in the version it was shown in)."))
        row.addStretch(1)
        clr = QPushButton("Clear history")
        clr.clicked.connect(self._clear_history)
        row.addWidget(clr)
        lay.addLayout(row)
        return w

    def _build_style_tab(self):
        st = self.settings.style
        w = QWidget()
        form = QFormLayout(w)

        self.font_box = QFontComboBox()
        self.font_box.setCurrentFont(st["font_family"])
        self.font_box.currentFontChanged.connect(lambda f: self._style("font_family", f.family()))
        self.bold_box = QCheckBox("Bold")
        self.bold_box.setChecked(st["bold"])
        self.bold_box.toggled.connect(lambda v: self._style("bold", v))
        fr = QHBoxLayout()
        fr.addWidget(self.font_box, 1)
        fr.addWidget(self.bold_box)
        form.addRow("Font", fr)

        self.size_spin = QSpinBox(minimum=30, maximum=300, suffix=" px")
        self.size_spin.setValue(st["max_size"])
        self.size_spin.setToolTip("Largest text size (at 1080p). Longer verses shrink automatically to fit.")
        self.size_spin.valueChanged.connect(lambda v: self._style("max_size", v))
        self.margin_spin = QSpinBox(minimum=0, maximum=25, suffix=" %")
        self.margin_spin.setValue(st["margin"])
        self.margin_spin.valueChanged.connect(lambda v: self._style("margin", v))
        self.align_box = QComboBox()
        self.align_box.addItems(["Center", "Left"])
        self.align_box.setCurrentIndex(1 if st["align"] == "left" else 0)
        self.align_box.currentIndexChanged.connect(lambda i: self._style("align", "left" if i else "center"))
        sr = QHBoxLayout()
        sr.addWidget(QLabel("Max size"))
        sr.addWidget(self.size_spin)
        sr.addWidget(QLabel("Margin"))
        sr.addWidget(self.margin_spin)
        sr.addWidget(QLabel("Align"))
        sr.addWidget(self.align_box)
        sr.addStretch(1)
        form.addRow("Text", sr)

        cr = QHBoxLayout()
        self.text_color_btn = self._color_button("text_color")
        self.ref_color_btn = self._color_button("ref_color")
        self.shadow_box = QCheckBox("Shadow")
        self.shadow_box.setChecked(st["shadow"])
        self.shadow_box.toggled.connect(lambda v: self._style("shadow", v))
        cr.addWidget(QLabel("Verse"))
        cr.addWidget(self.text_color_btn)
        cr.addWidget(QLabel("Version name"))
        cr.addWidget(self.ref_color_btn)
        cr.addWidget(self.shadow_box)
        cr.addStretch(1)
        form.addRow("Colors", cr)

        fr2 = QHBoxLayout()
        self.show_ref_box = QCheckBox("Reference")
        self.show_ref_box.setChecked(st["show_reference"])
        self.show_ref_box.toggled.connect(lambda v: self._style("show_reference", v))
        self.show_ver_box = QCheckBox("Version name")
        self.show_ver_box.setChecked(st["show_version"])
        self.show_ver_box.toggled.connect(lambda v: self._style("show_version", v))
        fr2.addWidget(self.show_ref_box)
        fr2.addWidget(self.show_ver_box)
        fr2.addStretch(1)
        form.addRow("Top-left label", fr2)

        br = QHBoxLayout()
        self.bg_mode = QComboBox()
        self.bg_mode.addItems(["Image", "Solid color"])
        self.bg_mode.setCurrentIndex(0 if st["bg_mode"] == "image" else 1)
        self.bg_mode.currentIndexChanged.connect(lambda i: self._style("bg_mode", "color" if i else "image"))
        self.bg_color_btn = self._color_button("bg_color")
        self.dim_slider = QSlider(Qt.Horizontal, minimum=0, maximum=85)
        self.dim_slider.setValue(st["dim"])
        self.dim_slider.setToolTip("Darken the image so text is easier to read")
        self.dim_slider.valueChanged.connect(lambda v: self._style("dim", v))
        br.addWidget(self.bg_mode)
        br.addWidget(QLabel("Color"))
        br.addWidget(self.bg_color_btn)
        br.addWidget(QLabel("Darken"))
        br.addWidget(self.dim_slider, 1)
        form.addRow("Background", br)

        self.bg_list = QListWidget()
        self.bg_list.setViewMode(QListWidget.IconMode)
        self.bg_list.setIconSize(QSize(128, 72))
        self.bg_list.setResizeMode(QListWidget.Adjust)
        self.bg_list.setMovement(QListWidget.Static)
        self.bg_list.setFixedHeight(118)
        self.bg_list.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.bg_list.setFlow(QListWidget.LeftToRight)
        self.bg_list.setWrapping(False)
        self.bg_list.itemClicked.connect(self._pick_background)
        add_bg = QPushButton("Add image…")
        add_bg.clicked.connect(self._add_background)
        bl = QVBoxLayout()
        bl.addWidget(self.bg_list)
        bl.addWidget(add_bg, alignment=Qt.AlignLeft)
        form.addRow("", bl)
        return w

    def _color_button(self, key):
        b = QToolButton()
        b.setFixedSize(40, 22)

        def refresh():
            b.setStyleSheet(f"background: {self.settings.style[key]}; border: 1px solid #888;")

        def pick():
            c = QColorDialog.getColor(QColor(self.settings.style[key]), self, "Choose color")
            if c.isValid():
                self._style(key, c.name())
                refresh()
        b.clicked.connect(pick)
        refresh()
        return b

    def _build_menu(self):
        mb = self.menuBar()
        fm = mb.addMenu("&File")
        fm.addAction("Import Bible Version…", self.import_dialog)
        fm.addAction("Open data folder", self._open_data_folder)
        fm.addSeparator()
        fm.addAction("Quit", QKeySequence.Quit, self.close)

        dm = mb.addMenu("&Display")
        self.act_show = dm.addAction("Show display window")
        self.act_show.setCheckable(True)
        self.act_show.setShortcut("Ctrl+D")
        self.act_show.toggled.connect(self.show_display_btn.setChecked)
        self.screens_menu = dm.addMenu("Fullscreen on screen")
        self.screens_menu.aboutToShow.connect(lambda: self._fill_screens_menu(self.screens_menu))
        dm.addAction("Toggle fullscreen", "F11", self._toggle_display_fullscreen)
        dm.addAction("Exit fullscreen (windowed)", self.display.leave_fullscreen)
        dm.addSeparator()
        self.act_top = dm.addAction("Display always on top")
        self.act_top.setCheckable(True)
        self.act_top.toggled.connect(self.display.set_on_top)
        self.act_frameless = dm.addAction("Borderless display window")
        self.act_frameless.setCheckable(True)
        self.act_frameless.toggled.connect(self.display.set_frameless)
        dm.addSeparator()
        dm.addAction("Blank screen", "Ctrl+B", lambda: self.blank_btn.toggle())

        vm = mb.addMenu("&View")
        self.act_ctrl_top = vm.addAction("Keep this window on top")
        self.act_ctrl_top.setCheckable(True)
        self.act_ctrl_top.toggled.connect(self._set_control_on_top)
        vm.addAction("Choose version…", "Ctrl+K", self.open_version_picker)
        vm.addAction("Find text", "Ctrl+F", self._focus_search)
        vm.addAction("Go to reference", "Ctrl+L", self._focus_ref)

        hm = mb.addMenu("&Help")
        hm.addAction("Keyboard shortcuts", self._show_help)
        hm.addSeparator()
        hm.addAction(f"About {APP_NAME}", self._show_about)

    def _build_shortcuts(self):
        for seq in ("PgDown", "Ctrl+Right", "Alt+Right"):
            QShortcut(QKeySequence(seq), self, self.next_verse)
        for seq in ("PgUp", "Ctrl+Left", "Alt+Left"):
            QShortcut(QKeySequence(seq), self, self.prev_verse)
        for i in range(1, 10):
            QShortcut(QKeySequence(f"Ctrl+{i}"), self, lambda n=i: self._favorite_n(n))
        QShortcut(QKeySequence("Escape"), self, self._focus_ref)

    # ============================================================ library
    def _refresh_library_dependent(self):
        self._update_version_ui()
        self._load_backgrounds()
        self._load_history()
        self.completer_model.setStringList(self.resolver.completions(self.version) if self.library.versions else [])

    def _update_version_ui(self):
        v = self.library.by_code.get(self.version)
        if v:
            extra = f"   ({v.coverage})" if v.coverage else ""
            self.version_btn.setText(f"{v.abbr}   ·   {v.name.title() if v.name.isupper() else v.name}   ·   {v.language}{extra}   ▾")
        else:
            self.version_btn.setText("No Bibles yet — File ▸ Import Bible Version…")
        self.fav_bar.set_favorites(self.library, self.settings["favorites"], self.version)

    def _load_backgrounds(self):
        self.bg_list.clear()
        d = self.library.data_dir / "backgrounds"
        files = sorted(p for p in d.glob("*") if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}) if d.exists() else []
        cur = self.settings.style.get("background")
        for p in files:
            pm = QPixmap(str(p))
            if pm.isNull():
                continue
            it = QListWidgetItem(QIcon(pm.scaled(128, 72, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)), p.stem)
            it.setData(Qt.UserRole, p.name)
            it.setToolTip(p.name)
            self.bg_list.addItem(it)
            if p.name == cur:
                it.setSelected(True)

    # ============================================================ navigation
    def go(self, text: str, record: bool = True):
        if not self.library.versions:
            self._first_run()
            return
        try:
            ref = self.resolver.parse(text, self.current_ref, self.version)
        except ParseError as e:
            self.message.setText(str(e))
            return
        self.message.setText(" ")
        self._show_range(ref.start_key, ref.end_key, record=record)

    def show_key(self, key: int, record: bool = True):
        if key:
            self._show_range(key, key, record=record)

    def _show_range(self, start: int, end: int, record: bool = True):
        passage = self.library.passage(self.version, start, end)
        self.current_range = (start, end)
        self.current_ref = ref_from_key(start)
        v = passage.version
        note = ""
        if not passage.text.strip():
            note = f"{passage.reference} is not in {v.abbr}" + (f" ({v.coverage})" if v.coverage else "")
        self.blank = False
        self.blank_btn.blockSignals(True)
        self.blank_btn.setChecked(False)
        self.blank_btn.blockSignals(False)
        self.slide = Slide(text=passage.text.strip(), reference=passage.reference,
                           version=v.name, note=note)
        self._push_slide()
        self.ref_edit.setText(passage.reference.title())
        self.ref_edit.selectAll()
        self.settings["last_ref"] = passage.reference
        self.statusBar().showMessage(f"{passage.reference}  —  {v.abbr}", 4000)
        if record:
            self._record_history(start, end)
        self._schedule_save()

    def next_verse(self):
        if not self.current_range:
            return
        vt = self.library.text(self.version)
        k = vt.next_key(self.current_range[1])
        if k:
            self.show_key(k, record=False)

    def prev_verse(self):
        if not self.current_range:
            return
        vt = self.library.text(self.version)
        k = vt.prev_key(self.current_range[0])
        if k:
            self.show_key(k, record=False)

    def set_version(self, code: str):
        if code not in self.library.by_code:
            return
        self.version = code
        self.settings["version"] = code
        self._update_version_ui()
        self.completer_model.setStringList(self.resolver.completions(code))
        if self.current_range:
            self._show_range(*self.current_range, record=False)
        if self.search_edit.text().strip() and self.results.topLevelItemCount():
            self.run_search()
        self._schedule_save()

    def open_version_picker(self):
        if not self.library.versions:
            return
        dlg = VersionPicker(self.library, self.version, self.settings["favorites"], self)
        dlg.chosen.connect(self.set_version)
        dlg.favorites_changed.connect(self._favorites_changed)
        pos = self.version_btn.mapToGlobal(self.version_btn.rect().bottomLeft())
        dlg.resize(max(560, self.version_btn.width()), 520)
        scr = self.screen().availableGeometry()
        pos.setY(min(pos.y(), scr.bottom() - dlg.height()))
        dlg.move(pos)
        dlg.exec()

    def _favorites_changed(self, favs):
        self.settings["favorites"] = favs
        self.fav_bar.set_favorites(self.library, favs, self.version)
        self._schedule_save()

    def _favorite_n(self, n):
        favs = [c for c in self.settings["favorites"] if c in self.library.by_code]
        if n <= len(favs):
            self.set_version(favs[n - 1])

    # ============================================================ display
    def _push_slide(self):
        slide = Slide(blank=True) if self.blank else self.slide
        self.display.set_slide(slide)
        g = self.display.geometry() if self.display.isVisible() else None
        aspect = (g.width() / g.height()) if g and g.height() else 16 / 9
        self.preview.set(slide, self.settings.style, aspect)

    def set_blank(self, on: bool):
        self.blank = on
        self._push_slide()

    def toggle_blank(self):
        self.blank_btn.toggle()

    def _style(self, key, value):
        self.settings.style[key] = value
        self.display.set_style(self.settings.style)
        self._push_slide()
        self._schedule_save()

    def _pick_background(self, item):
        self.bg_mode.setCurrentIndex(0)
        self._style("background", item.data(Qt.UserRole))

    def _add_background(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose background image", str(Path.home()),
                                              "Images (*.jpg *.jpeg *.png *.bmp *.webp)")
        if path:
            import shutil
            d = self.library.data_dir / "backgrounds"
            d.mkdir(parents=True, exist_ok=True)
            target = d / Path(path).name
            if Path(path).resolve() != target.resolve():
                shutil.copy2(path, target)
            self._load_backgrounds()
            self._style("bg_mode", "image")
            self.bg_mode.setCurrentIndex(0)
            self._style("background", target.name)

    def _set_display_visible(self, on: bool):
        self.act_show.blockSignals(True)
        self.act_show.setChecked(on)
        self.act_show.blockSignals(False)
        self.show_display_btn.setText("Hide display" if on else "Show display")
        if on:
            self.display.show()
            self.display.raise_()
        else:
            self.display.hide()
        self.settings.display["visible"] = on
        self._push_slide()
        self._schedule_save()

    def _fill_screens_menu(self, menu):
        menu.clear()
        for i, s in enumerate(QGuiApplication.screens(), 1):
            g = s.geometry()
            primary = "  (main)" if s == QGuiApplication.primaryScreen() else ""
            a = menu.addAction(f"Screen {i}: {s.name()}  {g.width()}×{g.height()}{primary}")
            a.triggered.connect(lambda _=False, n=s.name(): self._fullscreen_on(n))
        menu.addSeparator()
        menu.addAction("Windowed (not fullscreen)", self.display.leave_fullscreen)

    def _fullscreen_menu(self):
        from PySide6.QtWidgets import QMenu
        m = QMenu(self)
        self._fill_screens_menu(m)
        m.exec(self.fullscreen_btn.mapToGlobal(self.fullscreen_btn.rect().bottomLeft()))

    def _fullscreen_on(self, name):
        self.show_display_btn.setChecked(True)
        self.display.move_to_screen(name)
        self.settings.display["screen"] = name
        self.activateWindow()      # keep keyboard focus on the controls

    def _toggle_display_fullscreen(self):
        self.show_display_btn.setChecked(True)
        self.display.toggle_fullscreen()

    def _display_state_changed(self):
        d = self.settings.display
        d["fullscreen"] = self.display.isFullScreen()
        d["frameless"] = self.display.frameless
        d["on_top"] = self.display.on_top
        g = self.display.windowed_geometry()
        d["geometry"] = [g.x(), g.y(), g.width(), g.height()]
        if self.display.isFullScreen():
            d["screen"] = self.display.current_screen_name()
        self.fullscreen_btn.setText("Fullscreen ✓ …" if d["fullscreen"] else "Fullscreen on…")
        if self.preview.slide is not None:
            self._push_slide()
        self._schedule_save()

    def _typed_on_display(self, ch: str):
        self._focus_controls()
        self.ref_edit.setText(ch)
        self.ref_edit.setFocus()
        self.ref_edit.end(False)

    def _focus_controls(self):
        self.showNormal() if self.isMinimized() else self.show()
        self.raise_()
        self.activateWindow()
        self._focus_ref()

    def _focus_ref(self):
        self.ref_edit.setFocus()
        self.ref_edit.selectAll()

    def _focus_search(self):
        self.tabs.setCurrentIndex(0)
        self.search_edit.setFocus()
        self.search_edit.selectAll()

    def _set_control_on_top(self, on: bool):
        self.setWindowFlag(Qt.WindowStaysOnTopHint, on)
        self.show()
        self.settings["control_on_top"] = on
        self._schedule_save()

    # ============================================================ search
    def run_search(self):
        q = self.search_edit.text().strip()
        self.results.clear()
        if not q or not self.version:
            return
        scope = self.search_scope.currentIndex()
        books = None
        if scope == 1:
            books = OT_BOOKS
        elif scope == 2:
            books = NT_BOOKS
        elif scope == 3 and self.current_ref:
            books = [self.current_ref.book]
        vt = self.library.text(self.version)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            keys, total = vt.search(q, books=books, limit=1000)
        finally:
            QApplication.restoreOverrideCursor()
        v = vt.version
        items = []
        for k in keys:
            b, c, vs = split_key(k)
            t = vt.get(k)
            it = QTreeWidgetItem([f"{v.book_name(b)} {c}:{vs}", t])
            it.setData(0, Qt.UserRole, k)
            it.setToolTip(1, t)
            items.append(it)
        self.results.addTopLevelItems(items)
        shown = f" (showing first {len(keys)})" if total > len(keys) else ""
        self.search_info.setText(f"{total:,} verses in {v.abbr} contain “{q}”{shown}. Double-click or Enter to show.")
        if items:
            self.results.setCurrentItem(items[0])

    # ============================================================ history
    def _record_history(self, start, end):
        h = [e for e in self.settings["history"] if not (e["start"] == start and e["end"] == end and e["code"] == self.version)]
        h.insert(0, {"code": self.version, "start": start, "end": end})
        self.settings["history"] = h[:HISTORY_MAX]
        self._load_history()

    def _load_history(self):
        self.history_list.clear()
        for e in self.settings["history"]:
            v = self.library.by_code.get(e["code"])
            if not v:
                continue
            it = QListWidgetItem(f"{self._ref_label(v, e)}    —  {v.abbr}")
            it.setData(Qt.UserRole, e)
            self.history_list.addItem(it)

    @staticmethod
    def _ref_label(v, e):
        b, c, vs = split_key(e["start"])
        _, c2, v2 = split_key(e["end"])
        s = f"{v.book_name(b)} {c}:{vs}"
        if e["end"] != e["start"]:
            s += f"-{v2}" if c2 == c else f"-{c2}:{v2}"
        return s

    def _history_activated(self, item):
        e = item.data(Qt.UserRole)
        if e["code"] != self.version:
            self.set_version(e["code"])
        self._show_range(e["start"], e["end"], record=False)

    def _clear_history(self):
        self.settings["history"] = []
        self._load_history()
        self._schedule_save()

    # ============================================================ import
    def _first_run(self):
        r = QMessageBox.question(
            self, "Import your Bibles",
            "No Bible library found yet.\n\nImport the Bibles and background images from the old "
            "Digital Bible app now? You'll be asked for its folder "
            "(the one containing the 'Bibles' and 'Images' folders).",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        if r == QMessageBox.Yes:
            self.import_dialog()

    def import_dialog(self):
        start = self.settings.data.get("legacy_dir") or str(Path.home() / "Documents")
        folder = QFileDialog.getExistingDirectory(self, "Import Bible Version — select the folder that contains the Bibles folder", start)
        if not folder:
            return
        self.settings["legacy_dir"] = folder
        self._schedule_save()
        self._import_dlg = dlg = QProgressDialog("Starting import…", "Cancel", 0, 100, self)
        dlg.setWindowTitle("Import")
        dlg.setWindowModality(Qt.WindowModal)
        dlg.setMinimumDuration(0)
        dlg.setAutoReset(False)
        dlg.setAutoClose(False)
        dlg.setValue(0)
        self._thread = QThread(self)
        self._worker = ImportWorker(Path(folder), self.library.data_dir)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        # IMPORTANT: connect to methods of this (main-thread) QObject, not to
        # plain functions/lambdas. PySide6 runs plain-function slots on the
        # worker thread, and touching widgets from there froze the app on Windows.
        self._worker.progress.connect(self._import_progress)
        self._worker.finished.connect(self._import_done)
        self._worker.failed.connect(self._import_failed)
        dlg.canceled.connect(self._import_cancel)
        self._thread.start()

    @Slot(int, int, str)
    def _import_progress(self, i, total, msg):
        dlg = self._import_dlg
        if dlg is None:
            return
        dlg.setMaximum(max(1, total))
        dlg.setValue(min(i, total))
        dlg.setLabelText(f"{msg}   ({i} of {total})")

    @Slot()
    def _import_cancel(self):
        if self._worker is not None:
            self._worker.cancel = True
        if self._import_dlg is not None:
            self._import_dlg.setLabelText("Cancelling after the current Bible…")

    def _import_finish(self):
        if self._import_dlg is not None:
            self._import_dlg.close()
            self._import_dlg = None
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait(5000)

    @Slot(dict)
    def _import_done(self, summary):
        self._import_finish()
        self.library.reload()
        self.resolver = BookResolver(self.library)
        if self.version not in self.library.by_code and self.library.versions:
            self.version = "001" if "001" in self.library.by_code else self.library.versions[0].code
        self._refresh_library_dependent()
        failed = "\n".join(f"• {n}: {e}" for n, e in summary["failed"][:10])
        QMessageBox.information(self, "Import finished",
                                f"Imported {len(summary['imported'])} Bible versions and "
                                f"{summary['images']} background images." + (f"\n\nProblems:\n{failed}" if failed else ""))
        if self.library.versions:
            self.go(self.settings["last_ref"] or "Genesis 1:1", record=False)

    @Slot(str)
    def _import_failed(self, msg):
        self._import_finish()
        QMessageBox.warning(self, "Import failed", msg)

    def _open_data_folder(self):
        p = str(self.library.data_dir)
        Path(p).mkdir(parents=True, exist_ok=True)
        if sys.platform.startswith("win"):
            os.startfile(p)  # noqa
        elif sys.platform == "darwin":
            subprocess.Popen(["open", p])
        else:
            subprocess.Popen(["xdg-open", p])

    def _show_about(self):
        box = QMessageBox(self)
        box.setWindowTitle(f"About {APP_NAME}")
        box.setTextFormat(Qt.RichText)
        box.setText(
            f"<h2 style='margin-bottom:0'>{APP_NAME}</h2>"
            f"<p style='margin-top:2px'>Version {__version__}</p>"
            f"<p>Show Bible verses on a screen or projector.</p>"
            f"<p><b>{AUTHOR}</b><br>{AUTHOR_LOCALE}<br>"
            f"<a href='mailto:{AUTHOR_EMAIL}'>{AUTHOR_EMAIL}</a></p>"
            f"<p style='color:gray'>{len(self.library.versions)} Bible versions installed</p>")
        box.setTextInteractionFlags(Qt.TextBrowserInteraction)
        box.setIconPixmap(QPixmap())
        box.exec()

    def _show_help(self):
        QMessageBox.information(self, "Keyboard shortcuts", (
            "CONTROL WINDOW\n"
            "  Enter — show the typed reference\n"
            "  PgDn / Ctrl+→ — next verse        PgUp / Ctrl+← — previous verse\n"
            "  Ctrl+K — choose version            Ctrl+1…9 — favorite versions\n"
            "  Ctrl+F — search text               Ctrl+L / Esc — jump to the reference box\n"
            "  Ctrl+B — blank screen              Ctrl+D — show/hide display\n"
            "  F11 — display fullscreen on/off\n\n"
            "DISPLAY WINDOW\n"
            "  → ↓ Space PgDn — next     ← ↑ PgUp — previous\n"
            "  F11 / F / double-click — fullscreen    Esc — back to a window\n"
            "  B — blank      start typing — jumps to the reference box\n"
            "  Right-click — screen, always-on-top, borderless options\n\n"
            "REFERENCES\n"
            "  Juan 3:16   jn 3:16   John 3:16-18   Mat 5:3-6:4   1 pe 5:7   I Pedro 5:7\n"
            "  Juan 3 (chapter)   3:17 (same book)   18 (same chapter)   Jude 3"))

    # ============================================================ persistence
    def _restore_windows(self):
        s = self.settings
        if s["control_geometry"]:
            x, y, w, h = s["control_geometry"]
            self.setGeometry(x, y, w, h)
        if s["control_on_top"]:
            self.act_ctrl_top.setChecked(True)
        d = s.display
        if d["geometry"]:
            x, y, w, h = d["geometry"]
            self.display.setGeometry(x, y, w, h)
        self.act_top.setChecked(bool(d["on_top"]))
        self.act_frameless.setChecked(bool(d["frameless"]))

    def restore_display(self):
        d = self.settings.display
        names = [sc.name() for sc in QGuiApplication.screens()]
        if d["visible"]:
            self.show_display_btn.setChecked(True)
            if d["fullscreen"] and d.get("screen") in names:
                self.display.move_to_screen(d["screen"])
            elif d["fullscreen"] and len(names) > 1:
                self.display.move_to_screen(names[1])
        else:
            self.show_display_btn.setChecked(False)
        self.activateWindow()

    def _schedule_save(self):
        self._save_timer.start()

    def _save_now(self):
        g = self.geometry()
        self.settings["control_geometry"] = [g.x(), g.y(), g.width(), g.height()]
        self.settings.save()

    def closeEvent(self, ev):
        if self._thread is not None and self._thread.isRunning():
            self._worker.cancel = True
            self._thread.quit()
            self._thread.wait(10000)
        self._save_now()
        self.display.close()
        super().closeEvent(ev)
