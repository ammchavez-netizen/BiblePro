"""BibleQ-AI.exe --selftest : check that the AI parts work inside a built .exe.

Writes a short report to data/selftest.txt (the .exe has no console) and returns
0 when meaning-based search works, 1 otherwise. build_exe_full.bat runs it after
building and shows the report.
"""
from __future__ import annotations

import importlib
import time
import traceback

from .settings import Settings, data_dir


def run() -> int:
    lines: list[str] = []
    ok = True

    def check(name: str, fn):
        nonlocal ok
        t0 = time.perf_counter()
        try:
            detail = fn() or ""
            lines.append(f"[ OK ] {name} {detail} ({time.perf_counter() - t0:.1f} s)")
            return True
        except Exception as exc:
            ok = False
            lines.append(f"[FAIL] {name}: {type(exc).__name__}: {exc}")
            lines.append("       " + traceback.format_exc().strip().splitlines()[-1])
            return False

    for mod in ("torch", "sentence_transformers", "transformers", "chromadb", "lingua",
                "google.genai", "keyring"):
        check(f"import {mod}", lambda m=mod: (getattr(importlib.import_module(m), "__version__", ""),)[0])

    def keyring_backend():
        import keyring
        return type(keyring.get_keyring()).__name__

    check("Windows Credential Manager (keyring backend)", keyring_backend)

    def language():
        from .ai.language import detect_language
        lang = detect_language("Ano ang sinasabi ng Bibliya tungkol sa pag-ibig?")
        return lang.name if lang else "(none)"

    check("language detection", language)

    settings = Settings(data_dir() / "settings.json")
    ai = settings["ai"]
    from .ai.embeddings import Embedder
    emb = Embedder(ai["embedding_model"], data_dir() / "models")
    if not emb.is_downloaded():
        ok = False
        lines.append(f"[SKIP] {ai['embedding_model']} is not in data\\models (copy it there or download it in "
                     f"AI Mode Settings).")
    else:
        vec = []

        def encode():
            vec.extend(emb.encode_query("God's love for the world"))
            return f"({len(vec)} numbers)"

        if check(f"embedding model {ai['embedding_model']}", encode):
            def search():
                from .ai.embeddings import EMBEDDING_MODELS
                from .ai.vector_store import VectorStore
                spec = EMBEDDING_MODELS[ai["embedding_model"]]
                store = VectorStore(data_dir() / "index" / "chroma", spec.model_id, spec.dim)
                n = store.count()
                if n == 0:
                    return "(index is empty: run Build Index)"
                hits = store.query(vec, 3)
                return f"({n:,} verses indexed; best match key {hits[0].key if hits else '-'})"

            check("meaning-based search (ChromaDB)", search)

    lines.insert(0, "BibleQ-AI self-test: " + ("PASSED" if ok else "PROBLEMS FOUND"))
    report = "\n".join(lines) + "\n"
    try:
        (data_dir() / "selftest.txt").write_text(report, encoding="utf-8")
    except OSError:
        pass
    print(report)
    return 0 if ok else 1
