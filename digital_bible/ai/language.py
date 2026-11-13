"""Detect the language of a question (offline, using the 'lingua' library).

Only languages BibleQ-AI has Bibles for are considered; this keeps detection
fast, light on memory, and accurate for short questions.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Optional


@dataclass(frozen=True)
class DetectedLanguage:
    code: str           # ISO 639-1 where possible, e.g. "en", "tl", "es"
    name: str           # English name, e.g. "Tagalog"
    confidence: float   # 0..1


_LINGUA = ["ENGLISH", "TAGALOG", "SPANISH", "PORTUGUESE", "GERMAN", "FRENCH", "ITALIAN", "DUTCH",
           "SWEDISH", "NYNORSK", "BOKMAL", "LATIN", "GREEK", "INDONESIAN", "MALAY", "HINDI",
           "SWAHILI", "AFRIKAANS", "CHINESE", "KOREAN", "JAPANESE"]
_CODE_FIX = {"nb": "no", "nn": "no"}


@lru_cache(maxsize=1)
def _detector():
    try:
        from lingua import Language, LanguageDetectorBuilder
    except ImportError:
        return None
    langs = [getattr(Language, n) for n in _LINGUA if hasattr(Language, n)]
    return LanguageDetectorBuilder.from_languages(*langs).build()


def detect_language(text: str) -> Optional[DetectedLanguage]:
    """Return the most likely language, or None if unknown / detector unavailable."""
    text = (text or "").strip()
    det = _detector()
    if det is None or len(text) < 2:
        return None
    values = det.compute_language_confidence_values(text)
    if not values:
        return None
    top = values[0]
    code = top.language.iso_code_639_1.name.lower()
    code = _CODE_FIX.get(code, code)
    return DetectedLanguage(code, top.language.name.title(), float(top.value))


def language_available() -> bool:
    return _detector() is not None
