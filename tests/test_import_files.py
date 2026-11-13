"""Settings › Import Bible version: single .sqlite / .db3 files, plus the display window's shape lock."""
import sqlite3

from digital_bible.display_window import keep_shape
from digital_bible.importer import import_files


def _legacy(path, title="Test Bible", n=3):
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE info (BookTitle TEXT, BookInfo TEXT)")
    con.execute("INSERT INTO info VALUES (?, '')", (title,))
    con.execute("CREATE TABLE bible (bcv INTEGER, content TEXT)")
    con.executemany("INSERT INTO bible VALUES (?, ?)",
                    [(1_001_001_000 + v, f"Verse {v} <i>text</i>") for v in range(1, n + 1)])
    con.commit()
    con.close()


def _own(path, name="Own Format Bible"):
    con = sqlite3.connect(path)
    con.executescript("CREATE TABLE verses (key INTEGER PRIMARY KEY, book INT, chapter INT, verse INT, text TEXT);"
                      "CREATE TABLE info (key TEXT PRIMARY KEY, value TEXT);")
    con.executemany("INSERT INTO verses VALUES (?,?,?,?,?)",
                    [(43_003_016, 43, 3, 16, "For God so loved the world"), (43_003_017, 43, 3, 17, "For God sent")])
    con.execute("INSERT INTO info VALUES ('name', ?)", (name,))
    con.commit()
    con.close()


def test_import_db3_and_sqlite(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    _legacy(src / "kjv.db3")
    _own(src / "mine.sqlite")
    before = (src / "kjv.db3").read_bytes()
    data = tmp_path / "data"
    s = import_files([src / "kjv.db3", src / "mine.sqlite"], data)
    assert s["imported"] == ["001", "002"] and not s["failed"]
    assert (src / "kjv.db3").read_bytes() == before            # the original is never changed
    cat = sqlite3.connect(data / "catalog.sqlite")
    rows = cat.execute("SELECT code, name, verse_count, has_ot, has_nt FROM versions ORDER BY code").fetchall()
    assert rows == [("001", "Test Bible", 3, 1, 0), ("002", "Own Format Bible", 2, 0, 1)]
    text = sqlite3.connect(data / "bibles" / "001.sqlite").execute("SELECT text FROM verses LIMIT 1").fetchone()[0]
    assert text == "Verse 1 text"
    # importing the same file again is skipped, a broken file is reported
    (src / "bad.sqlite").write_bytes(b"not a database at all")
    s = import_files([src / "kjv.db3", src / "bad.sqlite"], data)
    assert s["imported"] == [] and len(s["skipped"]) == 1 and s["failed"][0][0] == "bad.sqlite"


def test_new_code_does_not_overwrite(tmp_path):
    data = tmp_path / "data"
    (data / "bibles").mkdir(parents=True)
    (data / "bibles" / "001.sqlite").write_bytes(b"")
    _legacy(tmp_path / "a.db3")
    assert import_files([tmp_path / "a.db3"], data)["imported"] == ["002"]


def test_keep_shape():
    assert keep_shape(1000, 540, 16 / 9, 240, 135) == (1000, 562)     # width moved more
    assert keep_shape(960, 700, 16 / 9, 240, 135) == (1244, 700)      # height moved more
    assert keep_shape(100, 50, 16 / 9, 240, 135) == (240, 135)        # never below the minimum


def test_chapters_filled_from_small_files(tmp_path):
    _own(tmp_path / "nt.sqlite")
    data = tmp_path / "data"
    import_files([tmp_path / "nt.sqlite"], data)
    cat = sqlite3.connect(data / "catalog.sqlite")
    assert cat.execute("SELECT verses FROM chapters WHERE book=43 AND chapter=3").fetchone() == (17,)
