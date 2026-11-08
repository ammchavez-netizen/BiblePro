"""Parse typed references like "jn 3:16", "1 pe 5:7", "Juan 3:16-18", "Mateo 24"."""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Optional

from .library import ENGLISH_BOOKS, Library, fold, make_key, split_key

# Common abbreviations (English, Spanish, Tagalog). Keys are normalized (see norm()).
ABBREVIATIONS = {
    1: "gen gn ge", 2: "ex exo exod", 3: "lev lv le", 4: "num nm nu nb bil", 5: "deut dt deu",
    6: "josh jos jsh", 7: "judg jdg jg jdgs huk", 8: "ru rth", 9: "1sam 1sa 1sm", 10: "2sam 2sa 2sm",
    11: "1kgs 1ki 1kg 1king 1har 1re", 12: "2kgs 2ki 2kg 2king 2har 2re", 13: "1chr 1ch 1cr 1cro",
    14: "2chr 2ch 2cr 2cro", 15: "ezr esd", 16: "neh ne", 17: "esth est es", 18: "jb",
    19: "ps psa psm pss psalm sal slm aw", 20: "prov pr prv pro kaw", 21: "eccl ecc ec qoh ecl",
    22: "song sos ss sng cant canticles awitngmgaawit", 23: "isa is", 24: "jer je jr",
    25: "lam la pan", 26: "ezek eze ezk", 27: "dan dn da", 28: "hos ho os ose", 29: "jl joe",
    30: "am", 31: "obad ob oba abd", 32: "jonah jnh jon", 33: "mic mc mi", 34: "nah na",
    35: "hab hb", 36: "zeph zep zp zef sof", 37: "hag hg ag", 38: "zech zec zc zac",
    39: "mal ml", 40: "matt mt mat", 41: "mk mrk mr mar", 42: "lk luk lu luc",
    43: "jn jhn joh jo", 44: "act ac hch gaw", 45: "rom ro rm", 46: "1cor 1co", 47: "2cor 2co",
    48: "gal ga", 49: "eph ephes ef efe", 50: "phil php pp fil flp", 51: "col co",
    52: "1thess 1th 1ts 1tes", 53: "2thess 2th 2ts 2tes", 54: "1tim 1ti 1tm", 55: "2tim 2ti 2tm",
    56: "tit ti", 57: "philem phm phlm flm flmn", 58: "heb he", 59: "jas jam jm sant stg",
    60: "1pet 1pe 1pt 1p 1ped", 61: "2pet 2pe 2pt 2p 2ped", 62: "1jn 1jo 1jhn 1joh",
    63: "2jn 2jo 2jhn 2joh", 64: "3jn 3jo 3jhn 3joh", 65: "jud jd", 66: "rev re rv apoc ap apo",
}

_ORDINALS = {
    "i": "1", "ii": "2", "iii": "3", "1st": "1", "2nd": "2", "3rd": "3",
    "first": "1", "second": "2", "third": "3", "una": "1", "ikalawang": "2", "ikatlong": "3",
    "primera": "1", "segunda": "2", "tercera": "3", "primeiro": "1", "segundo": "2", "terceiro": "3",
}


def norm(name: str) -> str:
    """'I  Corinto' -> '1corinto', 'Song of Solomon' -> 'songofsolomon', '創 世 記' -> '創世記'."""
    s = fold(name).replace(".", " ").strip()
    parts = s.split()
    if parts and parts[0] in _ORDINALS and len(parts) > 1:
        parts[0] = _ORDINALS[parts[0]]
    s = "".join(parts)
    return "".join(ch for ch in s if ch.isalnum())


@dataclass
class Ref:
    book: int
    chapter: int
    verse: int
    verse_end: Optional[int] = None
    chapter_end: Optional[int] = None

    @property
    def start_key(self) -> int:
        return make_key(self.book, self.chapter, self.verse)

    @property
    def end_key(self) -> int:
        return make_key(self.book, self.chapter_end or self.chapter, self.verse_end or self.verse)


class ParseError(ValueError):
    pass


_REF = re.compile(
    r"^\s*(?P<book>(?:[1-3]\s*)?[^\d:]*?[^\d\s:])?\s*"
    r"(?P<ch>\d+)?"
    r"(?:\s*[:.,\s]\s*(?P<v>\d+))?"
    r"(?:\s*[-–—]\s*(?:(?P<ch2>\d+)\s*[:.]\s*)?(?P<v2>\d+))?\s*$"
)


