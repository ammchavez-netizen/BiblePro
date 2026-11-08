"""Read access to the imported Bible library (see importer.py)."""
from __future__ import annotations

import bisect
import sqlite3
import unicodedata
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

OT_BOOKS = range(1, 40)
NT_BOOKS = range(40, 67)

# English names used as a fallback for versions with odd/missing book names.
ENGLISH_BOOKS = [
    "Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy", "Joshua", "Judges", "Ruth",
    "1 Samuel", "2 Samuel", "1 Kings", "2 Kings", "1 Chronicles", "2 Chronicles", "Ezra",
    "Nehemiah", "Esther", "Job", "Psalms", "Proverbs", "Ecclesiastes", "Song of Solomon",
    "Isaiah", "Jeremiah", "Lamentations", "Ezekiel", "Daniel", "Hosea", "Joel", "Amos",
    "Obadiah", "Jonah", "Micah", "Nahum", "Habakkuk", "Zephaniah", "Haggai", "Zechariah",
    "Malachi", "Matthew", "Mark", "Luke", "John", "Acts", "Romans", "1 Corinthians",
    "2 Corinthians", "Galatians", "Ephesians", "Philippians", "Colossians",
    "1 Thessalonians", "2 Thessalonians", "1 Timothy", "2 Timothy", "Titus", "Philemon",
    "Hebrews", "James", "1 Peter", "2 Peter", "1 John", "2 John", "3 John", "Jude",
    "Revelation",
]


def make_key(book: int, chapter: int, verse: int) -> int:
    return book * 1_000_000 + chapter * 1000 + verse


def split_key(key: int):
    return key // 1_000_000, (key // 1000) % 1000, key % 1000


def fold(text: str) -> str:
    """Lower-case and strip accents, for accent-insensitive search."""
    text = unicodedata.normalize("NFKD", text.casefold())
    return "".join(ch for ch in text if not unicodedata.combining(ch))


@dataclass
class Version:
    code: str
    abbr: str
    name: str
    language: str
    info: str
    verse_count: int
    has_ot: bool
    has_nt: bool
    sort_order: int
    books: dict = field(default_factory=dict)

    @property
    def coverage(self) -> str:
        if self.has_ot and self.has_nt:
            return ""
        return "NT only" if self.has_nt else "OT only"

    def book_name(self, book: int) -> str:
        name = self.books.get(book, "").strip()
        if not name or name.isdigit():
            name = ENGLISH_BOOKS[book - 1].upper()
        return name

    @property
    def label(self) -> str:
        return f"{self.abbr} — {self.name.title() if self.name.isupper() else self.name}"


@dataclass
class Passage:
    version: Version
    keys: list          # verse keys, in order
    texts: list         # matching texts

    @property
    def first(self) -> int:
        return self.keys[0]

    @property
    def last(self) -> int:
        return self.keys[-1]

    @property
    def text(self) -> str:
        if len(self.keys) == 1:
            return self.texts[0]
        parts = []
        for k, t in zip(self.keys, self.texts):
            parts.append(f"{split_key(k)[2]} {t}" if t else "")
        return " ".join(p for p in parts if p)

    @property
    def reference(self) -> str:
        b, c, v = split_key(self.first)
        _, c2, v2 = split_key(self.last)
        ref = f"{self.version.book_name(b)} {c}:{v}"
        if self.last != self.first:
            ref += f"-{v2}" if c2 == c else f"-{c2}:{v2}"
        return ref


