"""Gemini answers grounded in retrieved Bible passages.

Only the user's question (plus a short recent chat history) and the retrieved
passages are sent to Google. The API key is passed in by the caller (it lives in
Windows Credential Manager) and is never logged or included in error text.

Citations: every passage gets an ID (V1, V2, ...). The model must cite with those
IDs only; after generation any ID that does not exist is removed and reported,
so the app never shows a reference that was not actually retrieved.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Callable, Iterator, Optional, Sequence

DEFAULT_MODEL = "gemini-3.8-flash"
TIMEOUT_S = 60


# ======================================================================= errors
class GeminiError(Exception):
    """kind: no_package | no_key | invalid_key | permission | rate_limit | network |
    model_not_found | blocked | empty | server | other"""

    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind
        self.message = message


FRIENDLY = {
    "no_package": "The Gemini library is not installed (pip install -r requirements-ai.txt).",
    "no_key": "No Gemini API key is saved. Add one in AI Mode → Settings.",
    "invalid_key": "Google rejected the API key. Check that it was copied correctly.",
    "permission": "This API key is not allowed to use that model or the Gemini API.",
    "rate_limit": "Gemini's rate limit or free quota was reached. Wait a minute and try again.",
    "network": "Couldn't reach Google. Check your internet connection.",
    "model_not_found": "That model isn't available for this API key. Use Scan Available Models to pick one.",
    "blocked": "Gemini declined to answer this question (safety filter).",
    "empty": "Gemini returned an empty answer.",
    "server": "Google's servers had a temporary problem. Try again shortly.",
}


def _scrub(text: str, secret: str = "") -> str:
    text = str(text or "")
    if secret:
        text = text.replace(secret, "••••")
    text = re.sub(r"(key=)[A-Za-z0-9_\-]{8,}", r"\1••••", text)
    text = re.sub(r"AIza[0-9A-Za-z_\-]{20,}", "••••", text)
    return text[:300]


def classify(exc: BaseException, secret: str = "") -> GeminiError:
    """Turn any exception from google-genai / httpx into a GeminiError."""
    if isinstance(exc, GeminiError):
        return exc
    code = getattr(exc, "code", None)
    status = str(getattr(exc, "status", "") or "")
    msg = _scrub(getattr(exc, "message", None) or str(exc), secret)
    low = (msg + " " + status).lower()
    name = type(exc).__name__.lower()
    if isinstance(code, int):
        if code == 400 and ("api key" in low or "api_key" in low):
            return GeminiError("invalid_key", FRIENDLY["invalid_key"])
        if code in (401,):
            return GeminiError("invalid_key", FRIENDLY["invalid_key"])
        if code == 403:
            return GeminiError("permission", FRIENDLY["permission"] + f" ({msg})")
        if code == 404:
            return GeminiError("model_not_found", FRIENDLY["model_not_found"])
        if code == 429 or "resource_exhausted" in low:
            return GeminiError("rate_limit", FRIENDLY["rate_limit"])
        if code >= 500:
            return GeminiError("server", FRIENDLY["server"] + f" ({code})")
        return GeminiError("other", f"Gemini error {code}: {msg}")
    if any(w in name for w in ("connect", "timeout", "network", "transport")) or isinstance(exc, (OSError, TimeoutError)):
        return GeminiError("network", FRIENDLY["network"])
    if any(w in low for w in ("getaddrinfo", "name resolution", "connection", "timed out", "unreachable")):
        return GeminiError("network", FRIENDLY["network"])
    return GeminiError("other", f"{type(exc).__name__}: {msg}")


# ======================================================================= client
@dataclass
class ModelInfo:
    id: str
    display_name: str
    description: str = ""
    input_limit: int = 0
    output_limit: int = 0


def _model_sort_key(m: ModelInfo):
    i = m.id.lower()
    stable = not any(w in i for w in ("preview", "exp", "-latest", "tts", "image", "live", "audio", "embedding"))
    nums = [int(n) for n in re.findall(r"\d+", i)[:2]] + [0, 0]
    return (0 if "gemini" in i else 1, 0 if stable else 1, -nums[0], -nums[1],
            0 if "flash" in i and "lite" not in i else 1 if "pro" in i else 2, i)


class GeminiClient:
    def __init__(self, api_key: str, timeout_s: int = TIMEOUT_S):
        if not api_key:
            raise GeminiError("no_key", FRIENDLY["no_key"])
        try:
            from google import genai
            from google.genai import types
        except ImportError:
            raise GeminiError("no_package", FRIENDLY["no_package"]) from None
        self._key = api_key
        self._types = types
        self._client = genai.Client(api_key=api_key,
                                    http_options=types.HttpOptions(timeout=int(timeout_s * 1000)))

    def list_models(self) -> list[ModelInfo]:
        """Models this key can use for text answers (generateContent)."""
        try:
            out = []
            for m in self._client.models.list():
                actions = [a for a in (m.supported_actions or [])]
                if actions and "generateContent" not in actions:
                    continue
                mid = (m.name or "").split("/", 1)[-1]
                low = mid.lower()
                if not mid or any(w in low for w in ("embedding", "aqa", "imagen", "veo", "tts", "-image",
                                                     "native-audio", "live")):
                    continue
                out.append(ModelInfo(mid, m.display_name or mid, (m.description or "")[:200],
                                     m.input_token_limit or 0, m.output_token_limit or 0))
        except Exception as exc:
            raise classify(exc, self._key) from None
        out.sort(key=_model_sort_key)
        return out

    def test(self, model: str) -> dict:
        """Check the key, network and that `model` is usable. Returns details."""
        t0 = time.time()
        models = self.list_models()
        ids = {m.id for m in models}
        info = {"ok": True, "models": len(models), "model": model, "model_available": model in ids,
                "seconds": 0.0, "reply": ""}
        if model in ids:
            info["reply"] = self.generate(model, "Reply with the single word: OK", system="", max_tokens=16).strip()[:40]
        info["seconds"] = round(time.time() - t0, 1)
        return info

    def stream(self, model: str, prompt: str, system: str = "", temperature: float = 0.3,
               max_tokens: int = 2048, retries: int = 1) -> Iterator[str]:
        """Yield the answer in pieces as Gemini writes it.

        A rate-limit/server error before anything arrived is retried once; after text has
        started arriving, errors are raised (the caller keeps what it already has)."""
        types = self._types
        cfg = types.GenerateContentConfig(temperature=temperature, max_output_tokens=max_tokens,
                                          system_instruction=system or None)
        for attempt in range(retries + 1):
            got_text = False
            last = None
            try:
                for chunk in self._client.models.generate_content_stream(model=model, contents=prompt, config=cfg):
                    last = chunk
                    try:
                        piece = chunk.text or ""
                    except Exception:
                        piece = ""
                    if piece:
                        got_text = True
                        yield piece
            except Exception as exc:
                err = classify(exc, self._key)
                if not got_text and err.kind in ("rate_limit", "server") and attempt < retries:
                    time.sleep(2 * (attempt + 1))
                    continue
                raise err from None
            if not got_text:
                fb = getattr(last, "prompt_feedback", None) if last is not None else None
                if fb is not None and getattr(fb, "block_reason", None):
                    raise GeminiError("blocked", FRIENDLY["blocked"])
                cands = (getattr(last, "candidates", None) or []) if last is not None else []
                reason = str(getattr(cands[0], "finish_reason", "")) if cands else ""
                if any(w in reason for w in ("SAFETY", "PROHIBITED", "BLOCK")):
                    raise GeminiError("blocked", FRIENDLY["blocked"])
                raise GeminiError("empty", FRIENDLY["empty"])
            return

    def generate(self, model: str, prompt: str, system: str = "", temperature: float = 0.3,
                 max_tokens: int = 2048, retries: int = 1, json_mode: bool = False) -> str:
        types = self._types
        cfg = types.GenerateContentConfig(temperature=temperature, max_output_tokens=max_tokens,
                                          system_instruction=system or None,
                                          response_mime_type="application/json" if json_mode else None)
        for attempt in range(retries + 1):
            try:
                resp = self._client.models.generate_content(model=model, contents=prompt, config=cfg)
            except Exception as exc:
                err = classify(exc, self._key)
                if err.kind in ("rate_limit", "server") and attempt < retries:
                    time.sleep(3 * (attempt + 1))
                    continue
                raise err from None
            text = ""
            try:
                text = resp.text or ""
            except Exception:
                text = ""
            if not text.strip():
                fb = getattr(resp, "prompt_feedback", None)
                if fb is not None and getattr(fb, "block_reason", None):
                    raise GeminiError("blocked", FRIENDLY["blocked"])
                cands = getattr(resp, "candidates", None) or []
                reason = str(getattr(cands[0], "finish_reason", "")) if cands else ""
                if "SAFETY" in reason or "PROHIBITED" in reason or "BLOCK" in reason:
                    raise GeminiError("blocked", FRIENDLY["blocked"])
                raise GeminiError("empty", FRIENDLY["empty"])
            return text
        raise GeminiError("other", "Gemini did not respond.")


# ======================================================================= RAG prompt
SYSTEM_PROMPT = """You are BibleQ-AI's Bible research assistant. You answer questions about the Bible clearly and helpfully, like a knowledgeable Bible teacher.

