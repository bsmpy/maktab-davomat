"""One-time browser sign-in tickets.

The bot proves who someone is — they shared the number the school recorded and
typed back a code only that chat received. What it cannot do is set a password:
anything typed into a chat stays in its history forever.

So the bot hands over a link instead. The ticket behind it is single-use, lives
for minutes, and is stored as a hash, so reading the cache does not yield a
working credential. Redeeming it issues the same tokens a password login would.
"""
from __future__ import annotations

import hashlib
import secrets

from django.conf import settings
from django.core.cache import cache

TICKET_TTL_SECONDS = 300
_PREFIX = "login-ticket:"


def _key(raw: str) -> str:
    return f"{_PREFIX}{hashlib.sha256(raw.encode()).hexdigest()}"


def issue_login_ticket(user) -> str:
    """Return the URL the bot should offer as a button."""
    raw = secrets.token_urlsafe(32)
    cache.set(_key(raw), user.pk, timeout=TICKET_TTL_SECONDS)
    return f"{settings.FRONTEND_URL.rstrip('/')}/kirish/telegram?ticket={raw}"


def redeem_login_ticket(raw: str):
    """Consume a ticket and return its user, or ``None``.

    Deleted before the user is looked up, so a replay of the same value cannot
    be answered twice even if two requests race.
    """
    from apps.accounts.models import User

    if not raw:
        return None

    key = _key(raw)
    user_id = cache.get(key)
    cache.delete(key)
    if user_id is None:
        return None
    return User.objects.filter(pk=user_id, is_active=True).first()