class BookResolver:
    def __init__(self, library: Library):
        self.library = library
        votes: dict[str, Counter] = defaultdict(Counter)
        for v in library.versions:
            for b, name in v.books.items():
                key = norm(name)
                if key and not key.isdigit():
                    votes[key][b] += 1
        for b, name in enumerate(ENGLISH_BOOKS, 1):
            votes[norm(name)][b] += 1000
            votes[norm(name.rstrip("s"))][b] += 1000  # "psalm"
        self.names = {k: c.most_common(1)[0][0] for k, c in votes.items()}
        self.abbr = {}
        for b, keys in ABBREVIATIONS.items():
            for k in keys.split():
                self.abbr.setdefault(k, b)
        self._sorted = sorted(set(self.names) | set(self.abbr))

    def resolve(self, text: str, version_code: Optional[str] = None) -> Optional[int]:
        key = norm(text)
        if not key:
            return None
        if key in self.abbr:
            return self.abbr[key]
        if key in self.names:
            return self.names[key]
        # Prefix match. Prefer the current version's names, then English, then canon order.
        cands = set()
        for k in self._sorted:
            if k.startswith(key):
                cands.add(self.abbr.get(k) or self.names[k])
        if not cands:
            return None
        if len(cands) == 1:
            return cands.pop()
        if version_code and version_code in self.library.by_code:
            v = self.library.by_code[version_code]
            local = [b for b in sorted(cands) if norm(v.book_name(b)).startswith(key)]
            if local:
                return local[0]
        eng = [b for b in sorted(cands) if norm(ENGLISH_BOOKS[b - 1]).startswith(key)]
        return (eng or sorted(cands))[0]

    def completions(self, version_code: Optional[str]) -> list[str]:
        names = []
        if version_code in self.library.by_code:
            v = self.library.by_code[version_code]
            names += [v.book_name(b).title() for b in range(1, 67)]
        names += ENGLISH_BOOKS
        seen, out = set(), []
        for n in names:
            if n.lower() not in seen:
                seen.add(n.lower())
                out.append(n)
        return out

    def parse(self, text: str, current: Optional[Ref] = None, version_code: Optional[str] = None) -> Ref:
        text = text.strip()
        if not text:
            raise ParseError("Type a reference, e.g. Juan 3:16")
        m = _REF.match(text)
        if not m:
            raise ParseError(f"Couldn't read “{text}”")
        book_txt, ch, v, ch2, v2 = m.group("book", "ch", "v", "ch2", "v2")
        lib = self.library

        if book_txt:
            book = self.resolve(book_txt, version_code)
            if book is None:
                raise ParseError(f"Unknown book “{book_txt.strip()}”")
            chapter = int(ch) if ch else 1
            verse = int(v) if v else 1
            if ch and not v and lib.chapter_count(book) == 1:   # "Jude 3" = verse 3
                chapter, verse = 1, int(ch)
        else:
            if current is None:
                raise ParseError("Include a book name, e.g. Juan 3:16")
            book = current.book
            if ch and v:              # "3:16" -> same book
                chapter, verse = int(ch), int(v)
            elif ch:                  # "16"   -> same chapter
                chapter, verse = current.chapter, int(ch)
            else:
                raise ParseError(f"Couldn't read “{text}”")

        if not 1 <= chapter <= lib.chapter_count(book):
            raise ParseError(f"{ENGLISH_BOOKS[book - 1]} has {lib.chapter_count(book)} chapters")
        vmax = lib.verse_count(book, chapter)
        if not 1 <= verse <= vmax:
            raise ParseError(f"{ENGLISH_BOOKS[book - 1]} {chapter} has {vmax} verses")
        ref = Ref(book, chapter, verse)
        if v2:
            c2 = int(ch2) if ch2 else chapter
            e2 = int(v2)
            if c2 < chapter or (c2 == chapter and e2 < verse):
                raise ParseError("The end of the range is before the start")
            if c2 > lib.chapter_count(book):
                raise ParseError(f"{ENGLISH_BOOKS[book - 1]} has {lib.chapter_count(book)} chapters")
            e2 = min(e2, lib.verse_count(book, c2))
            ref.verse_end, ref.chapter_end = e2, (c2 if c2 != chapter else None)
        return ref


def ref_from_key(key: int) -> Ref:
    b, c, v = split_key(key)
    return Ref(b, c, v)
