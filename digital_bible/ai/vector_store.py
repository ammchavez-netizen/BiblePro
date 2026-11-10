"""Persistent local vector index (ChromaDB) in data/index/chroma.

* One collection per embedding model, so vectors from different models are
  never mixed. Changing the model means building that model's collection.
* Record id = "<version code>:<verse key>"; re-adding is an upsert, so
  interrupted indexing can simply continue.
* Metadata on every record allows filtering by translation and language.
"""
from __future__ import annotations

import re
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from .sources import VerseRecord


class VectorStoreError(RuntimeError):
    pass


def collection_name(model_id: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", model_id).strip("_")
    return f"verses__{slug}"[:60]


@dataclass
class VectorHit:
    code: str
    key: int
    score: float            # cosine similarity, 1 = identical meaning
    text: str


class VectorStore:
    def __init__(self, path: Path, model_id: str, dim: int):
        try:
            import chromadb
            from chromadb.config import Settings as ChromaSettings
        except ImportError as exc:
            raise VectorStoreError("Missing package 'chromadb'. Run: pip install -r requirements-ai.txt") from exc
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True)
        self.model_id, self.dim = model_id, dim
        try:
            self.client = chromadb.PersistentClient(
                path=str(self.path), settings=ChromaSettings(anonymized_telemetry=False))
            self.col = self.client.get_or_create_collection(
                collection_name(model_id),
                metadata={"hnsw:space": "cosine", "embedding_model": model_id, "dim": dim},
                embedding_function=None)
        except Exception as exc:
            raise VectorStoreError(f"Vector index could not be opened (it may be damaged; "
                                   f"use Rebuild Index): {exc}") from exc
        meta = self.col.metadata or {}
        if meta.get("embedding_model", model_id) != model_id or int(meta.get("dim", dim)) != dim:
            raise VectorStoreError("This index was built with a different embedding model.")

    # ------------------------------------------------------------ write
    def upsert(self, records: list[VerseRecord], vectors: list[list[float]]):
        if not records:
            return
        self.col.upsert(
            ids=[r.uid for r in records],
            embeddings=vectors,
            documents=[r.text for r in records],
            metadatas=[{
                "code": r.code, "key": r.key, "book": r.book, "chapter": r.chapter,
                "verse": r.verse, "book_id": r.book_id, "lang": r.lang_code,
                "translation": r.translation, "abbr": r.abbr, "hash": r.text_hash,
                "file": r.source_file,
            } for r in records])

    def existing_ids(self, code: str) -> set[str]:
        out, offset = set(), 0
        while True:
            got = self.col.get(where={"code": code}, include=[], limit=5000, offset=offset)
            out.update(got["ids"])
            if len(got["ids"]) < 5000:
                return out
            offset += 5000

    def vectors_for_hashes(self, hashes: list[str]) -> dict[str, list[float]]:
        """Reuse vectors of identical texts already embedded (duplicate detection)."""
        out = {}
        for i in range(0, len(hashes), 500):
            got = self.col.get(where={"hash": {"$in": hashes[i:i + 500]}}, include=["embeddings", "metadatas"])
            for emb, meta in zip(got["embeddings"], got["metadatas"]):
                out.setdefault(meta["hash"], list(emb))
        return out

    def delete_code(self, code: str):
        self.col.delete(where={"code": code})

    # ------------------------------------------------------------ read
    def count(self, code: Optional[str] = None) -> int:
        if code is None:
            return self.col.count()
        return len(self.existing_ids(code))

    def query(self, vector: list[float], k: int = 50, codes: Optional[Iterable[str]] = None,
              langs: Optional[Iterable[str]] = None) -> list[VectorHit]:
        where = []
        if codes:
            where.append({"code": {"$in": list(codes)}})
        if langs:
            where.append({"lang": {"$in": list(langs)}})
        flt = None if not where else (where[0] if len(where) == 1 else {"$and": where})
        n = self.col.count()
        if n == 0:
            return []
        res = self.col.query(query_embeddings=[vector], n_results=min(k, n), where=flt,
                             include=["metadatas", "documents", "distances"])
        return [VectorHit(m["code"], int(m["key"]), 1.0 - float(d), doc)
                for m, d, doc in zip(res["metadatas"][0], res["distances"][0], res["documents"][0])]

    # ------------------------------------------------------------ maintenance
    def drop(self):
        self.client.delete_collection(self.col.name)


def backup_index(index_dir: Path) -> Path:
    """Copy data/index (vectors + keyword index + state) to data/index_backups/<time>."""
    index_dir = Path(index_dir)
    dest = index_dir.parent / "index_backups" / time.strftime("%Y%m%d-%H%M%S")
    shutil.copytree(index_dir, dest)
    return dest


def restore_index(backup_dir: Path, index_dir: Path):
    index_dir = Path(index_dir)
    if index_dir.exists():
        shutil.rmtree(index_dir)
    shutil.copytree(backup_dir, index_dir)
