"""Gemini integration: error handling, citation checking and the answer flow.

These tests never contact Google: the Gemini calls are replaced by fakes.
"""
import pytest

from digital_bible.ai import generator as gen

SOURCES = [
    {"key": 43003016, "code": "002", "abbr": "KJV", "language": "English", "reference": "JOHN 3:16",
     "text": "For God so loved the world, that he gave his only begotten Son...", "methods": ["keyword"],
     "similarity": None, "translation": "King James Version"},
    {"key": 62004008, "code": "002", "abbr": "KJV", "language": "English", "reference": "1 JOHN 4:8",
     "text": "He that loveth not knoweth not God; for God is love.", "methods": ["semantic"],
     "similarity": 0.71, "translation": "King James Version"},
]


def test_citations_valid_invalid_and_grouped():
    text = "God loves the world [V1]. God is love [V2, V5]. Also [V9] and [v1][V2]."
    c = gen.validate_citations(text, 2)
    assert c.cited == [1, 2]
    assert sorted(set(c.invalid)) == ["V5", "V9"]
    assert "[V9]" not in c.text and "[V5]" not in c.text
    assert "God is love [V2]." in c.text


def test_link_citations_markdown():
    assert gen.link_citations("Loved [V1].", SOURCES) == "Loved ([John 3:16 · KJV](cite:1))."
    assert gen.link_citations("Love [V1][V2]", SOURCES) == \
        "Love ([John 3:16 · KJV](cite:1); [1 John 4:8 · KJV](cite:2))"


def test_nice_reference():
    assert gen.nice_reference("II TIMOTHY 3:4") == "II Timothy 3:4"
    assert gen.nice_reference("1 JOHN 4:8") == "1 John 4:8"
    assert gen.nice_reference("Juan 3:16") == "Juan 3:16"


def test_prompt_contains_only_question_and_passages():
    p = gen.build_prompt("What is love?", gen.make_passages(SOURCES), [("Earlier q", "Earlier a")])
    assert "[V1] JOHN 3:16 (KJV, English)" in p and "[V2] 1 JOHN 4:8" in p
    assert p.rstrip().endswith("User question: What is love?")
    assert "Tagalog" in gen.system_prompt("Tagalog")
    assert "same language" in gen.system_prompt(None)


@pytest.mark.parametrize("code,body,kind", [
    (400, {"error": {"message": "API key not valid. Please pass a valid API key.", "status": "INVALID_ARGUMENT"}}, "invalid_key"),
    (403, {"error": {"message": "Permission denied", "status": "PERMISSION_DENIED"}}, "permission"),
    (404, {"error": {"message": "models/x is not found", "status": "NOT_FOUND"}}, "model_not_found"),
    (429, {"error": {"message": "Quota exceeded", "status": "RESOURCE_EXHAUSTED"}}, "rate_limit"),
    (503, {"error": {"message": "overloaded", "status": "UNAVAILABLE"}}, "server"),
])
def test_classify_api_errors(code, body, kind):
    from google.genai import errors
    cls = errors.ClientError if code < 500 else errors.ServerError
    assert gen.classify(cls(code, body)).kind == kind


def test_classify_network_and_key_scrub():
    import httpx
    assert gen.classify(httpx.ConnectError("getaddrinfo failed")).kind == "network"
    assert gen.classify(TimeoutError()).kind == "network"
    err = gen.classify(RuntimeError("bad key=AIzaSyA1234567890abcdefghijklmnop"), "AIzaSyA1234567890abcdefghijklmnop")
    assert "AIzaSy" not in err.message


def test_no_key():
    with pytest.raises(gen.GeminiError) as e:
        gen.GeminiClient("")
    assert e.value.kind == "no_key"


