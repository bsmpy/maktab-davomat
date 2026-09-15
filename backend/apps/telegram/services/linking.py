"""One-time Telegram account linking.

The web UI (authenticated) asks for a link token. The user either types the
6-digit code into the bot or follows a deep link; the bot forwards the raw
value to the backend, which is the only place that decides whether a Telegram
id may be bound to an account.

Both the code and the deep-link token are stored as SHA-256 hashes, are valid
once, and expire after ``TELEGRAM_LINK_TOKEN_TTL_SECONDS``.
"""
from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.audit.constants import AuditAction
from apps.audit.services import log_action
from apps.common.exceptions import ConflictError, NotFoundError

from ..models import TelegramAccount, TelegramLinkToken

CODE_LENGTH = 6


def _hash(value: str) -> str:
    return hashlib.sha256(f"tg-link:{value}".encode()).hexdigest()


@dataclass(frozen=True)
class LinkTokenIssue:
    code: str
    deep_link: str
    expires_at: object
    bot_username: str


@transaction.atomic
def issue_link_token(user) -> LinkTokenIssue:
    # Only one live token per user: issuing a new one invalidates the old.
    TelegramLinkToken.objects.filter(user=user, used_at__isnull=True).update(
        used_at=timezone.now()
    )

    code = "".join(secrets.choice("0123456789") for _ in range(CODE_LENGTH))
    token = secrets.token_urlsafe(24)
    ttl = settings.TELEGRAM["LINK_TOKEN_TTL_SECONDS"]
    expires_at = timezone.now() + timedelta(seconds=ttl)

    TelegramLinkToken.objects.create(
        user=user,
        code_hash=_hash(code),
        token_hash=_hash(token),
        expires_at=expires_at,
    )

    bot_username = settings.TELEGRAM["BOT_USERNAME"]
    deep_link = f"https://t.me/{bot_username}?start={token}" if bot_username else ""
    return LinkTokenIssue(
        code=code, deep_link=deep_link, expires_at=expires_at, bot_username=bot_username
    )


def _find_token(raw_value: str) -> TelegramLinkToken | None:
    digest = _hash(raw_value.strip())
    return (
        TelegramLinkToken.objects.select_related("user")
        .filter(used_at__isnull=True, expires_at__gt=timezone.now())
        .filter(code_hash=digest)
        .first()
        or TelegramLinkToken.objects.select_related("user")
        .filter(used_at__isnull=True, expires_at__gt=timezone.now())
        .filter(token_hash=digest)
        .first()
    )


@transaction.atomic
def consume_link_token(raw_value: str, *, telegram_id: int, profile: dict | None = None):
    """Bind ``telegram_id`` to the token's owner. Returns the TelegramAccount."""
    if not raw_value:
        raise NotFoundError("Ulanish kodi noto'g'ri yoki muddati tugagan.", code="INVALID_LINK_TOKEN")

    link_token = _find_token(raw_value)
    if link_token is None:
        raise NotFoundError(
            "Ulanish kodi noto'g'ri yoki muddati tugagan.", code="INVALID_LINK_TOKEN"
        )

    existing = TelegramAccount.objects.filter(telegram_id=telegram_id).first()
    if existing and existing.user_id != link_token.user_id:
        raise ConflictError(
            "Bu Telegram akkaunt boshqa foydalanuvchiga ulangan.",
            code="TELEGRAM_ALREADY_LINKED",
        )

    profile = profile or {}
    account, _created = TelegramAccount.objects.update_or_create(
        user=link_token.user,
        defaults={
            "telegram_id": telegram_id,
            "telegram_username": (profile.get("username") or "")[:64],
            "first_name": (profile.get("first_name") or "")[:128],
            "last_name": (profile.get("last_name") or "")[:128],
            "language_code": (profile.get("language_code") or "uz")[:8],
            "is_active": True,
            "notifications_enabled": True,
            "linked_at": timezone.now(),
        },
    )

    link_token.used_at = timezone.now()
    link_token.used_by_telegram_id = telegram_id
    link_token.save(update_fields=["used_at", "used_by_telegram_id", "updated_at"])

    log_action(
        AuditAction.TELEGRAM_LINK,
        user=link_token.user,
        entity=account,
        metadata={"telegram_id": telegram_id},
    )
    return account


@transaction.atomic
def unlink_telegram_account(user) -> bool:
    account = TelegramAccount.objects.filter(user=user).first()
    if account is None:
        return False
    telegram_id = account.telegram_id
    account.delete()
    log_action(AuditAction.TELEGRAM_UNLINK, user=user, metadata={"telegram_id": telegram_id})
    return True