Rules you must always follow:
1. LANGUAGE: Write the whole answer in {language}. Match the language of the user's question even if the passages are in another language.
2. ANSWER THE QUESTION: Answer what was actually asked, directly, in the first 1-2 sentences. For "why" or "what does it mean" questions, explain the reason or meaning, not just what the verses say. For follow-up questions, use the earlier conversation to understand what the user means.
3. EVIDENCE: Support the answer with the Bible passages provided in the user message. Some passages may be unrelated to the question: ignore those. You may use general, widely accepted biblical and historical background to explain and connect the passages.
4. CITATIONS: Cite passages only with their IDs in square brackets, e.g. [V1] or [V2][V5]. Never write a citation ID that is not in the list, and never write a book, chapter or verse reference that is not among the passages.
5. QUOTES: Quote passage text exactly as given. You may translate a quotation into the answer language, and then say it is a translation.
6. HONESTY: If the passages don't contain what is needed, say what the Bible passages do show and what is missing, briefly. Never invent verses or claim the Bible says something it doesn't. Where Christians interpret something differently, say so briefly and fairly instead of taking a denominational side.
7. STYLE: Write naturally. Don't begin with phrases like "Based on the provided passages". Use short paragraphs or bullet points (Markdown). Keep it under about 350 words unless the user asks for more."""


