"""Serializer fields for the identifiers that appear all over the app.

Phone, passport ID and JSHSHIR are typed on a dozen different forms. Keeping
one field class per identifier means the rule is written once: every endpoint
accepts the same shapes, rejects the same ones and returns the same message.
"""
from __future__ import annotations

from rest_framework import serializers

from .crypto import normalize_jshshir
from .passport import InvalidPassportId, normalize_passport_id
from .phone import InvalidPhoneNumber, normalize_phone


class PhoneField(serializers.CharField):
    """``+998(90)123-45-67`` (and every other shape) → ``+998901234567``."""

    def __init__(self, **kwargs):
        kwargs.setdefault("max_length", 24)
        super().__init__(**kwargs)

    def to_internal_value(self, data) -> str:
        value = super().to_internal_value(data)
        if not value.strip():
            return ""
        try:
            return normalize_phone(value)
        except InvalidPhoneNumber as exc:
            raise serializers.ValidationError(str(exc)) from None


class PassportIdField(serializers.CharField):
    """Two uppercase Latin letters and seven digits."""

    def __init__(self, **kwargs):
        kwargs.setdefault("max_length", 12)
        super().__init__(**kwargs)

    def to_internal_value(self, data) -> str:
        value = super().to_internal_value(data)
        if not value.strip():
            return ""
        try:
            return normalize_passport_id(value)
        except InvalidPassportId as exc:
            raise serializers.ValidationError(str(exc)) from None


class JshshirField(serializers.CharField):
    """Exactly fourteen digits."""

    def __init__(self, **kwargs):
        kwargs.setdefault("max_length", 20)
        super().__init__(**kwargs)

    def to_internal_value(self, data) -> str:
        value = super().to_internal_value(data)
        if not value.strip():
            return ""
        try:
            return normalize_jshshir(value)
        except ValueError:
            raise serializers.ValidationError(
                "JSHSHIR 14 ta raqamdan iborat bo'lishi kerak."
            ) from None
