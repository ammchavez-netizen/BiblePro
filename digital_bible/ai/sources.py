"""Bible database discovery and normalized verse records.

Bible files are opened READ-ONLY and are never modified.

Formats are handled by small *schema adapters*. Each adapter looks at the
tables/columns of a SQLite file and says whether it can read it. Today there
are two formats:

* ``ConvertedAdapter`` - BibleQ-AI's own files  data/bibles/NNN.sqlite
  (table ``verses(key, book, chapter, verse, text)`` + ``info``)
* ``LegacyAdapter``    - the old Digital Bible ``.db3`` files
  (RC4-encrypted; table ``bible(bcv, content)`` + ``bookname`` + ``info``)

To support a new format later, add an adapter class and register it in
``ADAPTERS``; nothing else has to change.
"""
from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, Optional

from ..library import ENGLISH_BOOKS, make_key

# OSIS book identifiers (a standard, language-neutral book id), 1..66.
OSIS_BOOKS = [
    "Gen", "Exod", "Lev", "Num", "Deut", "Josh", "Judg", "Ruth", "1Sam", "2Sam", "1Kgs",
    "2Kgs", "1Chr", "2Chr", "Ezra", "Neh", "Esth", "Job", "Ps", "Prov", "Eccl", "Song",
    "Isa", "Jer", "Lam", "Ezek", "Dan", "Hos", "Joel", "Amos", "Obad", "Jonah", "Mic",
    "Nah", "Hab", "Zeph", "Hag", "Zech", "Mal", "Matt", "Mark", "Luke", "John", "Acts",
    "Rom", "1Cor", "2Cor", "Gal", "Eph", "Phil", "Col", "1Thess", "2Thess", "1Tim",
    "2Tim", "Titus", "Phlm", "Heb", "Jas", "1Pet", "2Pet", "1John", "2John", "3John",
    "Jude", "Rev",
]

# Language name (as stored in the catalog) -> ISO 639 code.
LANGUAGE_CODES = {
    "English": "en", "Tagalog": "tl", "Spanish": "es", "Portuguese": "pt", "Chinese": "zh",
    "Korean": "ko", "Japanese": "ja", "German": "de", "French": "fr", "Italian": "it",
    "Dutch": "nl", "Swedish": "sv", "Norwegian": "no", "Latin": "la", "Greek": "el",
    "Indonesian": "id", "Malay / Indonesian": "ms", "Hindi": "hi", "Nepali": "ne",
    "Swahili": "sw", "Afrikaans": "af", "Cebuano": "ceb", "Ilocano": "ilo",
    "Hiligaynon": "hil", "Kapampangan": "pam", "Pangasinan": "pag", "Waray": "war",
    "Bicolano": "bcl", "Chavacano": "cbk", "Twi": "tw", "Ewe": "ee", "Tok Pisin": "tpi",
    "Haitian Creole": "ht", "Hawaiian Pidgin": "hwc",
}


def language_code(language: str) -> str:
    return LANGUAGE_CODES.get(language, "und")      # "und" = undetermined (ISO 639-2)


def normalize_for_hash(text: str) -> str:
    return " ".join(text.casefold().split())


