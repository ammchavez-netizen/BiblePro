"""AI Mode backend for BiblePro.

Layers (each usable on its own, none of them touches the original Bible files):

    sources.py        find Bible databases, read them through schema adapters,
                      produce normalized VerseRecord objects
    keyword_index.py  SQLite FTS5 full-text index (names, places, exact phrases)
    embeddings.py     local embedding models (default BAAI/bge-m3)        [phase 3]
    vector_store.py   persistent ChromaDB vector index                    [phase 3]
    indexer.py        background, incremental, cancellable indexing        [phase 3]
    retriever.py      hybrid retrieval: references + keywords + meaning    [phase 3]

Everything the AI layer writes lives in  data/index/ .
"""

DEFAULT_INDEXED_VERSIONS = ["001", "002"]     # Ang Dating Biblia, King James Version
