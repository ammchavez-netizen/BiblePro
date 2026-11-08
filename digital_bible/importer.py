"""Import the Bible library from the old .NET "Digital Bible" app.

The old app stores each Bible version as an encrypted SQLite file
(``Bibles/NNN.db3``, System.Data.SQLite legacy RC4 encryption) and keeps the
version catalog (names, abbreviations, languages) in ``Settings/display.db``.

This module converts all of that into an open, unencrypted library:

    data/
      catalog.sqlite        versions, book names, chapter/verse counts
      bibles/<code>.sqlite  one plain SQLite file per version
      backgrounds/          background images copied from the old Images folder

Run it from the app (File > Import Bible Version...) or from the
command line:

    python -m digital_bible.importer "C:\\path\\to\\Digital Bible Release_2020.09.13"
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import sqlite3
import sys
import unicodedata
from pathlib import Path
from typing import Callable, Optional

# Password the old app used to open its Bible files (found in Bible.dll).
LEGACY_PASSWORD = b"4ngd4t1ngd55n!"
SQLITE_MAGIC = b"SQLite format 3\x00"

SKIP_IMAGES = {"close.png", "maximize.png", "restore.png", "thumbs.db"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp"}

# Better language labels than the old catalog's "--" (by keyword in the title).
LANGUAGE_HINTS = [
    ("ENGLISH TRANSLATION OF THE GREEK", "English"),
    ("EBERHARD NESTLE", "Greek"), ("GREEK", "Greek"), ("STEPHANUS", "Greek"),
    ("TISCHENDORF", "Greek"), ("SBL GREEK", "Greek"),
    ("CEBUANO", "Cebuano"), ("ILOCANO", "Ilocano"), ("HILIGAYNON", "Hiligaynon"),
    ("PAMPANGO", "Kapampangan"), ("PANGASINENSE", "Pangasinan"), ("WARAY", "Waray"),
    ("BICOL", "Bicolano"), ("CHAVACANO", "Chavacano"),
    ("DUTCH", "Dutch"), ("GERMAN", "German"), ("ELBERFELDER", "German"), ("LUTHER", "German"),
    ("ITALIAN", "Italian"), ("INDONESIAN", "Indonesian"), ("ALKITAB", "Malay / Indonesian"),
    ("JAPANESE", "Japanese"), ("KOREAN", "Korean"), ("HANGUL", "Korean"),
    ("LATIN", "Latin"), ("NORWEGIAN", "Norwegian"), ("SWEDISH", "Swedish"),
    ("SWAHILI", "Swahili"), ("HINDI", "Hindi"), ("NEPALI", "Nepali"),
    ("AFRICAN BIBLE", "Afrikaans"), ("NKWA ASEM", "Twi"), ("ÉWÉ", "Ewe"),
    ("PISIN", "Tok Pisin"), ("HAWAI", "Hawaiian Pidgin"), ("HAITIAN", "Haitian Creole"),
    ("PORTUGUESE", "Portuguese"), ("ALMEIDA", "Portuguese"),
    ("ANG BIBLIA", "Tagalog"),
    ("TYNDALE", "English"), ("BISHOPS BIBLE", "English"), ("PASSION TRANSLATION", "English"),
    ("WYCLIFFE", "English"), ("HEART ENGLISH", "English"),
]

# ---------------------------------------------------------------- decryption


def _rc4(key: bytes, data: bytes) -> bytes:
    s = list(range(256))
    j = 0
    for i in range(256):
        j = (j + s[i] + key[i % len(key)]) & 0xFF
        s[i], s[j] = s[j], s[i]
    i = j = 0
    out = bytearray(len(data))
    for n, b in enumerate(data):
        i = (i + 1) & 0xFF
        j = (j + s[i]) & 0xFF
        s[i], s[j] = s[j], s[i]
        out[n] = b ^ s[(s[i] + s[j]) & 0xFF]
    return bytes(out)


def decrypt_legacy_db(raw: bytes, password: bytes = LEGACY_PASSWORD) -> bytes:
    """Return the plain SQLite bytes of an old Digital Bible .db3 file."""
    if raw.startswith(SQLITE_MAGIC):
        return raw  # already plain
    key = hashlib.sha1(password).digest()[:16]
    head = _rc4(key, raw[:18])
    if not head.startswith(SQLITE_MAGIC):
        raise ValueError("not a Digital Bible database (wrong password or format)")
    page_size = int.from_bytes(head[16:18], "big")
    page_size = 65536 if page_size == 1 else page_size
    if len(raw) % page_size:
        raise ValueError("file size is not a multiple of the page size")
    # Every page is encrypted with a fresh RC4 stream, so one page of keystream
    # repeated across the file decrypts all of it. XOR as big ints = fast, no numpy.
    stream = _rc4(key, bytes(page_size)) * (len(raw) // page_size)
    plain = int.from_bytes(raw, "big") ^ int.from_bytes(stream, "big")
    return plain.to_bytes(len(raw), "big")


def open_legacy_db(path: Path) -> sqlite3.Connection:
    data = decrypt_legacy_db(path.read_bytes())
    con = sqlite3.connect(":memory:")
    con.deserialize(data)
    return con

# ------------------------------------------------------------- text cleanup

_TAG = re.compile(r"<\s*/?\s*[A-Za-z][A-Za-z0-9]*(?:\s+[^<>]*)?\s*/?\s*>")
_CJK = r"\u3000-\u303f\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uff00-\uffef"
_CJK_GAP = re.compile(rf"(?<=[{_CJK}]) +(?=[{_CJK}])")


def clean_text(text) -> str:
    """Tidy verse text: drop stray markup, fix spacing around punctuation.

    Square brackets (words added by translators) are kept on purpose.
    """
    if text is None:
        return ""
    if isinstance(text, bytes):
        try:
            text = text.decode("utf-8")
        except UnicodeDecodeError:
            text = text.decode("cp1252", "replace")
    t = text.replace("\r", " ").replace("\n", " ").replace("\t", " ")
    t = t.replace("{~}", " ")
    t = _TAG.sub(" ", t)
    t = t.replace("*", " ")
    t = re.sub(r"(?:(?<=\s)|^)[~^|<>]+(?=\s|$)", " ", t)  # lone markers
    t = re.sub(r"(?<=\S)\^", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"\s+([,.;:!?)\]}»”’。，、；：！？」』])", r"\1", t)
    t = re.sub(r"([(\[{«“‘「『])\s+", r"\1", t)
    t = re.sub(r"(?<=\w) - (?=\w)", "-", t)
    t = _CJK_GAP.sub("", t)
    return t


def clean_name(name) -> str:
    name = clean_text(name)
    return re.sub(r"\s+", " ", name).strip()


def _abbr_from_title(title: str) -> str:
    words = re.findall(r"[A-Za-zÀ-ÿ]+|\d+", unicodedata.normalize("NFC", title))
    ab = "".join(w if w.isdigit() else w[0] for w in words).upper()
    return ab[:10] or "BIBLE"


def _guess_language(title: str, catalog_lang: Optional[str]) -> str:
    up = title.upper()
    for key, lang in LANGUAGE_HINTS:
        if key in up:
            return lang
    if catalog_lang and catalog_lang not in ("--", "None", ""):
        return catalog_lang.title() if catalog_lang.isupper() else catalog_lang
    return "Other"

# ------------------------------------------------------------------ catalog

CATALOG_SCHEMA = """
CREATE TABLE IF NOT EXISTS versions (
    code TEXT PRIMARY KEY,      -- file stem, e.g. '001'
    abbr TEXT NOT NULL,
    name TEXT NOT NULL,
    language TEXT NOT NULL,
    info TEXT,
    verse_count INTEGER NOT NULL,
    has_ot INTEGER NOT NULL,
    has_nt INTEGER NOT NULL,
    sort_order INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS book_names (
    code TEXT NOT NULL, book INTEGER NOT NULL, name TEXT NOT NULL,
    PRIMARY KEY (code, book)
);
CREATE TABLE IF NOT EXISTS chapters (
    book INTEGER NOT NULL, chapter INTEGER NOT NULL, verses INTEGER NOT NULL,
    PRIMARY KEY (book, chapter)
);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
"""

BIBLE_SCHEMA = """
CREATE TABLE verses (
    key INTEGER PRIMARY KEY,    -- book*1000000 + chapter*1000 + verse
    book INTEGER NOT NULL, chapter INTEGER NOT NULL, verse INTEGER NOT NULL,
    text TEXT NOT NULL
);
CREATE TABLE info (key TEXT PRIMARY KEY, value TEXT);
"""


def _read_legacy_catalog(settings_db: Path) -> dict:
    """Map file name -> (name, abbr, language) from the old display.db."""
    out = {}
    if not settings_db.exists():
        return out
    con = sqlite3.connect(f"file:{settings_db}?mode=ro", uri=True)
    try:
        rows = con.execute(
            "SELECT a.version, a.namedb, a.verabb, c.language "
            "FROM tblControl a LEFT JOIN tblLanguage c ON a.language = c.languageid"
        ).fetchall()
    except sqlite3.Error:
        rows = []
    finally:
        con.close()
    for file_name, name, abbr, lang in rows:
        out[str(file_name).lower()] = (name, abbr, lang)
    return out


def split_bcv(bcv: int):
    """Old key format 1BBCCCVVV -> (book, chapter, verse)."""
    s = int(bcv) % 100_000_000
    return s // 1_000_000, (s // 1000) % 1000, s % 1000


def find_legacy_root(path: Path) -> Path:
    """Accept the release folder, its parent, or the Bibles folder itself."""
    path = Path(path)
    candidates = [path, path.parent] + [p for p in path.glob("*") if p.is_dir()]
    for c in candidates:
        if (c / "Bibles").is_dir() and any((c / "Bibles").glob("*.db3")):
            return c
    if path.name.lower() == "bibles" and any(path.glob("*.db3")):
        return path.parent
    raise FileNotFoundError(f"No 'Bibles' folder with .db3 files found under {path}")


def import_legacy(
    legacy_dir: Path,
    data_dir: Path,
    progress: Optional[Callable[[int, int, str], None]] = None,
    cancelled: Optional[Callable[[], bool]] = None,
) -> dict:
    """Convert the old app's library into ``data_dir``. Returns a summary."""
    root = find_legacy_root(Path(legacy_dir))
    data_dir = Path(data_dir)
    bible_dir = data_dir / "bibles"
    bible_dir.mkdir(parents=True, exist_ok=True)
    legacy_catalog = _read_legacy_catalog(root / "Settings" / "display.db")

    files = sorted((root / "Bibles").glob("*.db3"))
    cat = sqlite3.connect(data_dir / "catalog.sqlite")
    cat.executescript(CATALOG_SCHEMA)
    used_abbr = {r[0] for r in cat.execute("SELECT abbr FROM versions")}
    summary = {"imported": [], "failed": [], "images": 0}
    have_chapters = cat.execute("SELECT COUNT(*) FROM chapters").fetchone()[0] > 0

    for n, path in enumerate(files):
        if cancelled and cancelled():
            break
        code = path.stem
        if progress:
            progress(n, len(files), f"Importing {path.name}")
        try:
            src = open_legacy_db(path)
            title, info = code, ""
            try:
                row = src.execute("SELECT BookTitle, BookInfo FROM info").fetchone()
                if row:
                    title = clean_name(row[0]) or code
                    info = clean_name(row[1] or "")
            except sqlite3.Error:
                pass
            books = {}
            try:
                row = src.execute("SELECT * FROM bookname").fetchone()
                if row:
                    for b, nm in enumerate(row[1:67], start=1):
                        books[b] = clean_name(nm) or str(b)
            except sqlite3.Error:
                pass

            verses = []
            for bcv, content in src.execute("SELECT bcv, content FROM bible ORDER BY bcv"):
                b, c, v = split_bcv(bcv)
                if not (1 <= b <= 66):
                    continue
                verses.append((b * 1_000_000 + c * 1000 + v, b, c, v, clean_text(content)))
            src.close()
            verses.sort()

            out_path = bible_dir / f"{code}.sqlite"
            tmp_path = out_path.with_suffix(".tmp")
            if tmp_path.exists():
                tmp_path.unlink()
            dst = sqlite3.connect(tmp_path)
            dst.executescript(BIBLE_SCHEMA)
            dst.executemany("INSERT OR REPLACE INTO verses VALUES (?,?,?,?,?)", verses)
            dst.executemany("INSERT INTO info VALUES (?,?)",
                            [("name", title), ("info", info), ("source", path.name)])
            dst.commit()
            dst.close()
            os.replace(tmp_path, out_path)

            if not have_chapters and len(verses) > 31000:
                counts = {}
                for _, b, c, v, _t in verses:
                    counts[(b, c)] = max(counts.get((b, c), 0), v)
                cat.executemany("INSERT OR REPLACE INTO chapters VALUES (?,?,?)",
                                [(b, c, v) for (b, c), v in counts.items()])
                have_chapters = True

            name, abbr, lang = legacy_catalog.get(path.name.lower(), (None, None, None))
            name = clean_name(name) if name else title
            if not (abbr or "").strip():
                abbr = _abbr_from_title(name)
                reserved = {(a or "").strip() for _n, a, _l in legacy_catalog.values()}
                if abbr in reserved:
                    abbr = f"{abbr}-{code}"
            old = cat.execute("SELECT abbr FROM versions WHERE code=?", (code,)).fetchone()
            if old:
                used_abbr.discard(old[0])
            if abbr in used_abbr:
                alt = _abbr_from_title(name)
                abbr = alt if alt not in used_abbr else f"{abbr}-{code}"
            used_abbr.add(abbr)
            filled = [x for x in verses if x[4]]
            has_ot = any(x[1] <= 39 for x in filled)
            has_nt = any(x[1] >= 40 for x in filled)
            cat.execute(
                "INSERT OR REPLACE INTO versions VALUES (?,?,?,?,?,?,?,?,?)",
                (code, abbr, name, _guess_language(name, lang), info, len(filled),
                 int(has_ot), int(has_nt), n),
            )
            cat.execute("DELETE FROM book_names WHERE code=?", (code,))
            cat.executemany("INSERT INTO book_names VALUES (?,?,?)",
                            [(code, b, nm) for b, nm in books.items()])
            cat.commit()
            summary["imported"].append(code)
        except Exception as exc:  # keep going; report at the end
            summary["failed"].append((path.name, str(exc)))

    # Background images
    img_src = root / "Images"
    img_dst = data_dir / "backgrounds"
    if img_src.is_dir():
        img_dst.mkdir(parents=True, exist_ok=True)
        for img in img_src.iterdir():
            if img.suffix.lower() in IMAGE_EXT and img.name.lower() not in SKIP_IMAGES:
                target = img_dst / img.name
                if not target.exists() or target.stat().st_size != img.stat().st_size:
                    shutil.copy2(img, target)
                summary["images"] += 1

    cat.execute("INSERT OR REPLACE INTO meta VALUES ('source', ?)", (str(root),))
    cat.commit()
    cat.close()
    if progress:
        progress(len(files), len(files), "Done")
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("legacy_dir", help="Folder of the old app (contains Bibles, Images, Settings)")
    ap.add_argument("--data", default=str(Path(__file__).resolve().parent.parent / "data"),
                    help="Output data folder (default: ./data next to the app)")
    args = ap.parse_args(argv)

    def show(i, total, msg):
        print(f"\r[{i:>3}/{total}] {msg:<40}", end="", flush=True)

    s = import_legacy(Path(args.legacy_dir), Path(args.data), progress=show)
    print(f"\nImported {len(s['imported'])} versions, {s['images']} images into {args.data}")
    for name, err in s["failed"]:
        print(f"  FAILED {name}: {err}")
    return 0 if not s["failed"] else 1


if __name__ == "__main__":
    sys.exit(main())
