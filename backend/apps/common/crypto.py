"""Encryption / hashing helpers for sensitive identifiers (JSHSHIR, phone).

Two representations are stored side by side:

* ``*_hash``      – HMAC-SHA256 with a server-side pepper. Deterministic, so it
                    can be indexed and looked up, but not reversible.
* ``*_encrypted`` – Fernet ciphertext, reversible by privileged code paths only.

Nothing anywhere returns the plaintext to an API client.
"""
from __future__ import annotations

import hashlib
import hmac
import re
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

JSHSHIR_RE = re.compile(r"^\d{14}$")


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    key = settings.FIELD_ENCRYPTION_KEY
    if not key:
        raise ImproperlyConfigured("FIELD_ENCRYPTION_KEY is not set.")
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except Exception as exc:  # pragma: no cover - configuration error
        raise ImproperlyConfigured(
            "FIELD_ENCRYPTION_KEY must be a urlsafe base64-encoded 32 byte key."
        ) from exc


def encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt(token: str) -> str | None:
    if not token:
        return None
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken:
        return None


def _pepper() -> bytes:
    key = settings.JSHSHIR_HASH_KEY
    if not key:
        raise ImproperlyConfigured("JSHSHIR_HASH_KEY is not set.")
    return key.encode() if isinstance(key, str) else key


def hash_value(value: str) -> str:
    """Deterministic, peppered hash used for equality lookups."""
    return hmac.new(_pepper(), value.encode(), hashlib.sha256).hexdigest()


def normalize_jshshir(value: str) -> str:
    digits = re.sub(r"\D", "", value or "")
    if not JSHSHIR_RE.match(digits):
        raise ValueError("JSHSHIR must contain exactly 14 digits.")
    return digits


def mask_jshshir(last4: str | None) -> str:
    """``**********1234`` – the only representation ever sent to a client."""
    if not last4:
        return "*" * 14
    return "*" * 10 + last4[-4:]


def mask_phone(phone: str | None) -> str:
    """``+998 ** *** 45 67`` – enough for the user to recognise their number."""
    if not phone:
        return ""
    digits = re.sub(r"\D", "", phone)
    if len(digits) < 4:
        return "*" * len(digits)
    tail = digits[-4:]
    head = digits[:3] if len(digits) > 9 else ""
    return f"+{head}{'*' * (len(digits) - len(head) - 4)}{tail}" if head else f"***{tail}"
