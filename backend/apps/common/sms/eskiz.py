"""Eskiz.uz SMS gateway.

Eskiz issues a bearer token from email + password that expires after ~30 days.
The token is cached in Redis and refreshed transparently on a 401, so the
credentials are exchanged once rather than on every message.

Credentials are read from ``Sozlamalar → Integratsiyalar → SMS (Eskiz)`` when
configured there, and from the environment otherwise.
"""
from __future__ import annotations

import logging

import httpx
from django.core.cache import cache

from .base import SMSMessage, SMSProvider, SMSSendError

logger = logging.getLogger(__name__)

TOKEN_CACHE_KEY = "sms:eskiz:token"
TOKEN_TTL_SECONDS = 25 * 24 * 3600  # refresh well before Eskiz's own expiry


class EskizSMSProvider(SMSProvider):
    name = "eskiz"

    # --- configuration -------------------------------------------------- #
    def _settings(self) -> dict:
        """Database configuration wins; environment is the fallback."""
        from apps.integrations.constants import IntegrationKind
        from apps.integrations.services.registry import integration_config, integration_secret

        config = integration_config(IntegrationKind.SMS_ESKIZ)
        return {
            "base_url": (config.get("base_url") or "https://notify.eskiz.uz/api").rstrip("/"),
            "sender": config.get("sender") or self.options.get("sender") or "4546",
            "email": config.get("email") or self.options.get("email") or "",
            "password": integration_secret(IntegrationKind.SMS_ESKIZ, "password")
            or self.options.get("password", ""),
            "token": integration_secret(IntegrationKind.SMS_ESKIZ, "token")
            or self.options.get("token", ""),
            "timeout": self.options.get("timeout", 10),
        }

    # --- auth ------------------------------------------------------------ #
    def _login(self, config: dict) -> str:
        if not config["email"] or not config["password"]:
            # A long-lived token pasted into settings is also a valid setup.
            if config["token"]:
                return config["token"]
            raise SMSSendError(
                "Eskiz sozlanmagan: email va parol yoki tayyor token kiriting."
            )
        try:
            response = httpx.post(
                f"{config['base_url']}/auth/login",
                data={"email": config["email"], "password": config["password"]},
                timeout=config["timeout"],
            )
            response.raise_for_status()
            token = (response.json().get("data") or {}).get("token")
        except httpx.HTTPError as exc:
            logger.error("Eskiz login failed: %s", exc.__class__.__name__)
            raise SMSSendError("Eskiz xizmatiga ulanib bo'lmadi.") from exc
        except (ValueError, AttributeError) as exc:
            raise SMSSendError("Eskiz javobini o'qib bo'lmadi.") from exc

        if not token:
            raise SMSSendError("Eskiz login yoki parol noto'g'ri.")
        cache.set(TOKEN_CACHE_KEY, token, timeout=TOKEN_TTL_SECONDS)
        return token

    def _token(self, config: dict, *, force_refresh: bool = False) -> str:
        if not force_refresh:
            cached = cache.get(TOKEN_CACHE_KEY)
            if cached:
                return cached
            if config["token"]:
                return config["token"]
        return self._login(config)

    # --- sending ---------------------------------------------------------- #
    def _send_once(self, config: dict, token: str, message: SMSMessage) -> httpx.Response:
        return httpx.post(
            f"{config['base_url']}/message/sms/send",
            data={
                "mobile_phone": message.to.lstrip("+"),
                "message": message.text,
                "from": config["sender"],
            },
            headers={"Authorization": f"Bearer {token}"},
            timeout=config["timeout"],
        )

    def send(self, message: SMSMessage) -> str:
        config = self._settings()
        token = self._token(config)

        try:
            response = self._send_once(config, token, message)
            if response.status_code in (401, 403):
                # Token expired or was revoked — re-login once and retry.
                token = self._token(config, force_refresh=True)
                response = self._send_once(config, token, message)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            # Never log the payload: it contains the OTP.
            logger.error("Eskiz send failed: %s", exc.__class__.__name__)
            raise SMSSendError("SMS yuborib bo'lmadi. Keyinroq qayta urinib ko'ring.") from exc

        try:
            data = response.json()
        except ValueError:
            return ""

        status = str(data.get("status", "")).lower()
        if status and status not in {"waiting", "success", "ok", "accepted"}:
            raise SMSSendError(f"Eskiz xabarni qabul qilmadi: {data.get('message', status)}")
        return str(data.get("id") or data.get("message_id") or "")

    # --- diagnostics ------------------------------------------------------ #
    def check(self) -> dict:
        """Used by the "Tekshirish" button in Sozlamalar."""
        config = self._settings()
        token = self._token(config, force_refresh=True)
        try:
            response = httpx.get(
                f"{config['base_url']}/auth/user",
                headers={"Authorization": f"Bearer {token}"},
                timeout=config["timeout"],
            )
            response.raise_for_status()
            data = (response.json() or {}).get("data") or {}
        except httpx.HTTPError as exc:
            raise SMSSendError("Eskiz xizmatiga ulanib bo'lmadi.") from exc
        return {
            "email": data.get("email", ""),
            "name": data.get("name", ""),
            "balance": data.get("balance"),
            "sender": config["sender"],
        }
