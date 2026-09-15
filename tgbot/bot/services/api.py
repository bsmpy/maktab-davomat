"""Async client for the Django REST API.

This is the bot's *only* data source: there is no database connection here, so
every permission check and every aggregation still happens on the backend.
Authentication is a shared service token; the end user is identified by their
Telegram id, which the backend only trusts because it was bound to an account
through a one-time link token.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from bot.config import config

logger = logging.getLogger(__name__)


class ApiError(Exception):
    """A structured error from the backend's unified error envelope."""

    def __init__(self, code: str, message: str, status: int = 0):
        self.code = code
        self.message = message
        self.status = status
        super().__init__(message)

    @property
    def not_linked(self) -> bool:
        return self.code == "TELEGRAM_NOT_LINKED"

    @property
    def no_children(self) -> bool:
        return self.code == "NO_CHILDREN"

    @property
    def phone_unknown(self) -> bool:
        """The number is not in the school's register."""
        return self.code == "PHONE_NOT_REGISTERED"

    @property
    def bad_code(self) -> bool:
        return self.code in {"INVALID_OTP", "OTP_EXPIRED", "OTP_ATTEMPTS_EXCEEDED"}


NETWORK_MESSAGE = "Server bilan bog'lanib bo'lmadi. Birozdan so'ng qayta urinib ko'ring."


class BackendClient:
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=config.api_base,
            timeout=config.http_timeout,
            headers={
                "X-Bot-Token": config.service_token,
                "Content-Type": "application/json",
            },
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = await self._client.post(path, json=payload)
        except httpx.HTTPError as exc:
            logger.warning("Backend unreachable: %s", exc.__class__.__name__)
            raise ApiError("NETWORK_ERROR", NETWORK_MESSAGE) from exc

        if response.status_code >= 400:
            try:
                error = response.json().get("error", {})
            except ValueError:
                error = {}
            raise ApiError(
                error.get("code", "UNKNOWN_ERROR"),
                error.get("message", "Kutilmagan xatolik yuz berdi."),
                response.status_code,
            )

        try:
            return response.json()
        except ValueError:
            return {}

    # --- endpoints ------------------------------------------------------ #
    async def link(self, telegram_id: int, token: str, profile: dict) -> dict:
        return await self._post(
            "/bot/link/", {"telegram_id": telegram_id, "token": token, "profile": profile}
        )

    # --- signing in by sharing a contact -------------------------------- #
    async def known_phone(self, telegram_id: int) -> dict:
        return await self._post("/bot/auth/phone/", {"telegram_id": telegram_id})

    async def auth_contact(self, telegram_id: int, phone: str) -> dict:
        return await self._post(
            "/bot/auth/contact/", {"telegram_id": telegram_id, "phone": phone}
        )

    async def auth_verify(
        self, telegram_id: int, phone: str, code: str, profile: dict
    ) -> dict:
        return await self._post(
            "/bot/auth/verify/",
            {
                "telegram_id": telegram_id,
                "phone": phone,
                "code": code,
                "profile": profile,
            },
        )

    async def phone_change_request(self, telegram_id: int, phone: str) -> dict:
        return await self._post(
            "/bot/phone/request/", {"telegram_id": telegram_id, "phone": phone}
        )

    async def phone_change_verify(self, telegram_id: int, phone: str, code: str) -> dict:
        return await self._post(
            "/bot/phone/verify/",
            {"telegram_id": telegram_id, "phone": phone, "code": code},
        )

    async def me(self, telegram_id: int) -> dict:
        return await self._post("/bot/me/", {"telegram_id": telegram_id})

    async def children(self, telegram_id: int) -> dict:
        return await self._post("/bot/children/", {"telegram_id": telegram_id})

    async def set_active_child(self, telegram_id: int, student_id: str) -> dict:
        return await self._post(
            "/bot/active-child/", {"telegram_id": telegram_id, "student": student_id}
        )

    async def attendance(
        self, telegram_id: int, period: str, student_id: str | None = None, date: str | None = None
    ) -> dict:
        payload: dict[str, Any] = {"telegram_id": telegram_id, "period": period}
        if student_id:
            payload["student"] = student_id
        if date:
            payload["date"] = date
        return await self._post("/bot/attendance/", payload)

    async def notifications(self, telegram_id: int, limit: int = 5, only_unread: bool = False) -> dict:
        return await self._post(
            "/bot/notifications/",
            {"telegram_id": telegram_id, "limit": limit, "only_unread": only_unread},
        )

    async def set_notifications(self, telegram_id: int, enabled: bool) -> dict:
        return await self._post(
            "/bot/settings/", {"telegram_id": telegram_id, "notifications_enabled": enabled}
        )

    async def unlink(self, telegram_id: int) -> dict:
        return await self._post("/bot/unlink/", {"telegram_id": telegram_id})


#: One shared client for the whole process (connection pooling).
api = BackendClient()