def test_answer_flow_with_fake_model():
    seen = {}

    def fake(model, prompt, system=""):
        seen.update(model=model, prompt=prompt, system=system)
        return "Ang Diyos ay pag-ibig [V2] at inibig niya ang sanlibutan [V1][V7]."

    c = gen.answer(None, "gemini-test", "Ano ang pag-ibig ng Diyos?", "Tagalog", SOURCES, generate=fake)
    assert c.cited == [2, 1] and c.invalid == ["V7"]
    assert "Tagalog" in seen["system"] and "Ano ang pag-ibig" in seen["prompt"]


def test_controller_compose(monkeypatch):
    """AiController._compose: AI answer when a key exists, passages fallback otherwise."""
    from types import SimpleNamespace
    from digital_bible.qml_ui.ai_controller import AiController

    class FakeClient:
        def __init__(self, key, timeout_s=60):
            if key == "offline":
                raise gen.GeminiError("network", gen.FRIENDLY["network"])

        def generate(self, model, prompt, system=""):
            return "God is love [V2]."

    monkeypatch.setattr(gen, "GeminiClient", FakeClient)
    ctl = AiController.__new__(AiController)
    ctl.settings = {"ai": {"model": "gemini-test", "answers_enabled": True}}
    ctl._packages = {"google-genai": True}
    lang = SimpleNamespace(name="English", code="en")

    ctl._read_key = lambda: "k"
    out = ctl._compose("What is God?", lang, SOURCES, [], [])
    assert out["mode"] == "ai" and out["cited"] == [2]
    assert "(cite:2)" in out["text"] and out["plain"] == "God is love [V2]."

    ctl._read_key = lambda: "offline"
    out = ctl._compose("What is God?", lang, SOURCES, [], [])
    assert out["mode"] == "passages" and "internet" in out["text"] and out["sources"] == SOURCES

    ctl._read_key = lambda: ""
    assert "No Gemini API key" in ctl._compose("q", lang, SOURCES, [], [])["text"]

    ctl.settings["ai"]["answers_enabled"] = False
    ctl._read_key = lambda: "k"
    assert ctl._compose("q", lang, SOURCES, [], [])["mode"] == "passages"


def test_display_partial_hides_half_written_citation():
    assert gen.display_partial("God loved [V1", SOURCES) == "God loved"
    assert gen.display_partial("God is love [V2] and [V", SOURCES) == "God is love ([1 John 4:8 · KJV](cite:2)) and"


def test_streaming_compose_sends_verses_first_then_text(monkeypatch):
    """Verses are shown before Gemini writes; text arrives in pieces; the result is checked."""
    import time as _t
    from types import SimpleNamespace
    from digital_bible.qml_ui.ai_controller import AiController

    class StreamClient:
        def __init__(self, key, timeout_s=60):
            pass

        def stream(self, model, prompt, system=""):
            for piece in ["God ", "is love ", "[V2]", ". He gave ", "His Son [V1][V9]."]:
                _t.sleep(0.1)
                yield piece

    monkeypatch.setattr(gen, "GeminiClient", StreamClient)
    ctl = AiController.__new__(AiController)
    ctl.settings = {"ai": {"model": "gemini-test", "answers_enabled": True}}
    ctl._packages = {"google-genai": True}
    ctl._read_key = lambda: "k"
    updates = []
    out = ctl._compose("What is God?", SimpleNamespace(name="English"), SOURCES, [], [],
                       on_partial=updates.append, t_search=0.2)
    assert updates[0]["phase"] == "generating" and updates[0]["sources"] == SOURCES and updates[0]["text"] == ""
    texts = [u["text"] for u in updates[1:]]
    assert texts and texts[0].startswith("God") and len(texts) >= 3          # arrived in pieces
    assert out["phase"] == "done" and out["cited"] == [2, 1]
    assert any("V9" in n for n in out["notes"])
    assert out["timing"]["search"] == 0.2 and out["timing"]["first"] <= out["timing"]["total"]

    # the client is reused for the next question
    first = ctl._client_cache[1]
    ctl._compose("Again?", None, SOURCES, [], [], on_partial=lambda u: None)
    assert ctl._client_cache[1] is first


