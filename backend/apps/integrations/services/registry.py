"""Resolves integration configuration: database first, environment as fallback.

A fresh install works purely from ``.env``; once someone saves settings in
Sozlamalar → Integratsiyalar the stored row wins. School-specific rows override
the global one, so a second school can have its own bot or SMS account.
"""
from __future__ import annotations

import logging
from typing import Any

from django.conf import settings

from ..constants import IntegrationKind

logger = logging.getLogger(__name__)

#: Defaults pulled from settings when nothing is configured in the database.
ENV_FALLBACKS: dict[str, dict[str, Any]] = {
    IntegrationKind.TELEGRAM_BOT: {
        "config": {"bot_username": lambda: settings.TELEGRAM["BOT_USERNAME"]},
        "secrets": {"bot_token": lambda: settings.TELEGRAM["BOT_TOKEN"]},
    },
    IntegrationKind.SMS_ESKIZ: {
        "config": {
            "base_url": lambda: settings.SMS_PROVIDER_SETTINGS.get("base_url", ""),
            "sender": lambda: settings.SMS_PROVIDER_SETTINGS.get("sender", ""),
        },
        "secrets": {"token": lambda: settings.SMS_PROVIDER_SETTINGS.get("token", "")},
    },
    IntegrationKind.FACE_ID: {"config": {}, "secrets": {}},
    IntegrationKind.TERMINALS: {"config": {}, "secrets": {}},
}

#: Non-secret defaults for every integration, merged under whatever is stored.
DEFAULT_CONFIG: dict[str, dict[str, Any]] = {
    IntegrationKind.TELEGRAM_BOT: {
        "bot_username": "",
        # Which turnstile passes raise a Telegram message to the guardians.
        "send_entry": True,
        "send_exit": True,
        "send_reason_updates": True,
    },
    IntegrationKind.SMS_ESKIZ: {
        "base_url": "https://notify.eskiz.uz/api",
        "sender": "4546",
        "email": "",
        "send_otp": True,
    },
    IntegrationKind.FACE_ID: {
        "fdid": "1",
        "auto_enroll": True,
        "min_photo_bytes": 8 * 1024,
        "max_photo_bytes": 2 * 1024 * 1024,
    },
    IntegrationKind.TERMINALS: {
        # The school day the arrival is measured against. Arriving up to
        # `school_start_time` is on time; a minute past it is late.
        "school_start_time": "08:10",
        "school_end_time": "14:00",
        # Kept configurable, but the rule is a hard cutoff by default.
        "late_grace_minutes": 0,
        # Arriving after this is too late to count as a school day at all: the
        # arrival is still shown, but the day is not counted as attended.
        "arrival_cutoff_time": "16:00",
        "poll_interval_minutes": 5,
        "poll_window_minutes": 120,
        # Ignore a second read within this many seconds (turnstile bounce).
        "debounce_seconds": 60,
        "sync_device_time": True,
    },
}


def get_integration(kind: str, school=None):
    """Return the most specific ``Integration`` row, or ``None``."""
    from ..models import Integration

    queryset = Integration.objects.filter(kind=kind)
    if school is not None:
        specific = queryset.filter(school=school).first()
        if specific is not None:
            return specific
    return queryset.filter(school__isnull=True).first()


def integration_config(kind: str, school=None) -> dict:
    """Merged non-secret configuration: defaults ← env ← database."""
    resolved = dict(DEFAULT_CONFIG.get(kind, {}))

    for key, source in ENV_FALLBACKS.get(kind, {}).get("config", {}).items():
        try:
            value = source()
        except Exception:  # pragma: no cover - misconfigured settings
            value = ""
        if value:
            resolved[key] = value

    integration = get_integration(kind, school)
    if integration is not None:
        resolved.update({k: v for k, v in (integration.config or {}).items() if v != ""})
        resolved["is_enabled"] = integration.is_enabled
    else:
        resolved.setdefault("is_enabled", False)
    return resolved


def integration_secret(kind: str, key: str, school=None) -> str:
    """Secret value for an integration, falling back to the environment."""
    integration = get_integration(kind, school)
    if integration is not None:
        value = integration.secret(key)
        if value:
            return value

    source = ENV_FALLBACKS.get(kind, {}).get("secrets", {}).get(key)
    if source is None:
        return ""
    try:
        return source() or ""
    except Exception:  # pragma: no cover
        return ""


def is_enabled(kind: str, school=None) -> bool:
    integration = get_integration(kind, school)
    return bool(integration and integration.is_enabled)
