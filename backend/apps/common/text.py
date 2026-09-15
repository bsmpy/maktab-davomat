"""Transliteration + slug helpers used by username generation."""
from __future__ import annotations

import re
import unicodedata

# Cyrillic (ru/uz) -> latin. Multi-character keys must be tried first.
_TRANSLIT_MAP: dict[str, str] = {
    "щ": "sh", "ш": "sh", "ч": "ch", "ц": "ts", "ю": "yu", "я": "ya",
    "ё": "yo", "ж": "j", "х": "x", "ъ": "", "ь": "", "ы": "i", "э": "e",
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "з": "z",
    "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o",
    "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f",
    # Uzbek Cyrillic extras
    "ў": "o", "қ": "q", "ғ": "g", "ҳ": "h",
    # Uzbek Latin letters that carry diacritics / modifier marks
    "ʻ": "", "ʼ": "", "‘": "", "’": "", "`": "", "'": "",
    "ō": "o", "ǒ": "o", "ğ": "g", "ç": "c", "ş": "s", "ı": "i", "ü": "u",
    "ö": "o", "ä": "a", "é": "e", "è": "e", "í": "i", "ú": "u", "ñ": "n",
}

_MULTI_KEYS = sorted(_TRANSLIT_MAP, key=len, reverse=True)


def transliterate(value: str) -> str:
    """Fold any supported script down to plain ASCII letters."""
    if not value:
        return ""
    text = value.strip().lower()
    out: list[str] = []
    index = 0
    while index < len(text):
        for key in _MULTI_KEYS:
            if text.startswith(key, index):
                out.append(_TRANSLIT_MAP[key])
                index += len(key)
                break
        else:
            out.append(text[index])
            index += 1
    folded = unicodedata.normalize("NFKD", "".join(out))
    return "".join(ch for ch in folded if not unicodedata.combining(ch))


def slugify_latin(value: str) -> str:
    """ASCII letters and digits only – safe for a username component."""
    text = transliterate(value)
    text = re.sub(r"[^a-z0-9]+", "", text)
    return text


def normalize_name(value: str) -> str:
    """Collapse whitespace and title-case a personal name."""
    return " ".join((value or "").split())