def test_stream_stopped_part_way_keeps_text(monkeypatch):
    from digital_bible.qml_ui.ai_controller import AiController

    class Broken:
        def __init__(self, key, timeout_s=60):
            pass

        def stream(self, model, prompt, system=""):
            yield "Partial answer [V1]"
            raise gen.GeminiError("network", gen.FRIENDLY["network"])

    monkeypatch.setattr(gen, "GeminiClient", Broken)
    ctl = AiController.__new__(AiController)
    ctl.settings = {"ai": {"model": "m", "answers_enabled": True}}
    ctl._packages = {"google-genai": True}
    ctl._read_key = lambda: "k"
    out = ctl._compose("q", None, SOURCES, [], [], on_partial=lambda u: None)
    assert out["mode"] == "ai" and "Partial answer" in out["text"]
    assert any("stopped before finishing" in n for n in out["notes"])


def test_chat_model_updates_rows_in_place():
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    from digital_bible.qml_ui.chat_model import ChatModel, ENTRY_ROLE
    app = QApplication.instance() or QApplication([])    # (the UI tests need a full QApplication)
    m = ChatModel()
    changed = []
    m.dataChanged.connect(lambda a, b, roles: changed.append(a.row()))
    m.append({"role": "user", "text": "q"})
    row = m.append({"role": "assistant", "text": "", "phase": "searching"})
    m.update(row, {"text": "Hello", "phase": "generating"})
    assert m.data(m.index(row, 0), ENTRY_ROLE)["text"] == "Hello" and changed == [row]
    assert m.rowCount() == 2
    m.clear()
    assert m.rowCount() == 0


def test_plan_search_parses_json_and_fences():
    class C:
        def __init__(self, raw):
            self.raw = raw
            self.kw = None

        def generate(self, model, prompt, **kw):
            self.kw = kw
            return self.raw

    c = C('```json\n{"references": ["Matthew 27:51-53", "John 11:43-44"], "query": "Who rose from the dead when Jesus died?"}\n```')
    plan = gen.plan_search(c, "m", "so there are people who rose then?", [("q", "a (Matthew 27:52)")])
    assert plan.references == ["Matthew 27:51-53", "John 11:43-44"]
    assert plan.query.startswith("Who rose") and c.kw["json_mode"] is True


def test_readable_history_replaces_ids():
    assert gen.readable_history("God is love [V2].", SOURCES) == "God is love (1 John 4:8)."


def test_suggested_references_are_looked_up_locally():
    """Gemini's suggestions are read from the local Bible; a made-up reference adds nothing."""
    from pathlib import Path
    from digital_bible.library import Library
    from digital_bible.ai.retriever import Retriever
    data = Path(__file__).resolve().parents[1] / "data"
    if not (data / "catalog.sqlite").exists():
        pytest.skip("needs an imported data/ folder")
    lib = Library(data)
    ret = Retriever(lib, None, None, None, ["002"])
    res = ret.retrieve("why did people come back to life when Jesus died", "en",
                       suggested_refs=["Matthew 27:51-53", "Hezekiah 3:4", "Romans 99:1"])
    refs = [v.reference for v in res.verses]
    assert refs[:3] == ["MATTHEW 27:51", "MATTHEW 27:52", "MATTHEW 27:53"]
    assert all("suggested" in v.methods for v in res.verses[:3])
    assert not any("HEZEKIAH" in r or "ROMANS 99" in r for r in refs)


def test_key_moves_from_old_app_name():
    from digital_bible.qml_ui import ai_controller as m

    class Ring:
        def __init__(self): self.d = {("BiblePro", "gemini_api_key"): "AIzaOLDKEY123456"}
        def get_password(self, s, u): return self.d.get((s, u))
        def set_password(self, s, u, p): self.d[(s, u)] = p
        def delete_password(self, s, u): self.d.pop((s, u), None)

    r = Ring()
    m._migrate_key(r)
    assert r.d == {("BibleQ-AI", "gemini_api_key"): "AIzaOLDKEY123456"}
