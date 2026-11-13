"""Small JSON settings store kept next to the library (portable, like the old app)."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

SETTINGS_VERSION = 2

# ADBTAG, KJV, MESSAGE, NKJV
DEFAULT_FAVORITES = ["001", "002", "034", "056"]

DEFAULTS = {
    "settings_version": SETTINGS_VERSION,
    "version": "001",
    "favorites": list(DEFAULT_FAVORITES),
    "last_ref": "Genesis 1:1",
    "history": [],                 # [{"code":..,"start":..,"end":..}]
    "control_geometry": None,
    "display": {
        "geometry": None,          # [x, y, w, h] when windowed
        "screen": None,            # screen name for fullscreen
        "fullscreen": False,
        "on_top": False,
        "visible": True,
    },
    "ai": {
        "indexed_versions": ["001", "002"],        # Ang Dating Biblia, King James Version
        "embedding_model": "BAAI/bge-m3",
        "retrieval": {"final_k": 12, "keyword_k": 60, "dense_k": 60,
                      "min_similarity": 0.35, "language_boost": 0.25},
        "provider": "gemini",
        "model": "gemini-3.8-flash",
        "answers_enabled": True,   # write answers with Gemini when a key is saved
        "smart_search": True,      # Gemini suggests which passages to look up before searching
        "models_cache": [],        # result of the last "Scan Available Models"
        "models_scanned": "",
    },
    "style": {
        "font_family": "Segoe UI",
        "bold": True,
        "text_color": "#FFFFFF",
        "ref_color": "#FFD54A",
        "bg_mode": "image",        # "image" | "color"
        "background": "default.jpg",
        "bg_color": "#0B1A2E",
        "dim": 35,                 # % dark overlay over the image
        "max_size": 80,           # max text height in px at 1080p
        "margin": 6,               # % of width
        "align": "center",         # "center" | "left"
        "show_reference": True,
        "show_version": True,
        "shadow": True,
    },
}


def app_dir() -> Path:
    if getattr(sys, "frozen", False):          # PyInstaller build
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def assets_dir() -> Path:
    """Bundled read-only files (icon). Inside the .exe they live in _internal."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", app_dir())) / "assets"
    return app_dir() / "assets"


def data_dir() -> Path:
    return app_dir() / "data"


class Settings:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.data = copy.deepcopy(DEFAULTS)
        if self.path.exists():
            try:
                saved = json.loads(self.path.read_text(encoding="utf-8"))
                self._merge(self.data, saved)
                self._upgrade(saved)
            except (OSError, ValueError):
                pass

    def _upgrade(self, saved: dict):
        """Apply new defaults once to settings saved by an older version."""
        if saved.get("settings_version", 1) < 2:
            self.data["favorites"] = list(DEFAULT_FAVORITES)
        self.data["settings_version"] = SETTINGS_VERSION
        # settings that are no longer used (classic window, CPU/GPU option)
        self.data.pop("control_on_top", None)
        self.data["display"].pop("frameless", None)      # the verse window is always borderless now
        self.data.get("ai", {}).pop("device", None)

    @staticmethod
    def _merge(base: dict, new: dict):
        for k, v in new.items():
            if isinstance(v, dict) and isinstance(base.get(k), dict):
                Settings._merge(base[k], v)
            else:
                base[k] = v

    def __getitem__(self, key):
        return self.data[key]

    def __setitem__(self, key, value):
        self.data[key] = value

    @property
    def style(self) -> dict:
        return self.data["style"]

    @property
    def display(self) -> dict:
        return self.data["display"]

    def save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8")
            tmp.replace(self.path)
        except OSError:
            pass
