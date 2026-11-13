"""Hybrid retrieval: exact references + keyword (FTS5) + meaning (bge-m3).

Results from the three methods are merged with Reciprocal Rank Fusion (RRF):
each method contributes 1/(k + rank) per verse, so a verse found by several
methods rises to the top. Verses are grouped by Bible location (book/chapter/
verse) because the same verse in two translations is the same passage; the
displayed text is picked from the preferred language/translation.

Everything here runs offline.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from ..library import Library, split_key
from ..reference import BookResolver, ParseError
from .embeddings import Embedder, EmbeddingError
from .keyword_index import KeywordIndex
from .vector_store import VectorStore, VectorStoreError

RRF_K = 60

# Something that looks like "<book> <chapter>:<verse>[-<verse>]" inside free text.
_REF_IN_TEXT = re.compile(
    r"((?:[1-3]|i{1,3})?\s*[^\W\d_]+(?:\s+(?:of|ng|mga|de|los|del)\s+[^\W\d_]+)*)\s*"
    r"(\d{1,3})\s*[:.]\s*(\d{1,3})(?:\s*[-–]\s*(\d{1,3}))?", re.UNICODE | re.IGNORECASE)


@dataclass
class RetrievalConfig:
    final_k: int = 12               # verses handed to the AI
    keyword_k: int = 60
    dense_k: int = 60
    min_similarity: float = 0.35    # dense hits below this are ignored
    language_boost: float = 0.25    # extra weight for verses in the user's language
    preferred_codes: tuple = ()     # e.g. ("001", "002")


@dataclass
class RetrievedVerse:
    key: int
    code: str                       # translation shown
    abbr: str
    translation: str
    language: str
    reference: str                  # in that translation's book names
    text: str
    score: float
    methods: list = field(default_factory=list)       # "reference", "keyword", "semantic"
    similarity: Optional[float] = None

    @property
    def book_chapter_verse(self):
        return split_key(self.key)


@dataclass
class RetrievalResult:
    verses: list
    references_found: list          # verse keys the user explicitly mentioned
    semantic_available: bool
    notes: list = field(default_factory=list)


class Retriever:
    def __init__(self, library: Library, keyword: Optional[KeywordIndex],
                 store: Optional[VectorStore], embedder: Optional[Embedder],
                 indexed_codes: list[str], config: RetrievalConfig = RetrievalConfig()):
        self.library = library
        self.resolver = BookResolver(library)
        self.keyword, self.store, self.embedder = keyword, store, embedder
        self.indexed_codes = [c for c in indexed_codes if c in library.by_code]
        self.config = config
        # Why meaning-based search is off when no vector store/embedder was given (set by the caller).
        self.dense_off_reason = "the meaning index hasn't been built yet"

    # ------------------------------------------------------------ references
    def find_references(self, question: str) -> list[tuple[int, int]]:
        """Return (start_key, end_key) for every Bible reference written in the question."""
        out = []
        for m in _REF_IN_TEXT.finditer(question):
            words = m.group(1).split()
            # try the longest book-name candidate first ("Song of Solomon", "1 Juan", "Romans")
            for i in range(len(words)):
                cand = " ".join(words[i:]) + f" {m.group(2)}:{m.group(3)}" + (f"-{m.group(4)}" if m.group(4) else "")
                try:
                    r = self.resolver.parse(cand, None)
                except ParseError:
                    continue
                if self.resolver.resolve(" ".join(words[i:])) is not None:
                    out.append((r.start_key, r.end_key))
                    break
        return out

    # ------------------------------------------------------------ main
    def retrieve(self, question: str, lang_code: Optional[str] = None,
                 codes: Optional[list[str]] = None, suggested_refs: Optional[list[str]] = None,
                 extra_query: str = "") -> RetrievalResult:
        """suggested_refs: references proposed by Gemini ("Matthew 27:51-53"); they are looked up
        in the local Bibles and ranked high. extra_query: a standalone rewrite of the question
        (for follow-ups) that is searched as well."""
        cfg = self.config
        codes = [c for c in (codes or self.indexed_codes) if c in self.library.by_code]
        scores: dict[int, float] = {}
        methods: dict[int, set] = {}
        best_text: dict[int, tuple] = {}      # key -> (code, text) as found
        similarity: dict[int, float] = {}
        notes = []

        def add(key, rank, method, code=None, text=None, weight=1.0):
            scores[key] = scores.get(key, 0.0) + weight / (RRF_K + rank)
            methods.setdefault(key, set()).add(method)
            if code and key not in best_text:
                best_text[key] = (code, text)

        # 1) explicit references: always included, ranked first
        refs = self.find_references(question)
        ref_keys = []
        for start, end in refs:
            vt = self.library.text(codes[0] if codes else self.library.versions[0].code)
            k = start
            while k is not None and k <= end and len(ref_keys) < 40:
                ref_keys.append(k)
                k = vt.next_key(k)
        for rank, key in enumerate(ref_keys):
            add(key, 0, "reference", weight=10.0 - rank * 0.01)

        # 1b) passages suggested by Gemini (only those that exist in the Bibles get in)
        sugg_keys = []
        if suggested_refs:
            vt = self.library.text(codes[0] if codes else self.library.versions[0].code)
            for ref in suggested_refs:
                for start, end in self.find_references(ref):
                    k = start
                    while k is not None and k <= end and len(sugg_keys) < 24:
                        if k not in sugg_keys and k not in ref_keys:
                            sugg_keys.append(k)
                        k = vt.next_key(k)
        for rank, key in enumerate(sugg_keys):
            add(key, rank, "suggested", weight=3.0)

        # 2) keyword search (without the reference text itself, e.g. "Romans 8:28")
        if self.keyword is not None:
            kw_query = _REF_IN_TEXT.sub(" ", question) if refs else question
            for rank, h in enumerate(self.keyword.search(kw_query, codes, cfg.keyword_k)):
                add(h.key, rank, "keyword", h.code, h.text)
            if extra_query and extra_query.strip().lower() != question.strip().lower():
                for rank, h in enumerate(self.keyword.search(extra_query, codes, cfg.keyword_k // 2)):
                    add(h.key, rank, "keyword", h.code, h.text, weight=0.7)

        # 3) semantic search
        semantic_ok = False
        if self.store is not None and self.embedder is not None:
            try:
                queries = [question]
                if extra_query and extra_query.strip().lower() != question.strip().lower():
                    queries.append(extra_query)
                for qi, q in enumerate(queries):
                    qv = self.embedder.encode_query(q)
                    hits = self.store.query(qv, cfg.dense_k, codes=codes)
                    semantic_ok = True
                    for rank, h in enumerate(hits):
                        if h.score < cfg.min_similarity:
                            continue
                        add(h.key, rank, "semantic", h.code, h.text, weight=1.0 if qi == 0 else 0.8)
                        similarity[h.key] = max(similarity.get(h.key, 0.0), h.score)
            except (EmbeddingError, VectorStoreError) as exc:
                notes.append(f"Meaning-based search unavailable: {exc}")
        else:
            notes.append(f"Keyword search only: {self.dense_off_reason}.")

        # 4) choose the translation to show for each verse + language preference
        ranked = []
        for key, s in scores.items():
            code = self._display_code(key, codes, lang_code, best_text.get(key, (None,))[0])
            if code is None:
                continue
            v = self.library.by_code[code]
            text = self.library.text(code).get(key) or ""
            if not text:
                continue
            if lang_code and _lang(v.language) == lang_code:
                s *= 1.0 + cfg.language_boost
            ranked.append(RetrievedVerse(
                key=key, code=code, abbr=v.abbr, translation=v.name, language=v.language,
                reference=self.library.passage(code, key).reference, text=text, score=s,
                methods=sorted(methods[key]), similarity=similarity.get(key)))
        ranked.sort(key=lambda r: (-("reference" in r.methods), -r.score))
        limit = min(30, max(cfg.final_k, len(ref_keys) + len(sugg_keys) + 4))
        return RetrievalResult(ranked[:limit], ref_keys, semantic_ok, notes)

    def _display_code(self, key, codes, lang_code, found_code):
        order = []
        if lang_code:
            order += [c for c in codes if _lang(self.library.by_code[c].language) == lang_code]
        order += [c for c in self.config.preferred_codes if c in codes]
        if found_code:
            order.append(found_code)
        order += codes
        for c in order:
            if self.library.text(c).has(key):
                return c
        return None

    # ------------------------------------------------------------ comparison
    def compare(self, key: int, codes: Optional[list[str]] = None) -> list[RetrievedVerse]:
        """The same verse in many translations (all 182 by default) for comparison questions."""
        import sqlite3
        out = []
        for v in self.library.versions:
            if codes and v.code not in codes:
                continue
            path = self.library.data_dir / "bibles" / f"{v.code}.sqlite"
            try:   # read just this one verse (read-only); avoids loading 182 Bibles into memory
                con = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
                row = con.execute("SELECT text FROM verses WHERE key=?", (key,)).fetchone()
                con.close()
            except sqlite3.Error:
                continue
            text = row[0] if row else ""
            if text:
                b, c, vs = split_key(key)
                out.append(RetrievedVerse(key, v.code, v.abbr, v.name, v.language,
                                          f"{v.book_name(b)} {c}:{vs}", text, 1.0, ["comparison"]))
        return out


def _lang(language: str) -> str:
    from .sources import language_code
    return language_code(language)