class VersionText:
    """All verses of one version, kept in memory for fast navigation/search."""

    def __init__(self, version: Version, path: Path):
        self.version = version
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        rows = con.execute("SELECT key, text FROM verses ORDER BY key").fetchall()
        con.close()
        self.keys = [k for k, _ in rows]
        self.text = {k: t for k, t in rows}
        self._filled = [k for k, t in rows if t]
        self._folded = None

    def get(self, key: int) -> Optional[str]:
        return self.text.get(key)

    def has(self, key: int) -> bool:
        return bool(self.text.get(key))

    def next_key(self, key: int) -> Optional[int]:
        i = bisect.bisect_right(self._filled, key)
        return self._filled[i] if i < len(self._filled) else None

    def prev_key(self, key: int) -> Optional[int]:
        i = bisect.bisect_left(self._filled, key)
        return self._filled[i - 1] if i > 0 else None

    def first_key(self) -> Optional[int]:
        return self._filled[0] if self._filled else None

    def search(self, query: str, books: Optional[Iterable[int]] = None, limit: int = 1000):
        """Accent/case-insensitive search.

        Every word must appear (matched at the start of a word, so "love" finds
        "loved" but "one" doesn't match inside "stone"); "quoted text" must
        appear as written. Verses containing the whole query as a phrase are
        listed first. Returns (keys, total_matches).
        """
        import re
        import shlex
        try:
            terms = shlex.split(query)
        except ValueError:
            terms = query.split()
        terms = [fold(t) for t in terms if t.strip()]
        if not terms:
            return [], 0
        if self._folded is None:
            self._folded = {k: fold(t) for k, t in self.text.items() if t}

        def pattern(term):
            # Scripts without spaces (Chinese/Japanese) -> plain substring.
            if any("　" <= ch <= "鿿" for ch in term):
                return re.compile(re.escape(term))
            return re.compile(r"(?<!\w)" + re.escape(term))

        pats = [pattern(t) for t in terms]
        phrase = pattern(" ".join(terms)) if len(terms) > 1 else None
        allowed = set(books) if books else None
        first, rest = [], []
        for k in self._filled:
            if allowed is not None and k // 1_000_000 not in allowed:
                continue
            ft = self._folded[k]
            if all(p.search(ft) for p in pats):
                (first if phrase is not None and phrase.search(ft) else rest).append(k)
        hits = first + rest
        return hits[:limit], len(hits)


class Library:
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.versions: list[Version] = []
        self.by_code: dict[str, Version] = {}
        self.chapters: dict[int, list[int]] = {}   # book -> [verses in ch1, ch2, ...]
        self._cache: "OrderedDict[str, VersionText]" = OrderedDict()
        self.reload()

    @property
    def catalog_path(self) -> Path:
        return self.data_dir / "catalog.sqlite"

    @property
    def is_empty(self) -> bool:
        return not self.versions

    def reload(self):
        self.versions, self.by_code, self.chapters = [], {}, {}
        self._cache.clear()
        if not self.catalog_path.exists():
            return
        con = sqlite3.connect(f"file:{self.catalog_path}?mode=ro", uri=True)
        for row in con.execute(
            "SELECT code, abbr, name, language, info, verse_count, has_ot, has_nt, sort_order "
            "FROM versions ORDER BY language, name"
        ):
            if not (self.data_dir / "bibles" / f"{row[0]}.sqlite").exists():
                continue
            v = Version(row[0], row[1], row[2], row[3], row[4] or "", row[5],
                        bool(row[6]), bool(row[7]), row[8])
            self.versions.append(v)
            self.by_code[v.code] = v
        for code, book, name in con.execute("SELECT code, book, name FROM book_names"):
            if code in self.by_code:
                self.by_code[code].books[book] = name
        for book, chapter, verses in con.execute("SELECT book, chapter, verses FROM chapters ORDER BY book, chapter"):
            self.chapters.setdefault(book, []).append(verses)
        con.close()

    def languages(self) -> list[str]:
        langs = sorted({v.language for v in self.versions})
        if "Other" in langs:
            langs.remove("Other")
            langs.append("Other")
        return langs

    def text(self, code: str) -> VersionText:
        if code in self._cache:
            self._cache.move_to_end(code)
            return self._cache[code]
        vt = VersionText(self.by_code[code], self.data_dir / "bibles" / f"{code}.sqlite")
        self._cache[code] = vt
        while len(self._cache) > 12:
            self._cache.popitem(last=False)
        return vt

    def chapter_count(self, book: int) -> int:
        return len(self.chapters.get(book, []))

    def verse_count(self, book: int, chapter: int) -> int:
        ch = self.chapters.get(book, [])
        return ch[chapter - 1] if 1 <= chapter <= len(ch) else 0

    def passage(self, code: str, start: int, end: Optional[int] = None) -> Passage:
        vt = self.text(code)
        end = end or start
        keys = [k for k in vt.keys if start <= k <= end] or [start]
        return Passage(vt.version, keys, [vt.get(k) or "" for k in keys])
