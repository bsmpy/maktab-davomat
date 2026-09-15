"""Uzbek phone number normalisation (E.164, +998XXXXXXXXX)."""
from __future__ import annotations

import re

PHONE_RE = re.compile(r"^\+998\d{9}$")


class InvalidPhoneNumber(ValueError):
    pass


def normalize_phone(raw: str) -> str:
    """Accept the shapes people actually type and return E.164.

    ``+998 90 123 45 67``, ``998901234567``, ``901234567`` and ``8901234567``
    all normalise to ``+998901234567``.
    """
    if not raw:
        raise InvalidPhoneNumber("Phone number is required.")
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 9:
        digits = "998" + digits
    elif len(digits) == 10 and digits.startswith("8"):
        digits = "998" + digits[1:]
    elif len(digits) == 12 and digits.startswith("998"):
        pass
    else:
        raise InvalidPhoneNumber("Telefon raqami noto'g'ri formatda.")
    candidate = "+" + digits
    if not PHONE_RE.match(candidate):
        raise InvalidPhoneNumber("Telefon raqami noto'g'ri formatda.")
    return candidate


def last_digits(phone: str, count: int = 4) -> str:
    digits = re.sub(r"\D", "", phone or "")
    return digits[-count:]
