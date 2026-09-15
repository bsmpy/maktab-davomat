"""Audit helpers.

``log_action`` is deliberately forgiving: an audit failure must never break the
business transaction it is observing.
"""
from __future__ import annotations

import contextlib
import contextvars
import datetime as dt
import decimal
import logging
from collections.abc import Iterable
from typing import Any

from django.db import models, transaction

from apps.common.throttling import client_ip

from .constants import AuditAction
from .middleware import get_current_request
from .models import AuditLog

logger = logging.getLogger(__name__)

#: Set while a bulk operation is running: per-row audit writes are suppressed so
#: that deleting 100k attendance rows does not emit 100k INSERTs.
_suppressed: contextvars.ContextVar[bool] = contextvars.ContextVar("audit_suppressed", default=False)


@contextlib.contextmanager
def suppressed(summary: dict | None = None, *, action: str | AuditAction | None = None, user=None):
    """Silence per-row audit writes for the duration of a bulk operation.

    A single summary entry is written on exit instead, so the trail records
    *that* a bulk change happened without one row per affected object::

        with suppressed({"reason": "reseed"}, action=AuditAction.ATTENDANCE_DELETE):
            Attendance.objects.all().delete()
    """
    token = _suppressed.set(True)
    try:
        yield
    finally:
        _suppressed.reset(token)
        if action is not None:
            log_action(action, user=user, metadata={"bulk": True, **(summary or {})})


def is_suppressed() -> bool:
    return _suppressed.get()


#: Keys removed from any payload before it is persisted.
SENSITIVE_KEYS = {
    "password",
    "password1",
    "password2",
    "password_confirm",
    "new_password",
    "old_password",
    "current_password",
    "otp",
    "otp_code",
    "code",
    "token",
    "access",
    "access_token",
    "refresh",
    "refresh_token",
    "secret",
    "authorization",
    "jshshir",
    "jshshir_hash",
    "jshshir_encrypted",
    "pinfl",
    "session_token",
    "csrf",
}


def _jsonable(value: Any) -> Any:
    """Coerce a value into something ``JSONField`` can store."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, models.Model):
        return str(value.pk)
    if isinstance(value, (dt.datetime, dt.date, dt.time)):
        return value.isoformat()
    if isinstance(value, decimal.Decimal):
        return float(value)
    return str(value)


def sanitize(data: Any) -> Any:
    """Strip secrets and coerce everything else into JSON-safe values.

    Audit payloads are assembled from model fields, so they routinely contain
    UUIDs and dates. Serialising them here (rather than letting the JSON
    encoder blow up mid-INSERT) keeps an audit write from poisoning the
    surrounding transaction.
    """
    if isinstance(data, dict):
        return {
            str(key): ("[REDACTED]" if str(key).lower() in SENSITIVE_KEYS else sanitize(value))
            for key, value in data.items()
        }
    if isinstance(data, (list, tuple, set)):
        return [sanitize(item) for item in data]
    return _jsonable(data)


def model_snapshot(instance: models.Model, fields: Iterable[str] | None = None) -> dict:
    """Serialisable snapshot of a model instance, with secrets removed."""
    names = list(fields) if fields else [
        field.name
        for field in instance._meta.concrete_fields
        if field.name not in {"password"} and not field.name.endswith("_encrypted")
    ]
    snapshot = {}
    for name in names:
        try:
            snapshot[name] = getattr(instance, name)
        except Exception:  # pragma: no cover - deferred/broken attribute
            continue
    return sanitize(snapshot)


def log_action(
    action: str | AuditAction,
    *,
    user=None,
    entity=None,
    entity_type: str = "",
    entity_id: str = "",
    old_data: dict | None = None,
    new_data: dict | None = None,
    metadata: dict | None = None,
    request=None,
    success: bool = True,
    username: str = "",
) -> AuditLog | None:
    if _suppressed.get():
        return None

    request = request or get_current_request()

    if entity is not None:
        entity_type = entity_type or entity._meta.label
        entity_id = entity_id or str(entity.pk)

    ip = None
    user_agent = ""
    if request is not None:
        ip = client_ip(request)
        if ip in {"", "unknown"}:
            ip = None
        user_agent = (request.META.get("HTTP_USER_AGENT") or "")[:255]

    resolved_user = user
    if resolved_user is None and request is not None:
        candidate = getattr(request, "user", None)
        if candidate is not None and getattr(candidate, "is_authenticated", False):
            resolved_user = candidate

    try:
        # An isolated savepoint: if the audit write fails for any reason it must
        # not break the business transaction it is observing.
        with transaction.atomic():
            return AuditLog.objects.create(
                user=resolved_user,
                username=username or (getattr(resolved_user, "username", "") or ""),
                action=str(action),
                entity_type=entity_type,
                entity_id=str(entity_id),
                old_data=sanitize(old_data) if old_data is not None else None,
                new_data=sanitize(new_data) if new_data is not None else None,
                metadata=sanitize(metadata or {}),
                ip_address=ip,
                user_agent=user_agent,
                success=success,
            )
    except Exception:  # pragma: no cover - auditing must not break the request
        logger.exception("Failed to write audit log for action=%s", action)
        return None
