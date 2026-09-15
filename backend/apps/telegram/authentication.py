"""Server-to-server authentication for the aiogram process.

The bot never receives a user JWT and never touches the database directly. It
presents a single shared secret (``BOT_SERVICE_TOKEN``) and then identifies the
end user by Telegram id — which the backend only trusts because that id was
bound to an account through a one-time link token.
"""
from __future__ import annotations

import secrets

from django.conf import settings
from rest_framework.permissions import BasePermission

HEADER = "X-Bot-Token"


class IsBotService(BasePermission):
    message = "Bot xizmati uchun autentifikatsiya talab qilinadi."

    def has_permission(self, request, view):
        expected = settings.TELEGRAM["SERVICE_TOKEN"]
        if not expected:
            return False
        provided = request.headers.get(HEADER, "")
        if not provided:
            authorization = request.headers.get("Authorization", "")
            if authorization.lower().startswith("bot "):
                provided = authorization[4:]
        return bool(provided) and secrets.compare_digest(provided, expected)
