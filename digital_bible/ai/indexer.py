"""Index management: discovery, keyword + vector indexing, status, logs.

Safe to run on a background thread. Progress is reported through a callback
receiving IndexProgress objects; cancel() stops after the current batch, and
the next run continues where it stopped (records are upserted by id).
"""
from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import asdict, dataclass, field
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Callable, Optional

from .embeddings import EMBEDDING_MODELS, Embedder, EmbeddingError
from .keyword_index import KeywordIndex
from .sources import BibleSource, discover_sources, iter_verses
from .vector_store import VectorStore, VectorStoreError, backup_index

BATCH = 64


@dataclass
class IndexProgress:
    stage: str = "idle"            # scanning | keyword | downloading | embedding | done | cancelled | error
    message: str = ""
    current_db: str = ""
    db_index: int = 0
    db_total: int = 0
    verses_done: int = 0
    verses_total: int = 0
    errors: list = field(default_factory=list)


@dataclass
class IndexStatus:
    databases_found: int = 0
    databases_indexed: int = 0
    databases_with_errors: int = 0
    translations: int = 0
    languages: int = 0
    verses_indexed: int = 0
    embeddings: int = 0
    last_indexed: Optional[float] = None
    state: str = "not built"       # not built | partial | ready | out of date
    embedding_model: str = ""
    selected_versions: list = field(default_factory=list)


def file_hash(path: Path) -> str:
    """Content fingerprint of a Bible file (independent of file dates)."""
    import hashlib
    h = hashlib.sha1()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def same_file(entry: dict, src: BibleSource) -> bool:
    """True if the indexed copy of this Bible matches the file on disk.

    Fast path: size + modification time. If those differ (e.g. the data folder was copied
    to another PC and the copy reset file dates) the content fingerprint decides, so an
    identical Bible is never re-embedded just because its date changed.
    """
    if not entry:
        return False
    if entry.get("signature") == src.signature:
        return True
    stored = entry.get("content_hash")
    if stored and stored == file_hash(src.path):
        entry["signature"] = src.signature          # remember the new date for next time
        return True
    return False


