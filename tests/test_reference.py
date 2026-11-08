"""Run with:  python -m pytest tests   (needs an imported data/ folder)."""
from pathlib import Path

import pytest

from digital_bible.library import Library, make_key
from digital_bible.reference import BookResolver, ParseError, Ref

DATA = Path(__file__).resolve().parent.parent / "data"
pytestmark = pytest.mark.skipif(not (DATA / "catalog.sqlite").exists(), reason="run the import first")


@pytest.fixture(scope="module")
def lib():
    return Library(DATA)


@pytest.fixture(scope="module")
def res(lib):
    return BookResolver(lib)


@pytest.mark.parametrize("text,expected", [
    ("Gen 1:1", (1, 1, 1)), ("jam 5:16", (59, 5, 16)), ("1 pe 5:7", (60, 5, 7)),
    ("I Pedro 5:7", (60, 5, 7)), ("3 jn 1:2", (64, 1, 2)), ("Juan 3:16", (43, 3, 16)),
    ("II Corinto 11:13", (47, 11, 13)), ("II Hari 18:17", (12, 18, 17)), ("Awit 23", (19, 23, 1)),
    ("Salmos 23:1", (19, 23, 1)), ("Awit ng mga Awit 2:1", (22, 2, 1)), ("Hechos 2:38", (44, 2, 38)),
    ("1pe5:7", (60, 5, 7)), ("jude 3", (65, 1, 3)), ("Mateo 24:24", (40, 24, 24)),
])
def test_parse(res, text, expected):
    r = res.parse(text, None, "001")
    assert (r.book, r.chapter, r.verse) == expected


def test_relative(res):
    cur = Ref(43, 3, 16)
    assert res.parse("3:17", cur).start_key == make_key(43, 3, 17)
    assert res.parse("18", cur).start_key == make_key(43, 3, 18)


def test_range(res):
    r = res.parse("John 3:16-18", None)
    assert (r.start_key, r.end_key) == (make_key(43, 3, 16), make_key(43, 3, 18))


@pytest.mark.parametrize("bad", ["gen 51:1", "jn 3:99", "xyz 1:1", ""])
def test_errors(res, bad):
    with pytest.raises(ParseError):
        res.parse(bad, None)


def test_navigation_and_search(lib):
    vt = lib.text("002")
    assert vt.next_key(make_key(43, 3, 16)) == make_key(43, 3, 17)
    assert vt.next_key(make_key(1, 50, 26)) == make_key(2, 1, 1)
    keys, total = vt.search("love one another")
    assert make_key(43, 13, 34) == keys[0] and total > 10
