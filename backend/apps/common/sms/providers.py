from __future__ import annotations

import logging
import uuid

import httpx

from .base import SMSMessage, SMSProvider, SMSSendError

logger = logging.getLogger(__name__)


class ConsoleSMSProvider(SMSProvider):
    """Development provider: prints the message instead of sending it.

    The OTP body itself is scrubbed by ``RedactingFilter`` before it reaches a
    handler, so this is safe to leave wired up in dev but it must never be the
    configured provider in production.
    """

    name = "console"
    delivers = False

    def send(self, message: SMSMessage) -> str:
        message_id = uuid.uuid4().hex
        print(
            f"\n[SMS:{message.purpose}] -> {message.to}\n{message.text}\n"
            f"(provider=console id={message_id})\n",
            flush=True,
        )
        return message_id


class DummySMSProvider(SMSProvider):
    """No-op provider used in tests; records everything it was asked to send."""

    name = "dummy"
    delivers = False
    outbox: list[SMSMessage] = []

    def send(self, message: SMSMessage) -> str:
        type(self).outbox.append(message)
        return uuid.uuid4().hex

    @classmethod
    def clear(cls) -> None:
        cls.outbox = []


class HTTPSMSProvider(SMSProvider):
    """Generic JSON-over-HTTP gateway (Eskiz/Play Mobile shaped).

    Configure via ``SMS_API_URL`` / ``SMS_API_TOKEN`` / ``SMS_SENDER``.
    """

    name = "http"

    def send(self, message: SMSMessage) -> str:
        base_url = self.options.get("base_url")
        token = self.options.get("token")
        if not base_url or not token:
            raise SMSSendError("SMS gateway is not configured (SMS_API_URL / SMS_API_TOKEN).")
        payload = {
            "mobile_phone": message.to.lstrip("+"),
            "message": message.text,
            "from": self.options.get("sender") or "",
        }
        try:
            response = httpx.post(
                base_url,
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
                timeout=self.options.get("timeout", 10),
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            # Never log the payload: it contains the OTP.
            logger.error("SMS gateway request failed: %s", exc.__class__.__name__)
            raise SMSSendError("SMS xizmati vaqtincha ishlamayapti.") from exc
        try:
            data = response.json()
        except ValueError:
            return uuid.uuid4().hex
        return str(data.get("id") or data.get("message_id") or uuid.uuid4().hex)
