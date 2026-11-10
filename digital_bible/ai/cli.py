"""Command-line tool for the AI index (useful before/without the UI).

    python -m digital_bible.ai.cli status
    python -m digital_bible.ai.cli build            # download bge-m3 if needed, index ADBTAG + KJV
    python -m digital_bible.ai.cli build --rebuild  # start the vectors from scratch
    python -m digital_bible.ai.cli search "What does the Bible say about forgiveness?"
    python -m digital_bible.ai.cli search "Ano ang sinasabi tungkol sa pagpapatawad?" --lang tl
    python -m digital_bible.ai.cli compare "John 3:16"
    python -m digital_bible.ai.cli details

Press Ctrl+C during build to cancel safely; run build again to continue.
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys

from ..library import Library
from ..reference import BookResolver
from ..settings import Settings, data_dir
from .indexer import IndexManager
from .retriever import RetrievalConfig, Retriever


def _manager(settings) -> IndexManager:
    ai = settings["ai"]
    return IndexManager(data_dir(), ai["embedding_model"], ai["indexed_versions"])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="biblepro-ai", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    sub.add_parser("details")
    b = sub.add_parser("build")
    b.add_argument("--rebuild", action="store_true")
    b.add_argument("--keywords-only", action="store_true")
    s = sub.add_parser("search")
    s.add_argument("question")
    s.add_argument("--lang", default=None, help="language code of the question, e.g. en, tl, es")
    s.add_argument("-k", type=int, default=10)
    c = sub.add_parser("compare")
    c.add_argument("reference")
    args = ap.parse_args(argv)

    settings = Settings(data_dir() / "settings.json")
    im = _manager(settings)

    if args.cmd == "status":
        st = im.status()
        when = dt.datetime.fromtimestamp(st.last_indexed).strftime("%Y-%m-%d %H:%M") if st.last_indexed else "never"
        print(f"State:              {st.state}\nEmbedding model:    {st.embedding_model}\n"
              f"Databases found:    {st.databases_found} ({st.databases_with_errors} with errors)\n"
              f"Selected versions:  {', '.join(st.selected_versions)}\n"
              f"Indexed:            {st.databases_indexed}/{st.translations} databases, "
              f"{st.languages} languages\nVerses indexed:     {st.verses_indexed:,}\n"
              f"Embeddings:         {st.embeddings:,}\nLast indexed:       {when}")
        return 0

    if args.cmd == "details":
        for d in im.details():
            if d["selected"] or d["error"]:
                print(f"{d['file']:12} {d['abbr']:9} {d['language']:10} {d['format']:22} "
                      f"indexed={d['indexed']} verses={d['verses']} {d['error']}")
        return 0

    if args.cmd == "build":
        def show(p):
            line = f"[{p.stage}] {p.message}"
            if p.stage == "embedding" and p.verses_total:
                line += f"  ({100 * p.verses_done / p.verses_total:.0f}%)"
            print("\r" + line[:110].ljust(110), end="", flush=True)
            if p.stage in ("done", "cancelled", "error"):
                print()
        try:
            res = im.build(show, rebuild=args.rebuild, embeddings=not args.keywords_only)
        except KeyboardInterrupt:
            im.cancel()
            print("\nCancelled. Run 'build' again to continue where it stopped.")
            return 1
        for e in res.errors:
            print("  ERROR:", e)
        return 0 if res.stage == "done" else 1

    lib = Library(data_dir())
    if args.cmd == "compare":
        ref = BookResolver(lib).parse(args.reference)
        ret = Retriever(lib, None, None, None, settings["ai"]["indexed_versions"])
        for v in ret.compare(ref.start_key):
            print(f"{v.abbr:10} {v.language:12} {v.reference:22} {v.text[:90]}")
        return 0

    if args.cmd == "search":
        st = im.status()
        store = emb = None
        if st.state in ("ready", "partial", "out of date") and st.embeddings:
            store, emb = im.vector_store(), im.embedder()
        cfg = RetrievalConfig(final_k=args.k, **{k: v for k, v in settings["ai"]["retrieval"].items()
                                                 if k != "final_k"})
        ret = Retriever(lib, im.keyword_index(), store, emb, settings["ai"]["indexed_versions"], cfg)
        res = ret.retrieve(args.question, args.lang)
        for n in res.notes:
            print("NOTE:", n)
        for v in res.verses:
            sim = f"{v.similarity:.2f}" if v.similarity is not None else "  - "
            print(f"{v.reference:22} {v.abbr:7} sim={sim} {'+'.join(v.methods):18} {v.text[:80]}")
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