def text_hash(text: str) -> str:
    return hashlib.sha1(normalize_for_hash(text).encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class VerseRecord:
    """One verse of one translation, in a format-independent shape."""
    source_file: str        # database file name, e.g. "001.sqlite"
    code: str               # version code, e.g. "001"
    translation: str        # e.g. "ANG DATING BIBLIA"
    abbr: str               # e.g. "ADBTAG"
    language: str           # e.g. "Tagalog"
    lang_code: str          # e.g. "tl"
    book: int               # 1..66
    book_id: str            # OSIS id, e.g. "John"
    book_name: str          # name in this translation, e.g. "JUAN"
    chapter: int
    verse: int
    text: str

    @property
    def key(self) -> int:
        return make_key(self.book, self.chapter, self.verse)

    @property
    def uid(self) -> str:
        """Stable id of this verse in this translation."""
        return f"{self.code}:{self.key}"

    @property
    def reference(self) -> str:
        return f"{self.book_name} {self.chapter}:{self.verse}"

    @property
    def text_hash(self) -> str:
        return text_hash(self.text)


@dataclass
class BibleSource:
    """A discovered Bible database file."""
    path: Path
    code: str
    translation: str = ""
    abbr: str = ""
    language: str = "Other"
    lang_code: str = "und"
    adapter: str = ""
    books: dict = field(default_factory=dict)
    error: str = ""

    @property
    def file_name(self) -> str:
        return self.path.name

    @property
    def signature(self) -> str:
        """Changes whenever the file changes (size + modification time)."""
        st = self.path.stat()
        return f"{st.st_size}:{int(st.st_mtime)}"

    def book_name(self, book: int) -> str:
        name = (self.books.get(book) or "").strip()
        return name if name and not name.isdigit() else ENGLISH_BOOKS[book - 1].upper()


# ----------------------------------------------------------------- adapters

def _open_ro(path: Path) -> sqlite3.Connection:
    # mode=ro + immutable: SQLite will not write anything, not even a journal.
    return sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro&immutable=1", uri=True)


def _schema(con: sqlite3.Connection) -> dict:
    tables = {}
    for (name,) in con.execute("SELECT name FROM sqlite_master WHERE type='table'"):
        tables[name.lower()] = {r[1].lower() for r in con.execute(f'PRAGMA table_info("{name}")')}
    return tables


class Adapter:
    name = "base"

    @staticmethod
    def matches(schema: dict) -> bool:
        raise NotImplementedError

    def connect(self, path: Path) -> sqlite3.Connection:
        return _open_ro(path)

    def info(self, con) -> tuple[str, dict]:
        raise NotImplementedError

    def verses(self, con) -> Iterator[tuple[int, int, int, str]]:
        raise NotImplementedError


class ConvertedAdapter(Adapter):
    name = "biblepro"

    @staticmethod
    def matches(schema):
        return {"key", "book", "chapter", "verse", "text"} <= schema.get("verses", set())

    def info(self, con):
        title = ""
        if "info" in _schema(con):
            row = con.execute("SELECT value FROM info WHERE key='name'").fetchone()
            title = row[0] if row else ""
        return title, {}

    def verses(self, con):
        yield from con.execute("SELECT book, chapter, verse, text FROM verses ORDER BY key")


class LegacyAdapter(Adapter):
    """Old Digital Bible .db3 (encrypted). Decrypted in memory only."""
    name = "digital-bible-legacy"

    @staticmethod
    def matches(schema):
        return {"bcv", "content"} <= schema.get("bible", set())

    def connect(self, path: Path):
        from ..importer import open_legacy_db
        return open_legacy_db(path)          # in-memory copy, file untouched

    def info(self, con):
        title, books = "", {}
        try:
            row = con.execute("SELECT BookTitle FROM info").fetchone()
            title = (row[0] or "") if row else ""
        except sqlite3.Error:
            pass
        try:
            row = con.execute("SELECT * FROM bookname").fetchone()
            if row:
                books = {b: str(n or "") for b, n in enumerate(row[1:67], start=1)}
        except sqlite3.Error:
            pass
        return title, books

    def verses(self, con):
        from ..importer import clean_text, split_bcv
        for bcv, content in con.execute("SELECT bcv, content FROM bible ORDER BY bcv"):
            b, c, v = split_bcv(bcv)
            if 1 <= b <= 66:
                yield b, c, v, clean_text(content)


ADAPTERS = [ConvertedAdapter(), LegacyAdapter()]


def detect_adapter(path: Path) -> Optional[Adapter]:
    """Pick the adapter that can read this file, or None."""
    try:
        if path.suffix.lower() == ".db3":
            with open(path, "rb") as fh:
                head = fh.read(16)
            if not head.startswith(b"SQLite format 3"):
                return LegacyAdapter()       # encrypted legacy file
        con = _open_ro(path)
        try:
            schema = _schema(con)
        finally:
            con.close()
    except (OSError, sqlite3.Error):
        return None
    return next((a for a in ADAPTERS if a.matches(schema)), None)


# --------------------------------------------------------------- discovery

def discover_sources(data_dir: Path, extra_dirs: tuple = ()) -> list[BibleSource]:
    """Find every readable Bible database.

    Metadata (name, abbreviation, language, book names) comes from
    catalog.sqlite when the file is known there, otherwise from the file.
    """
    data_dir = Path(data_dir)
    catalog = {}
    cat_path = data_dir / "catalog.sqlite"
    if cat_path.exists():
        con = _open_ro(cat_path)
        for code, abbr, name, lang in con.execute("SELECT code, abbr, name, language FROM versions"):
            catalog[code] = {"abbr": abbr, "name": name, "language": lang, "books": {}}
        for code, book, name in con.execute("SELECT code, book, name FROM book_names"):
            if code in catalog:
                catalog[code]["books"][book] = name
        con.close()

    files = sorted((data_dir / "bibles").glob("*.sqlite"))
    for d in extra_dirs:
        files += sorted(Path(d).glob("*.db3")) + sorted(Path(d).glob("*.sqlite"))

    out, seen = [], set()
    for path in files:
        code = path.stem
        if code in seen:                 # converted copy wins over the legacy original
            continue
        src = BibleSource(path=path, code=code)
        # Files BibleQ-AI converted itself (listed in the catalog) are known to be in its own
        # format, so they need not be opened just to detect the schema. Anything else is inspected.
        if code in catalog and path.suffix == ".sqlite" and path.parent == data_dir / "bibles":
            adapter = ConvertedAdapter()
        else:
            adapter = detect_adapter(path)
        if adapter is None:
            src.error = "unsupported or unreadable database"
            out.append(src)
            continue
        src.adapter = adapter.name
        meta = catalog.get(code)
        if meta:
            src.abbr, src.translation, src.language = meta["abbr"], meta["name"], meta["language"]
            src.books = dict(meta["books"])
        if not src.translation or not src.books:
            try:
                con = adapter.connect(path)
                title, books = adapter.info(con)
                con.close()
                src.translation = src.translation or title or code
                src.books = src.books or books
            except Exception as exc:                       # corrupted file etc.
                src.error = f"cannot read: {exc}"
        src.abbr = src.abbr or src.translation[:10]
        src.lang_code = language_code(src.language)
        seen.add(code)
        out.append(src)
    return out


def iter_verses(src: BibleSource) -> Iterator[VerseRecord]:
    """Yield the non-empty verses of a source as VerseRecords."""
    adapter = next(a for a in ADAPTERS if a.name == src.adapter)
    con = adapter.connect(src.path)
    try:
        for b, c, v, text in adapter.verses(con):
            if text and str(text).strip():
                yield VerseRecord(
                    source_file=src.file_name, code=src.code, translation=src.translation,
                    abbr=src.abbr, language=src.language, lang_code=src.lang_code,
                    book=b, book_id=OSIS_BOOKS[b - 1], book_name=src.book_name(b),
                    chapter=c, verse=v, text=str(text).strip())
    finally:
        con.close()
