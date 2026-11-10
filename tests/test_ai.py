"""AI layer tests. Use the offline 'test/hashing' embedder, so no model download is needed.

Run:  python -m pytest tests   (needs an imported data/ folder)
"""
import hashlib
import shutil
from pathlib import Path

import pytest

DATA = Path(__file__).resolve().parent.parent / "data"
pytestmark = pytest.mark.skipif(not (DATA / "catalog.sqlite").exists(), reason="run the import first")
chromadb = pytest.importorskip("chromadb")

from digital_bible.ai.indexer import IndexManager                          # noqa: E402
from digital_bible.ai.keyword_index import build_match_query                 # noqa: E402
from digital_bible.ai.retriever import RetrievalConfig, Retriever           # noqa: E402
from digital_bible.ai.sources import discover_sources, iter_verses          # noqa: E402
from digital_bible.ai.vector_store import VectorStore, VectorStoreError     # noqa: E402
from digital_bible.library import Library                                   # noqa: E402


@pytest.fixture(scope="module")
def workdir(tmp_path_factory):
    d = tmp_path_factory.mktemp("ai")
    (d / "bibles").mkdir()
    for code in ("001", "002"):
        shutil.copy(DATA / "bibles" / f"{code}.sqlite", d / "bibles")
    shutil.copy(DATA / "catalog.sqlite", d)
    return d


def _md5(p):
    return hashlib.md5(Path(p).read_bytes()).hexdigest()


def test_discovery_reads_without_modifying(workdir):
    before = {p: _md5(p) for p in (workdir / "bibles").glob("*.sqlite")}
    srcs = discover_sources(workdir)
    assert {s.code for s in srcs} == {"001", "002"} and not any(s.error for s in srcs)
    rec = next(r for r in iter_verses(srcs[0]) if r.key == 43003016)
    assert rec.book_id == "John" and rec.lang_code in ("tl", "en") and rec.text
    assert before == {p: _md5(p) for p in (workdir / "bibles").glob("*.sqlite")}


def test_stopwords_removed():
    assert build_match_query("What does the Bible say about forgiveness?") == '"forgive"*'


def test_build_cancel_resume_and_skip(workdir):
    im = IndexManager(workdir, "test/hashing", ["001", "002"])

    def stop_early(p):
        if p.stage == "embedding" and p.verses_done >= 1000:
            im.cancel()
    assert im.build(stop_early).stage == "cancelled"
    assert im.status().state == "partial"
    assert im.build().stage == "done"
    st = im.status()
    assert st.state == "ready" and st.databases_indexed == 2 and st.verses_indexed == 62206
    assert im.vector_store().count() == 62206
    assert im.build().stage == "done"                     # nothing to do second time
    with pytest.raises(VectorStoreError):
        VectorStore(workdir / "index" / "chroma", "test/hashing", 999)


def test_retrieval_references_and_keywords(workdir):
    im = IndexManager(workdir, "test/hashing", ["001", "002"])
    lib = Library(workdir)
    ret = Retriever(lib, im.keyword_index(), im.vector_store(), im.embedder(), ["001", "002"],
                    RetrievalConfig(final_k=10))
    r = ret.retrieve("Explain Romans 8:28", "en")
    assert r.verses[0].key == 45008028 and r.verses[0].abbr == "KJV"
    r = ret.retrieve("Ipaliwanag ang Juan 3:16", "tl")
    assert r.verses[0].key == 43003016 and r.verses[0].abbr == "ADBTAG"
    r = ret.retrieve("Nebuchadnezzar dream", "en")
    assert any(v.key // 1_000_000 == 27 for v in r.verses)          # Daniel
