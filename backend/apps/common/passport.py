"""Uzbek passport (ID card) series and number.

The document is always two uppercase Latin letters followed by seven digits —
``AA1234567``. People type it with spaces or in lower case, so normalise before
storing and reject anything that is not exactly that shape.
"""
from __future__ import annotations

import re

PASSPORT_ID_RE = re.compile(r"^[A-Z]{2}\d{7}$")

#: Shown to the user whenever the value does not match.
PASSPORT_ID_ERROR = (
    "Passport ID noto'g'ri: 2 ta katta lotin harfi va 7 ta raqam (masalan AA1234567)."
)


class InvalidPassportId(ValueError):
    pass


def normalize_passport_id(raw: str) -> str:
    """``aa 123 45 67`` → ``AA1234567``; anything else raises."""
    candidate = re.sub(r"[\s-]", "", raw or "").upper()
    if not PASSPORT_ID_RE.match(candidate):
        raise InvalidPassportId(PASSPORT_ID_ERROR)
    return candidate


def mask_passport_id(value: str | None) -> str:
    """``AA*****67`` – enough to recognise, not enough to reuse."""
    if not value:
        return ""
    return f"{value[:2]}{'*' * 5}{value[-2:]}"
