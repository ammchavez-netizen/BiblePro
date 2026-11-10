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