class IndexManager:
    def __init__(self, data_dir: Path, embedding_model: str, versions: list[str]):
        self.data_dir = Path(data_dir)
        self.index_dir = self.data_dir / "index"
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.embedding_model = embedding_model
        self.versions = list(versions)
        self._cancel = threading.Event()
        self._lock = threading.Lock()
        self.sources: list[BibleSource] = []
        self.log = logging.getLogger("biblepro.index")
        if not self.log.handlers:
            h = RotatingFileHandler(self.index_dir / "indexing.log", maxBytes=1_000_000,
                                    backupCount=2, encoding="utf-8")
            h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
            self.log.addHandler(h)
            self.log.setLevel(logging.INFO)

    # ------------------------------------------------------------ helpers
    @property
    def state_path(self) -> Path:
        return self.index_dir / "state.json"

    def _state(self) -> dict:
        try:
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _save_state(self, st: dict):
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(st, indent=1), encoding="utf-8")
        tmp.replace(self.state_path)

    def embedder(self) -> Embedder:
        return Embedder(self.embedding_model, self.data_dir / "models")

    def keyword_index(self) -> KeywordIndex:
        return KeywordIndex(self.index_dir / "keyword.sqlite")

    def vector_store(self) -> VectorStore:
        spec = EMBEDDING_MODELS[self.embedding_model]
        return VectorStore(self.index_dir / "chroma", spec.model_id, spec.dim)

    def cancel(self):
        self._cancel.set()

    def log_text(self, max_chars: int = 50_000) -> str:
        p = self.index_dir / "indexing.log"
        return p.read_text(encoding="utf-8", errors="replace")[-max_chars:] if p.exists() else ""

    # ------------------------------------------------------------ scan / status
    def scan(self) -> list[BibleSource]:
        self.sources = discover_sources(self.data_dir)
        self.log.info("Scan: %d databases, %d with errors", len(self.sources),
                      sum(bool(s.error) for s in self.sources))
        return self.sources

    def status(self) -> IndexStatus:
        sources = self.sources or self.scan()
        st = self._state().get(self.embedding_model, {})
        selected = [s for s in sources if s.code in self.versions and not s.error]
        same = {s.code: same_file(st.get(s.code, {}), s) for s in selected}
        done = [s for s in selected if st.get(s.code, {}).get("complete") and same[s.code]]
        stale = [s for s in selected if s.code in st and not same[s.code]]
        out = IndexStatus(
            databases_found=len(sources),
            databases_indexed=len(done),
            databases_with_errors=sum(bool(s.error) for s in sources),
            translations=len(selected),
            languages=len({s.language for s in selected}),
            verses_indexed=sum(st.get(s.code, {}).get("verses", 0) for s in done),
            embeddings=sum(st.get(s.code, {}).get("embedded", 0) for s in done),
            last_indexed=max((v.get("updated_at", 0) for v in st.values()), default=None) or None,
            embedding_model=self.embedding_model,
            selected_versions=[s.abbr for s in selected])
        if not st:
            out.state = "not built"
        elif stale:
            out.state = "out of date"
        elif len(done) == len(selected):
            out.state = "ready"
        else:
            out.state = "partial"
        return out

    # ------------------------------------------------------------ build
    def build(self, progress: Callable[[IndexProgress], None] = lambda p: None,
              rebuild: bool = False, embeddings: bool = True) -> IndexProgress:
        """Build / refresh the index. rebuild=True starts the vectors from scratch."""
        if not self._lock.acquire(blocking=False):
            raise RuntimeError("Indexing is already running.")
        self._cancel.clear()
        p = IndexProgress(stage="scanning", message="Scanning Bible databases…")
        try:
            progress(p)
            sources = self.scan()
            selected = [s for s in sources if s.code in self.versions]
            for s in selected:
                if s.error:
                    p.errors.append(f"{s.file_name}: {s.error}")
            selected = [s for s in selected if not s.error]
            p.db_total = len(selected)
            p.verses_total = 0

            # 1) keyword index (fast)
            p.stage, p.message = "keyword", "Updating keyword index…"
            progress(p)
            kw = self.keyword_index()
            if rebuild:
                for code in list(kw.indexed()):
                    kw.remove(code)
            rep = kw.update(selected, keep_codes={s.code for s in selected},
                            cancelled=self._cancel.is_set)
            kw.close()
            p.errors += [f"{c}: {e}" for c, e in rep["errors"]]
            self.log.info("Keyword index: %s", rep)
            if self._cancel.is_set():
                return self._finish(p, "cancelled", progress)
            if not embeddings:
                return self._finish(p, "done", progress)

            # 2) embedding model
            emb = self.embedder()
            if not emb.is_downloaded():
                p.stage = "downloading"
                emb.download(lambda m: (setattr(p, "message", m), progress(p)))
            p.message = f"Loading {self.embedding_model}…"
            progress(p)
            emb.load()

            # 3) vectors, translation by translation
            store = self.vector_store()
            state = self._state()
            mstate = state.setdefault(self.embedding_model, {})
            if rebuild:
                store.drop()
                store = self.vector_store()
                mstate.clear()
            for code in [c for c in list(mstate) if c not in {s.code for s in selected}]:
                store.delete_code(code)
                mstate.pop(code, None)
            self._save_state(state)

            for i, src in enumerate(selected, 1):
                p.db_index, p.current_db = i, f"{src.abbr} ({src.file_name})"
                entry = mstate.get(src.code, {})
                unchanged = same_file(entry, src)
                if entry.get("complete") and unchanged:
                    if not entry.get("content_hash"):           # record fingerprint (older indexes)
                        entry["content_hash"] = file_hash(src.path)
                    self._save_state(state)
                    continue
                if entry and not unchanged:
                    store.delete_code(src.code)                 # file really changed: redo it
                records = list(iter_verses(src))
                have = store.existing_ids(src.code)
                todo = [r for r in records if r.uid not in have]
                p.stage = "embedding"
                p.verses_total, p.verses_done = len(records), len(records) - len(todo)
                p.message = f"Embedding {src.abbr}: {p.verses_done:,}/{p.verses_total:,} verses"
                progress(p)
                embedded = entry.get("embedded", 0) if have else 0
                mstate[src.code] = {"signature": src.signature, "content_hash": file_hash(src.path),
                                    "verses": len(records), "complete": False, "embedded": embedded,
                                    "updated_at": time.time()}
                self._save_state(state)
                for b in range(0, len(todo), BATCH):
                    if self._cancel.is_set():
                        self._save_state(state)
                        return self._finish(p, "cancelled", progress)
                    batch = todo[b:b + BATCH]
                    # duplicate detection: reuse vectors of identical texts already embedded
                    reuse = store.vectors_for_hashes(list({r.text_hash for r in batch}))
                    need = [r for r in batch if r.text_hash not in reuse]
                    new_vecs = emb.encode_documents([r.text for r in need]) if need else []
                    fresh = dict(zip([r.text_hash for r in need], new_vecs))
                    store.upsert(batch, [reuse.get(r.text_hash) or fresh[r.text_hash] for r in batch])
                    embedded += len(need)
                    p.verses_done += len(batch)
                    mstate[src.code].update(embedded=embedded, updated_at=time.time())
                    if (b // BATCH) % 10 == 0:
                        self._save_state(state)
                    p.message = f"Embedding {src.abbr}: {p.verses_done:,}/{p.verses_total:,} verses"
                    progress(p)
                mstate[src.code].update(complete=True, updated_at=time.time())
                self._save_state(state)
                self.log.info("Embedded %s: %d verses (%d new vectors)", src.code, len(records), embedded)
            return self._finish(p, "done", progress)
        except (EmbeddingError, VectorStoreError) as exc:
            p.errors.append(str(exc))
            self.log.error("%s", exc)
            return self._finish(p, "error", progress)
        except Exception as exc:                                 # never crash the app
            p.errors.append(f"Unexpected error: {exc}")
            self.log.exception("Indexing failed")
            return self._finish(p, "error", progress)
        finally:
            self._lock.release()

    def _finish(self, p: IndexProgress, stage: str, progress) -> IndexProgress:
        p.stage = stage
        p.message = {"done": "Index is up to date.", "cancelled": "Indexing cancelled — run again to continue.",
                     "error": "Indexing stopped with errors (see log)."}.get(stage, stage)
        self.log.info("Finished: %s %s", stage, "; ".join(p.errors))
        progress(p)
        return p

    def backup(self) -> Path:
        return backup_index(self.index_dir)

    def details(self) -> list[dict]:
        """Per-database details for the 'View Database Details' dialog."""
        st = self._state().get(self.embedding_model, {})
        out = []
        for s in self.sources or self.scan():
            e = st.get(s.code, {})
            out.append({"file": s.file_name, "code": s.code, "translation": s.translation,
                        "abbr": s.abbr, "language": s.language, "lang_code": s.lang_code,
                        "format": s.adapter, "error": s.error, "selected": s.code in self.versions,
                        "indexed": bool(e.get("complete")), "verses": e.get("verses", 0)})
        return out
