"""Thin Telegram Bot API client used by the backend to push notifications.

The aiogram process only *reads* from users; outbound notification messages are
sent from Django/Celery so the whole business logic stays on one side.
"""
from __future__ import annotations

import logging

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)


class TelegramError(Exception):
    """Raised for a non-retryable Telegram API failure."""

    def __init__(self, message: str, *, blocked: bool = False):
        self.blocked = blocked
        super().__init__(message)


class TelegramClient:
    def __init__(self, token: str | None = None, timeout: int | None = None):
        self.token = token or settings.TELEGRAM["BOT_TOKEN"]
        self.timeout = timeout or settings.TELEGRAM["API_TIMEOUT"]

    @property
    def enabled(self) -> bool:
        return bool(self.token)

    def _call(self, method: str, payload: dict) -> dict:
        if not self.enabled:
            raise TelegramError("TELEGRAM_BOT_TOKEN is not configured.")
        url = f"https://api.telegram.org/bot{self.token}/{method}"
        try:
            response = httpx.post(url, json=payload, timeout=self.timeout)
        except httpx.HTTPError as exc:
            raise TelegramError(f"Telegram API unreachable: {exc.__class__.__name__}") from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise TelegramError("Telegram API returned a non-JSON response.") from exc

        if not data.get("ok"):
            description = str(data.get("description", "unknown error"))
            blocked = response.status_code in (400, 403) and (
                "blocked" in description.lower() or "chat not found" in description.lower()
            )
            raise TelegramError(description, blocked=blocked)
        return data.get("result", {})

    def send_message(
        self, chat_id: int, text: str, *, parse_mode: str = "HTML", reply_markup: dict | None = None
    ) -> dict:
        payload: dict = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        return self._call("sendMessage", payload)


def send_message(chat_id: int, text: str, **kwargs) -> dict:
    return TelegramClient().send_message(chat_id, text, **kwargs)
