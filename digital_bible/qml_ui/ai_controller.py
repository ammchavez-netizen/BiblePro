"""AI Mode controller: chat, index management, embedding models, API keys.

Long-running work (indexing, model download, loading the embedding model,
searching) runs on background threads. Results come back through Qt signals
connected to methods of this object, so the QML interface never freezes and
widgets are only touched on the UI thread.

Answers are written by Google Gemini from the retrieved passages only. When
Gemini can't be used (no key, offline, quota), AI Mode still answers with the
retrieved Bible passages.
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import sys
import threading
import time
from dataclasses import asdict

from PySide6.QtCore import Property, QObject, QRect, Signal, Slot
from PySide6.QtGui import QGuiApplication

from ..ai import generator as gen
from ..ai.embeddings import EMBEDDING_MODELS, Embedder
from ..ai.indexer import IndexManager
from ..ai.language import detect_language
from ..ai.retriever import RetrievalConfig, Retriever
from ..library import split_key

KEYRING_SERVICE = "BiblePro"


def _packages() -> dict:
    names = {"chromadb": "chromadb", "sentence_transformers": "sentence-transformers", "torch": "torch",
             "lingua": "lingua-language-detector", "google.genai": "google-genai", "keyring": "keyring"}
    out = {}
    for mod, pip_name in names.items():
        try:
            out[pip_name] = importlib.util.find_spec(mod) is not None
        except (ImportError, ValueError):
            out[pip_name] = False
    return out


class _Bridge(QObject):
    """Signals emitted from worker threads (delivered on the UI thread)."""
    progress = Signal(dict)
    indexDone = Signal(dict)
    answer = Signal(int, dict)
    downloadDone = Signal(str)
    geminiDone = Signal(str, dict)


class AiController(QObject):
    statusChanged = Signal()
    progressChanged = Signal()
    chatChanged = Signal()
    busyChanged = Signal()
    settingsChanged = Signal()
    logChanged = Signal()
    keyChanged = Signal()
    geminiChanged = Signal()
    popoutChanged = Signal()
    notice = Signal(str)

    def __init__(self, library, settings, main_ctrl=None):
        super().__init__()
        self.library, self.settings, self.main = library, settings, main_ctrl
        self._bridge = _Bridge()
        self._bridge.progress.connect(self._on_progress)
        self._bridge.indexDone.connect(self._on_index_done)
        self._bridge.answer.connect(self._on_answer)
        self._bridge.downloadDone.connect(self._on_download_done)
        self._bridge.geminiDone.connect(self._on_gemini_done)
        self._gemini_busy = ""                   # "", "test", "scan"
        self._gemini_result = {}
        self._popped = False
        self._messages: list = []
        self._busy = False
        self._progress = {"running": False, "stage": "idle", "message": "", "current": "",
                          "done": 0, "total": 0, "percent": 0, "errors": []}
        self._status: dict = {}
        self._log = ""
        self._details: list = []
        self._im = None
        self._retriever = None
        self._retriever_key = None
        self._lock = threading.Lock()
        self._packages = _packages()
        self.refreshStatus()

    # ================================================================ helpers
    @property
    def ai(self) -> dict:
        return self.settings["ai"]

    def manager(self) -> IndexManager:
        key = (self.ai["embedding_model"], tuple(self.ai["indexed_versions"]))
        if self._im is None or (self._im.embedding_model, tuple(self._im.versions)) != key:
            self._im = IndexManager(self.library.data_dir, *key[:1], list(key[1]))
        return self._im

    def _save(self):
        self.settings.save()

    # ================================================================ properties
    def _get_packages(self):
        return {"ok": all(v for k, v in self._packages.items() if k not in ("google-genai", "keyring")),
                "missing": [k for k, v in self._packages.items() if not v],
                "frozen": bool(getattr(sys, "frozen", False))}      # running as BiblePro.exe
    packages = Property("QVariantMap", _get_packages, notify=statusChanged)

    def _get_status(self):
        return self._status
    indexStatus = Property("QVariantMap", _get_status, notify=statusChanged)

    def _get_progress(self):
        return self._progress
    progress = Property("QVariantMap", _get_progress, notify=progressChanged)

    def _get_messages(self):
        return self._messages
    messages = Property("QVariantList", _get_messages, notify=chatChanged)

    def _get_busy(self):
        return self._busy
    busy = Property(bool, _get_busy, notify=busyChanged)

    def _get_log(self):
        return self._log
    indexLog = Property(str, _get_log, notify=logChanged)

    def _get_details(self):
        return self._details
    databaseDetails = Property("QVariantList", _get_details, notify=logChanged)

    def _get_versions(self):
        sel = set(self.ai["indexed_versions"])
        return [{"code": v.code, "abbr": v.abbr, "name": v.name.title() if v.name.isupper() else v.name,
                 "language": v.language, "selected": v.code in sel} for v in self.library.versions]
    indexVersions = Property("QVariantList", _get_versions, notify=settingsChanged)

    def _get_embedding(self):
        cur = self.ai["embedding_model"]
        models = []
        for mid, spec in EMBEDDING_MODELS.items():
            if spec.kind == "hashing":
                continue
            emb = Embedder(mid, self.library.data_dir / "models")
            models.append({"id": mid, "name": spec.display_name, "dim": spec.dim,
                           "gb": spec.approx_download_gb, "multilingual": spec.multilingual,
                           "downloaded": emb.is_downloaded(), "current": mid == cur})
        spec = EMBEDDING_MODELS.get(cur)
        return {"current": cur, "name": spec.display_name if spec else cur,
                "downloaded": Embedder(cur, self.library.data_dir / "models").is_downloaded() if spec else False,
                "models": models}
    embedding = Property("QVariantMap", _get_embedding, notify=settingsChanged)

    def _get_retrieval(self):
        return dict(self.ai["retrieval"])
    retrieval = Property("QVariantMap", _get_retrieval, notify=settingsChanged)

    def _gemini_ready(self) -> bool:
        return bool(self._packages.get("google-genai")) and bool(self._read_key())

    def _get_generation(self):
        model = self.ai.get("model") or gen.DEFAULT_MODEL
        models = list(self.ai.get("models_cache") or [])
        if not any(m.get("id") == model for m in models):
            models = [{"id": model, "name": model, "description": "", "input": 0, "output": 0}] + models
        if not self._packages.get("google-genai"):
            note = "Install the AI components (requirements-ai.txt) to get AI-written answers."
        elif not self._read_key():
            note = "Add a Gemini API key to get AI-written answers. Without it, AI Mode shows the passages it finds."
        else:
            note = "Answers are written by Gemini using only the Bible passages BiblePro finds. Only your question and those passages are sent to Google."
        return {"provider": self.ai.get("provider", "gemini"), "model": model, "models": models,
                "enabled": bool(self.ai.get("answers_enabled", True)),
                "available": self._gemini_ready(), "note": note,
                "busy": self._gemini_busy, "result": self._gemini_result,
                "scanned": self.ai.get("models_scanned", "")}
    generation = Property("QVariantMap", _get_generation, notify=geminiChanged)

    # ================================================================ status / logs
    @Slot()
    def refreshStatus(self):
        def work():
            try:
                st = asdict(self.manager().status())
                st["last_indexed_text"] = (dt.datetime.fromtimestamp(st["last_indexed"]).strftime("%b %d, %Y %I:%M %p")
                                           if st.get("last_indexed") else "Never")
            except Exception as exc:
                st = {"state": "error", "error": str(exc)}
            self._status = st
            self.statusChanged.emit()
        work()

    @Slot()
    def refreshLog(self):
        try:
            self._log = self.manager().log_text() or "(no log entries yet)"
            self._details = self.manager().details()
        except Exception as exc:
            self._log = f"Could not read log: {exc}"
        self.logChanged.emit()

    # ================================================================ indexing
    @Slot()
    def scanDatabases(self):
        self._start_index(scan_only=True)

    @Slot()
    def buildIndex(self):
        self._start_index()

    @Slot()
    def rebuildIndex(self):
        self._start_index(rebuild=True)

    @Slot()
    def cancelIndex(self):
        if self._im is not None:
            self._im.cancel()

    def _start_index(self, rebuild=False, scan_only=False):
        if self._progress["running"]:
            return
        im = self.manager()
        self._retriever = None                   # reload after indexing
        self._progress = {"running": True, "stage": "scanning", "message": "Starting…", "current": "",
                          "done": 0, "total": 0, "percent": 0, "errors": []}
        self.progressChanged.emit()

        def report(p):
            self._bridge.progress.emit({
                "running": p.stage not in ("done", "cancelled", "error"), "stage": p.stage,
                "message": p.message, "current": p.current_db, "done": p.verses_done,
                "total": p.verses_total,
                "percent": int(100 * p.verses_done / p.verses_total) if p.verses_total else 0,
                "errors": list(p.errors)})

        def work():
            try:
                if scan_only:
                    srcs = im.scan()
                    res = {"stage": "done", "message": f"Found {len(srcs)} Bible databases "
                                                       f"({sum(bool(s.error) for s in srcs)} with errors).",
                           "errors": [f"{s.file_name}: {s.error}" for s in srcs if s.error]}
                else:
                    p = im.build(report, rebuild=rebuild, embeddings=self._get_packages()["ok"])
                    res = {"stage": p.stage, "message": p.message, "errors": p.errors}
                    if not self._get_packages()["ok"] and p.stage == "done":
                        res["message"] = ("Keyword index is up to date. Install the AI components "
                                          "(requirements-ai.txt) to build the meaning index.")
            except Exception as exc:
                res = {"stage": "error", "message": str(exc), "errors": [str(exc)]}
            self._bridge.indexDone.emit(res)

        threading.Thread(target=work, daemon=True, name="biblepro-index").start()

    @Slot(dict)
    def _on_progress(self, p):
        self._progress = p
        self.progressChanged.emit()

    @Slot(dict)
    def _on_index_done(self, res):
        self._progress = {"running": False, "stage": res["stage"], "message": res["message"], "current": "",
                          "done": 0, "total": 0, "percent": 100 if res["stage"] == "done" else 0,
                          "errors": res.get("errors", [])}
        self.progressChanged.emit()
        self.refreshStatus()
        self.refreshLog()
        self.notice.emit(res["message"])

    @Slot()
    def backupIndex(self):
        try:
            dest = self.manager().backup()
            self.notice.emit(f"Index backed up to {dest}")
        except Exception as exc:
            self.notice.emit(f"Backup failed: {exc}")

    @Slot(str, bool)
    def setIndexedVersion(self, code: str, on: bool):
        sel = [c for c in self.ai["indexed_versions"] if c != code]
        if on:
            sel.append(code)
        self.ai["indexed_versions"] = sorted(sel)
        self._save()
        self.settingsChanged.emit()
        self.refreshStatus()

    # ================================================================ embedding model
    @Slot(str)
    def setEmbeddingModel(self, model_id: str):
        if model_id in EMBEDDING_MODELS and model_id != self.ai["embedding_model"]:
            self.ai["embedding_model"] = model_id
            self._retriever = None
            self._save()
            self.settingsChanged.emit()
            self.refreshStatus()
            self.notice.emit("Embedding model changed. Build the index to create vectors for this model.")

    @Slot(str)
    def downloadModel(self, model_id: str):
        if self._progress["running"]:
            return
        self._progress = {"running": True, "stage": "downloading", "message": f"Downloading {model_id}…",
                          "current": "", "done": 0, "total": 0, "percent": 0, "errors": []}
        self.progressChanged.emit()

        def report(m):
            self._bridge.progress.emit({"running": True, "stage": "downloading", "message": m, "current": "",
                                        "done": 0, "total": 0, "percent": 0, "errors": []})

        def work():
            try:
                Embedder(model_id, self.library.data_dir / "models").download(report)
                msg = f"{model_id} downloaded."
            except Exception as exc:
                msg = f"Download failed: {exc}"
            self._bridge.downloadDone.emit(msg)
        threading.Thread(target=work, daemon=True, name="biblepro-download").start()

    @Slot(str)
    def _on_download_done(self, msg):
        failed = msg.startswith("Download failed")
        self._progress = {"running": False, "stage": "error" if failed else "done", "message": msg,
                          "current": "", "done": 0, "total": 0, "percent": 0 if failed else 100,
                          "errors": [msg] if failed else []}
        self.progressChanged.emit()
        self.settingsChanged.emit()
        self.notice.emit(msg)

    # ================================================================ retrieval settings
    @Slot(str, float)
    def setRetrieval(self, key: str, value: float):
        if key in ("final_k", "keyword_k", "dense_k"):
            value = int(value)
        self.ai["retrieval"][key] = value
        self._retriever = None
        self._save()
        self.settingsChanged.emit()

    # ================================================================ API key (Windows Credential Manager)
    def _keyring(self):
        try:
            import keyring
            return keyring
        except ImportError:
            return None

    def _read_key(self) -> str:
        kr = self._keyring()
        if kr is None:
            return ""
        try:
            return kr.get_password(KEYRING_SERVICE, "gemini_api_key") or ""
        except Exception:
            return ""

    def _get_key_info(self):
        kr = self._keyring()
        if kr is None:
            return {"available": False, "set": False, "masked": ""}
        try:
            key = kr.get_password(KEYRING_SERVICE, "gemini_api_key") or ""
        except Exception:
            key = ""
        masked = (key[:4] + "•" * 12 + key[-4:]) if len(key) > 10 else ("•" * len(key))
        return {"available": True, "set": bool(key), "masked": masked}
    apiKey = Property("QVariantMap", _get_key_info, notify=keyChanged)

    @Slot(result=str)
    def revealApiKey(self) -> str:
        kr = self._keyring()
        try:
            return (kr.get_password(KEYRING_SERVICE, "gemini_api_key") or "") if kr else ""
        except Exception:
            return ""

    @Slot(str)
    def saveApiKey(self, key: str):
        kr = self._keyring()
        key = key.strip()
        if kr is None:
            self.notice.emit("Secure key storage is unavailable (install 'keyring').")
            return
        try:
            if key:
                kr.set_password(KEYRING_SERVICE, "gemini_api_key", key)
                self.notice.emit("API key saved in Windows Credential Manager.")
                self._gemini_result = {}
            self.keyChanged.emit()
            self.geminiChanged.emit()
        except Exception as exc:
            self.notice.emit(f"Could not save the key: {type(exc).__name__}")

    @Slot()
    def clearApiKey(self):
        kr = self._keyring()
        try:
            if kr:
                kr.delete_password(KEYRING_SERVICE, "gemini_api_key")
        except Exception:
            pass
        self._gemini_result = {}
        self.keyChanged.emit()
        self.geminiChanged.emit()
        self.notice.emit("API key removed.")

    # ================================================================ Gemini: test / scan / choose model
    @Slot()
    def testConnection(self):
        self._gemini_task("test")

    @Slot()
    def scanModels(self):
        self._gemini_task("scan")

    def _gemini_task(self, what: str):
        if self._gemini_busy:
            return
        self._gemini_busy = what
        self._gemini_result = {}
        self.geminiChanged.emit()
        key, model = self._read_key(), self.ai.get("model") or gen.DEFAULT_MODEL

        def work():
            res: dict = {}
            try:
                client = gen.GeminiClient(key)
                if what == "scan":
                    models = client.list_models()
                    res = {"ok": True, "models": [{"id": m.id, "name": m.display_name, "description": m.description,
                                                   "input": m.input_limit, "output": m.output_limit} for m in models]}
                else:
                    res = client.test(model)
            except gen.GeminiError as exc:
                res = {"ok": False, "kind": exc.kind, "message": exc.message}
            except Exception as exc:
                err = gen.classify(exc, key)
                res = {"ok": False, "kind": err.kind, "message": err.message}
            self._bridge.geminiDone.emit(what, res)

        threading.Thread(target=work, daemon=True, name=f"biblepro-gemini-{what}").start()

    @Slot(str, dict)
    def _on_gemini_done(self, what, res):
        self._gemini_busy = ""
        if what == "scan" and res.get("ok"):
            self.ai["models_cache"] = res["models"]
            self.ai["models_scanned"] = dt.datetime.now().strftime("%b %d, %Y %I:%M %p")
            self._save()
            cur = self.ai.get("model")
            ids = [m["id"] for m in res["models"]]
            msg = f"Found {len(ids)} Gemini models that can write answers."
            if cur not in ids and ids:
                msg += f" “{cur}” isn't one of them; choose a model from the list."
            self._gemini_result = {"ok": True, "what": "scan", "message": msg}
        elif what == "test" and res.get("ok"):
            if res.get("model_available"):
                msg = (f"Connected. {res['model']} answered in {res['seconds']} s "
                       f"({res['models']} models available to this key).")
            else:
                msg = (f"The API key works ({res['models']} models available), but “{res['model']}” isn't one "
                       f"of them. Click Scan Available Models and choose another.")
            self._gemini_result = {"ok": bool(res.get("model_available")), "what": "test", "message": msg}
        else:
            self._gemini_result = {"ok": False, "what": what, "message": res.get("message", "Failed."),
                                   "kind": res.get("kind", "other")}
        self.geminiChanged.emit()
        self.notice.emit(self._gemini_result["message"])

    @Slot(str)
    def setModel(self, model_id: str):
        model_id = (model_id or "").strip()
        if model_id and model_id != self.ai.get("model"):
            self.ai["model"] = model_id
            self._gemini_result = {}
            self._save()
            self.geminiChanged.emit()
            self.notice.emit(f"AI answers will use {model_id}.")

    @Slot(bool)
    def setAnswersEnabled(self, on: bool):
        self.ai["answers_enabled"] = bool(on)
        self._save()
        self.geminiChanged.emit()

    # ================================================================ chat pop-out window
    def _get_popped(self):
        return self._popped
    chatPoppedOut = Property(bool, _get_popped, notify=popoutChanged)

    @Slot(bool)
    def setChatPoppedOut(self, on: bool):
        if bool(on) != self._popped:
            self._popped = bool(on)
            self.popoutChanged.emit()

    @Slot(QObject, QObject)
    def dockWindow(self, chat_win, main_win):
        """Give the chat window the main window's size and put it right beside it.

        Uses frame geometry (title bar + borders) so the two windows touch without
        overlapping. If there is no screen to the right, it tries the left side,
        and otherwise keeps it on the main window's screen."""
        try:
            mf = main_win.frameGeometry()
            mg = main_win.geometry()
            cf, cg = chat_win.frameGeometry(), chat_win.geometry()
            # chat frame margins (fall back to the main window's when not shown yet)
            if cf.width() > cg.width():
                ml, mt = cg.x() - cf.x(), cg.y() - cf.y()
                mr, mb = cf.right() - cg.right(), cf.bottom() - cg.bottom()
            else:
                ml, mt = mg.x() - mf.x(), mg.y() - mf.y()
                mr, mb = mf.right() - mg.right(), mf.bottom() - mg.bottom()
            # Windows 10/11 frames include ~7px invisible borders on left/right/bottom
            overlap = 2 * min(ml, mr) if min(ml, mr) <= 10 else 0
            w, h = mg.width(), mg.height()

            def fits(frame_x):
                # at least 90% of the window must be on screens (it may span two monitors)
                r = QRect(frame_x, mf.y(), mf.width(), mf.height())
                seen = 0
                for scr in QGuiApplication.screens():
                    part = scr.availableGeometry().intersected(r)
                    if not part.isEmpty():
                        seen += part.width() * part.height()
                return seen >= 0.9 * r.width() * r.height()

            right = mf.x() + mf.width() - overlap
            left = mf.x() - mf.width() + overlap
            if fits(right):
                fx = right
            elif fits(left):
                fx = left
            else:
                scr = main_win.screen() or QGuiApplication.primaryScreen()
                avail = scr.availableGeometry()
                fx = max(avail.x(), avail.x() + avail.width() - mf.width())
            chat_win.setGeometry(fx + ml, mf.y() + mt, w, h)
        except Exception:
            pass

    # ================================================================ chat
    @Slot(str)
    def ask(self, question: str):
        question = question.strip()
        if not question or self._busy:
            return
        self._messages = self._messages + [{"role": "user", "text": question, "sources": [], "notes": []}]
        idx = len(self._messages)
        self._messages = self._messages + [{"role": "assistant", "text": "", "pending": True,
                                             "sources": [], "notes": [], "language": ""}]
        self.chatChanged.emit()
        self._set_busy(True)
        history = [(self._messages[i - 1]["text"], self._messages[i].get("plain", self._messages[i]["text"]))
                   for i in range(1, idx - 1)
                   if self._messages[i]["role"] == "assistant" and self._messages[i].get("mode") == "ai"
                   and self._messages[i - 1]["role"] == "user"]

        def work():
            try:
                lang = detect_language(question)
                ret = self._get_retriever()
                res = ret.retrieve(question, lang.code if lang else None)
                sources = [{"key": v.key, "code": v.code, "abbr": v.abbr, "translation": v.translation,
                            "language": v.language, "reference": v.reference, "text": v.text,
                            "methods": v.methods,
                            "similarity": round(v.similarity, 2) if v.similarity is not None else None}
                           for v in res.verses]
                out = self._compose(question, lang, sources, res.notes, history)
            except Exception as exc:
                out = {"role": "assistant", "text": f"Something went wrong while searching: {exc}",
                       "sources": [], "notes": [], "language": "", "pending": False, "error": True}
            self._bridge.answer.emit(idx, out)

        threading.Thread(target=work, daemon=True, name="biblepro-ask").start()

    def _compose(self, question, lang, sources, notes, history) -> dict:
        """Ask Gemini to answer from `sources`, or fall back to listing the passages."""
        notes = list(notes)
        base = {"role": "assistant", "sources": sources, "cited": [], "notes": notes,
                "language": lang.name if lang else "", "pending": False, "mode": "passages", "model": ""}
        if not sources:
            return {**base, "text": "No matching passages were found in the indexed Bibles, so there is "
                                    "nothing to answer from. Try different words or a Bible reference."}
        use_ai = self.ai.get("answers_enabled", True)
        key = self._read_key() if use_ai else ""
        reason = ""
        if not use_ai:
            reason = "AI-written answers are turned off in Settings."
        elif not self._packages.get("google-genai"):
            reason = gen.FRIENDLY["no_package"]
        elif not key:
            reason = gen.FRIENDLY["no_key"]
        else:
            model = self.ai.get("model") or gen.DEFAULT_MODEL
            try:
                client = gen.GeminiClient(key)
                checked = gen.answer(client, model, question, lang.name if lang else None, sources, history)
                if checked.invalid:
                    notes.append("Removed citation(s) that didn't match a retrieved passage: "
                                 + ", ".join(sorted(set(checked.invalid))))
                if not checked.cited:
                    notes.append("The answer didn't cite specific passages; the passages it was given are listed below.")
                return {**base, "mode": "ai", "model": model, "cited": checked.cited, "notes": notes,
                        "plain": checked.text, "text": gen.link_citations(checked.text, sources)}
            except gen.GeminiError as exc:
                reason = exc.message
            except Exception as exc:
                reason = gen.classify(exc, key).message
        n = len(sources)
        text = (f"I found {n} relevant passage{'s' if n != 1 else ''} in the indexed Bibles (below)."
                + (f"\n\n*No AI-written answer: {reason}*" if reason else ""))
        return {**base, "text": text}

    def _get_retriever(self) -> Retriever:
        with self._lock:
            ai = self.ai
            key = (ai["embedding_model"], tuple(ai["indexed_versions"]), tuple(sorted(ai["retrieval"].items())))
            if self._retriever is not None and self._retriever_key == key:
                return self._retriever
            im = self.manager()
            # The keyword index is tiny and builds in about a second: keep it current automatically,
            # so AI Mode can answer (with keyword + reference search) even before "Build Index".
            try:
                kw = im.keyword_index()
                kw.update([s for s in (im.sources or im.scan()) if s.code in ai["indexed_versions"]],
                          keep_codes=set(ai["indexed_versions"]))
                kw.close()
            except Exception:
                pass
            st = im.status()
            store = emb = None
            pk = self._get_packages()
            if not pk["ok"]:
                reason = ("meaning-based search isn't included in BiblePro.exe — start BiblePro with run.bat for it"
                          if pk["frozen"] else
                          "the AI components aren't installed (pip install -r requirements-ai.txt)")
            elif not st.embeddings:
                reason = "the meaning index hasn't been built yet (AI Mode → Settings → Build Index)"
            else:
                reason = ""
                try:
                    store, emb = im.vector_store(), im.embedder()
                except Exception as exc:
                    store = emb = None
                    reason = f"the embedding model couldn't be loaded ({type(exc).__name__})"
            cfg = RetrievalConfig(**{k: v for k, v in ai["retrieval"].items()
                                     if k in RetrievalConfig.__dataclass_fields__},
                                  preferred_codes=tuple(ai["indexed_versions"]))
            self._retriever = Retriever(self.library, im.keyword_index(), store, emb,
                                        ai["indexed_versions"], cfg)
            if reason:
                self._retriever.dense_off_reason = reason
            self._retriever_key = key
            return self._retriever

    @Slot(int, dict)
    def _on_answer(self, idx, out):
        msgs = list(self._messages)
        if 0 <= idx < len(msgs):
            msgs[idx] = out
        self._messages = msgs
        self.chatChanged.emit()
        self._set_busy(False)

    def _set_busy(self, on):
        self._busy = on
        self.busyChanged.emit()

    @Slot()
    def clearChat(self):
        if not self._busy:
            self._messages = []
            self.chatChanged.emit()

    @Slot(int, str)
    def openVerse(self, key: int, code: str):
        if self.main is not None:
            self.main.showKeyIn(key, code)

    @Slot(int, result="QVariantList")
    def compare(self, key: int):
        ret = Retriever(self.library, None, None, None, self.ai["indexed_versions"])
        return [{"abbr": v.abbr, "language": v.language, "reference": v.reference, "text": v.text,
                 "code": v.code} for v in ret.compare(key)]