PLAN_PROMPT = """You help a Bible search engine find the passages needed to answer a question.
Return JSON only, in this form:
{"references": ["Matthew 27:51-53", "John 11:43-44"], "query": "standalone search question"}

- "references": up to 8 Bible passages (English book names, chapter:verse or chapter:verse-verse; never a whole chapter) that most directly answer the question. Include the key passages a Bible scholar would look up first. Only real references you are confident about.
- "query": the question rewritten as a standalone search question in English, including what earlier turns of the conversation refer to (e.g. "it", "that", "then")."""


@dataclass
class SearchPlan:
    references: list[str] = field(default_factory=list)
    query: str = ""


def plan_search(client: "GeminiClient", model: str, question: str,
                history: Sequence[tuple[str, str]] = ()) -> SearchPlan:
    """Ask Gemini which passages to look up (fast, small request). The verses themselves are
    then read from the local Bibles, so nothing Gemini suggests is shown unless it exists."""
    import json
    lines = []
    for q, a in list(history)[-2:]:
        lines.append(f"User: {q[:400]}")
        lines.append("Assistant: " + re.sub(r"\s+", " ", a)[:500])
    lines.append(f"Question: {question}")
    raw = client.generate(model, "\n".join(lines), system=PLAN_PROMPT, temperature=0.0,
                          max_tokens=400, retries=0, json_mode=True)
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?|```$", "", raw).strip()
    try:
        data = json.loads(raw)
    except ValueError:
        m = re.search(r"\{.*\}", raw, re.S)
        data = json.loads(m.group(0)) if m else {}
    refs = [str(r).strip() for r in (data.get("references") or []) if str(r).strip()][:8]
    return SearchPlan(refs, str(data.get("query") or "").strip()[:400])


def readable_history(plain: str, sources: Sequence[dict]) -> str:
    """An earlier answer with its [Vn] markers replaced by the actual references."""
    def repl(m):
        n = int(m.group(1))
        return f" ({nice_reference(sources[n - 1]['reference'])})" if 1 <= n <= len(sources) else ""
    return re.sub(r"\s?\[V(\d+)\]", repl, plain or "")


@dataclass
class Passage:
    id: str
    reference: str
    abbr: str
    language: str
    text: str


def make_passages(sources: Sequence[dict]) -> list[Passage]:
    return [Passage(f"V{i}", s["reference"], s["abbr"], s["language"], s["text"])
            for i, s in enumerate(sources, 1)]


def build_prompt(question: str, passages: Sequence[Passage], history: Sequence[tuple[str, str]] = ()) -> str:
    lines = []
    if history:
        lines.append("Earlier in this conversation (for context only):")
        for q, a in history[-2:]:
            lines.append(f"User: {q[:500]}")
            short = re.sub(r"\s+", " ", a)[:600]
            lines.append(f"Assistant: {short}")
        lines.append("")
    lines.append("Bible passages retrieved for this question:")
    for p in passages:
        lines.append(f"[{p.id}] {p.reference} ({p.abbr}, {p.language}): {p.text}")
    lines.append("")
    lines.append(f"User question: {question}")
    return "\n".join(lines)


def system_prompt(language_name: Optional[str]) -> str:
    lang = (f"{language_name} (the language of the user's question)" if language_name
            else "the same language as the user's question")
    return SYSTEM_PROMPT.format(language=lang)


_CITE_GROUP = re.compile(r"\[\s*(V\d+(?:\s*[,;]\s*V?\d+)*)\s*\]", re.IGNORECASE)


@dataclass
class CheckedAnswer:
    text: str                     # with valid [Vn] markers kept, invalid ones removed
    cited: list[int] = field(default_factory=list)       # 1-based passage numbers, in order of first use
    invalid: list[str] = field(default_factory=list)


def validate_citations(text: str, n_passages: int) -> CheckedAnswer:
    cited: list[int] = []
    invalid: list[str] = []

    def repl(m):
        out = []
        for part in re.split(r"\s*[,;]\s*", m.group(1)):
            num = int(re.sub(r"\D", "", part) or 0)
            if 1 <= num <= n_passages:
                out.append(f"[V{num}]")
                if num not in cited:
                    cited.append(num)
            else:
                invalid.append(part.upper() if part.upper().startswith("V") else f"V{part}")
        return "".join(out)

    clean = _CITE_GROUP.sub(repl, text)
    clean = re.sub(r"[ \t]+([.,;:!?])", r"\1", clean)
    return CheckedAnswer(clean.strip(), cited, invalid)


def nice_reference(ref: str) -> str:
    """'II TIMOTHY 3:4' -> 'II Timothy 3:4' (roman numerals stay upper case)."""
    if not ref.isupper():
        return ref
    return " ".join(w if re.fullmatch(r"[IVX]+", w) else w.title() for w in ref.split(" "))


def link_citations(text: str, sources: Sequence[dict]) -> str:
    """Replace citation markers with Markdown links for the chat view.

    "loved [V1]."      -> "loved ([John 3:16 · KJV](cite:1))."
    "[V2][V5]"         -> "([1 John 4:8 · KJV](cite:2); [Romans 5:8 · KJV](cite:5))"
    """
    def label(n):
        s = sources[n - 1]
        return f"[{nice_reference(s['reference'])} · {s['abbr']}](cite:{n})"

    def repl(m):
        nums = [int(x) for x in re.findall(r"\[V(\d+)\]", m.group(0))]
        return " (" + "; ".join(label(n) for n in nums) + ")"
    return re.sub(r"\s?(?:\[V\d+\])+", repl, text)


def display_partial(text: str, sources: Sequence[dict]) -> str:
    """Text written so far, ready to show: a half-written "[V1" at the end is hidden,
    complete citations become links, citations to unknown passages are dropped."""
    text = re.sub(r"\[\s*V?\d*[\s,;V\d]*$", "", text)
    return link_citations(validate_citations(text, len(sources)).text, sources)


def answer(client: GeminiClient, model: str, question: str, language_name: Optional[str],
           sources: Sequence[dict], history: Sequence[tuple[str, str]] = (),
           generate: Optional[Callable[..., str]] = None) -> CheckedAnswer:
    passages = make_passages(sources)
    prompt = build_prompt(question, passages, history)
    gen = generate or client.generate
    raw = gen(model, prompt, system=system_prompt(language_name))
    return validate_citations(raw, len(passages))
