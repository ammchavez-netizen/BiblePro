"""Keyword (full-text) index using SQLite FTS5.

Good at what meaning-based search is weak at: proper names, places, book
names, rare theological terms and exact phrases. Stored in
data/index/keyword.sqlite; rebuilt per translation only when its file changed.
"""
from __future__ import annotations

import re
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Optional

from ..library import fold
from .sources import BibleSource, iter_verses

SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
    code TEXT PRIMARY KEY, file TEXT, signature TEXT, verses INTEGER,
    language TEXT, lang_code TEXT, translation TEXT, abbr TEXT, indexed_at REAL
);
CREATE VIRTUAL TABLE IF NOT EXISTS verses_fts USING fts5(
    text, code UNINDEXED, key UNINDEXED,
    tokenize = 'unicode61 remove_diacritics 2'
);
"""

_WORD = re.compile(r"\w+", re.UNICODE)

# Words that carry no search meaning in questions (English, Tagalog, Spanish).
STOPWORDS = set("""
a an the and or of to in on at for from by with about as is are was were be been being do does did
what which who whom whose when where why how this that these those it its into than then there their
they them he she his her him we us our you your i me my mine not no yes can could would should will
shall may might must say says said tell teach teaches taught explain describe compare meaning mean means
bible biblical verse verses scripture scriptures passage passages chapter book according discuss
discusses please give show find list some any all many much more most
ang ng mga sa si ni kay na at ay ba po ano anong sino saan kailan bakit paano ito iyan iyon yung
ay sinasabi sabi sinabi tungkol ipaliwanag paliwanag ihambing talata bibliya biblia aklat kabanata
el la los las un una unos unas de del al y o que qué en por para con sobre como cómo cuál cuáles
quién dónde cuándo es son fue dice dicen explica explicar compara comparar versículo versículos
""".split())


@dataclass
class KeywordHit:
    code: str
    key: int
    score: float          # higher = better
    text: str


_SUFFIXES = ("iness", "ies", "ing", "ness", "edly", "ed", "es", "s")


def stem(word: str) -> str:
    """Very light suffix trimming so 'loving' ~ love, 'enemies' ~ enemy (used as a prefix)."""
    for suf in _SUFFIXES:
        if word.endswith(suf) and len(word) - len(suf) >= 3:
            return word[: -len(suf)]
    return word


def build_match_query(query: str, mode: str = "and") -> str:
    """Turn user text into a safe FTS5 query.

    "quoted phrases" stay phrases; other words become prefix terms
    ("forgiv" matches forgive/forgiven/forgiveness). mode="or" relaxes the
    query when the strict AND version finds too little.
    """
    phrases = re.findall(r'"([^"]+)"', query)
    rest = re.sub(r'"[^"]+"', " ", query)
    parts = []
    for ph in phrases:
        words = _WORD.findall(fold(ph))
        if words:
            parts.append('"' + " ".join(words) + '"')
    for w in _WORD.findall(fold(rest)):
        if len(w) >= 2 and w not in STOPWORDS and not w.isdigit():
            parts.append(f'"{stem(w)}"*')
    if not parts:
        return ""
    return (" OR " if mode == "or" else " AND ").join(parts)


class KeywordIndex:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(self.path, check_same_thread=False)
        self.con.executescript(SCHEMA)

    def close(self):
        self.con.close()

    # ------------------------------------------------------------ status
    def indexed(self) -> dict:
        return {r[0]: {"signature": r[1], "verses": r[2], "indexed_at": r[3]}
                for r in self.con.execute("SELECT code, signature, verses, indexed_at FROM sources")}

    def needs_update(self, src: BibleSource) -> bool:
        row = self.con.execute("SELECT signature, verses FROM sources WHERE code=?", (src.code,)).fetchone()
        if row is None:
            return True
        if row[0] == src.signature:
            return False
        # Date changed (e.g. data folder copied to another PC): compare the verse count and
        # a quick checksum of the text instead of rebuilding blindly.
        try:
            texts = [r.text for r in iter_verses(src)]
        except Exception:
            return True
        import hashlib
        digest = hashlib.sha1("\n".join(texts).encode("utf-8")).hexdigest()
        stored = self.con.execute("SELECT group_concat(text, char(10)) FROM "
                                  "(SELECT text FROM verses_fts WHERE code=? ORDER BY key)", (src.code,)).fetchone()[0] or ""
        if len(texts) == row[1] and hashlib.sha1(stored.encode("utf-8")).hexdigest() == digest:
            with self.con:
                self.con.execute("UPDATE sources SET signature=? WHERE code=?", (src.signature, src.code))
            return False
        return True

    # ------------------------------------------------------------ build
    def remove(self, code: str):
        self.con.execute("DELETE FROM verses_fts WHERE code=?", (code,))
        self.con.execute("DELETE FROM sources WHERE code=?", (code,))
        self.con.commit()

    def index_source(self, src: BibleSource, cancelled: Callable[[], bool] = lambda: False) -> int:
        """(Re)index one translation. Returns verses indexed, or -1 if cancelled."""
        rows = []
        for rec in iter_verses(src):
            if cancelled():
                return -1
            rows.append((rec.text, rec.code, rec.key))
        with self.con:                                    # one transaction
            self.con.execute("DELETE FROM verses_fts WHERE code=?", (src.code,))
            self.con.executemany("INSERT INTO verses_fts(text, code, key) VALUES (?,?,?)", rows)
            self.con.execute(
                "INSERT OR REPLACE INTO sources VALUES (?,?,?,?,?,?,?,?,?)",
                (src.code, src.file_name, src.signature, len(rows), src.language,
                 src.lang_code, src.translation, src.abbr, time.time()))
        return len(rows)

    def update(self, sources: Iterable[BibleSource], keep_codes: Optional[set] = None,
               progress: Callable[[str], None] = lambda m: None,
               cancelled: Callable[[], bool] = lambda: False) -> dict:
        """Index changed/new sources; drop translations no longer wanted."""
        sources = [s for s in sources if not s.error]
        wanted = {s.code for s in sources} if keep_codes is None else set(keep_codes)
        report = {"indexed": [], "skipped": [], "removed": [], "errors": []}
        for code in set(self.indexed()) - wanted:
            self.remove(code)
            report["removed"].append(code)
        for src in sources:
            if src.code not in wanted:
                continue
            if not self.needs_update(src):
                report["skipped"].append(src.code)
                continue
            progress(f"Keyword index: {src.abbr} ({src.file_name})")
            try:
                n = self.index_source(src, cancelled)
            except Exception as exc:
                report["errors"].append((src.code, str(exc)))
                continue
            if n < 0:
                report["cancelled"] = True
                break
            report["indexed"].append((src.code, n))
        return report

    # ------------------------------------------------------------ search
    def search(self, query: str, codes: Optional[Iterable[str]] = None, limit: int = 50) -> list[KeywordHit]:
        codes = list(codes) if codes else None
        hits = self._run(build_match_query(query, "and"), codes, limit)
        if len(hits) < max(5, limit // 5):                   # relax to OR if strict AND is thin
            seen = {(h.code, h.key) for h in hits}
            for h in self._run(build_match_query(query, "or"), codes, limit):
                if (h.code, h.key) not in seen:
                    hits.append(h)
        return hits[:limit]

    def _run(self, match: str, codes, limit) -> list[KeywordHit]:
        if not match:
            return []
        sql = "SELECT code, key, -bm25(verses_fts) AS s, text FROM verses_fts WHERE verses_fts MATCH ?"
        args: list = [match]
        if codes:
            sql += f" AND code IN ({','.join('?' * len(codes))})"
            args += codes
        sql += " ORDER BY bm25(verses_fts) LIMIT ?"
        args.append(limit)
        try:
            return [KeywordHit(c, int(k), float(s), t) for c, k, s, t in self.con.execute(sql, args)]
        except sqlite3.OperationalError:
            return []
