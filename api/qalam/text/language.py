import re

from langdetect import DetectorFactory, LangDetectException, detect

DetectorFactory.seed = 0

_ARABIC = re.compile(r"[\u0600-\u06FF]")
_LETTER = re.compile(r"[A-Za-z\u00C0-\u024F\u0600-\u06FF]")
_SUPPORTED = {"ar": "ar", "fr": "fr", "en": "en"}


def detect_language(text: str) -> str:
    sample = text.strip()[:4000]
    if not sample:
        return "unknown"
    letters = _LETTER.findall(sample)
    if not letters:
        return "unknown"
    arabic = _ARABIC.findall(sample)
    if len(arabic) / len(letters) >= 0.3:
        return "ar"
    try:
        code = detect(sample)
    except LangDetectException:
        return "unknown"
    return _SUPPORTED.get(code, "unknown")


def direction_for(language: str) -> str:
    return "rtl" if language == "ar" else "ltr"
