from __future__ import annotations

import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

USERNAME_RE = re.compile(r"^[a-z0-9]([a-z0-9._-]{1,48})[a-z0-9]$")


def validate_username(value: str) -> None:
    if not USERNAME_RE.match(value or ""):
        raise ValidationError(
            _("Login faqat lotin harflari, raqamlar, nuqta va chiziqchadan iborat bo'lishi kerak.")
        )


class PasswordStrengthValidator:
    """Requires a mix of character classes and rejects trivial patterns.

    Django's built-in validators already cover length, similarity to user
    attributes, the common-password list and all-numeric passwords; this adds
    the composition rule.
    """

    def __init__(self, min_classes: int = 2):
        self.min_classes = min_classes

    def validate(self, password, user=None):
        classes = sum(
            bool(pattern.search(password))
            for pattern in (
                re.compile(r"[a-z]"),
                re.compile(r"[A-Z]"),
                re.compile(r"\d"),
                re.compile(r"[^A-Za-z0-9]"),
            )
        )
        if classes < self.min_classes:
            raise ValidationError(
                _(
                    "Parol juda oddiy. Kamida harf va raqamdan foydalaning."
                ),
                code="password_too_simple",
            )
        if re.fullmatch(r"(.)\1+", password or ""):
            raise ValidationError(
                _("Parol bir xil belgilardan iborat bo'lishi mumkin emas."),
                code="password_repetitive",
            )
        lowered = (password or "").lower()
        for sequence in ("12345678", "qwertyui", "abcdefgh"):
            if sequence in lowered:
                raise ValidationError(
                    _("Parol ketma-ket belgilardan iborat bo'lmasligi kerak."),
                    code="password_sequential",
                )

    def get_help_text(self):
        return _("Parol kamida 8 belgidan, harf va raqamlardan iborat bo'lishi kerak.")
