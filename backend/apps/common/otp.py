"""Redis-backed one-time password service.

Design notes:

* Only the *hash* of the code is stored, so a Redis dump does not leak codes.
* Attempts are counted server-side; the record self-destructs on exhaustion.
* A resend cooldown key blocks OTP flooding independently of the DRF throttle.
* ``purpose`` namespaces the codes so a registration OTP cannot be replayed
  against the password-reset flow.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
from dataclasses import dataclass
from enum import Enum

from django.conf import settings
from django.core.cache import cache

from apps.common.sms import SMSMessage, get_sms_provider

logger = logging.getLogger(__name__)


class OTPPurpose(str, Enum):
    REGISTRATION = "registration"
    PASSWORD_RESET = "password_reset"
    PHONE_CHANGE = "phone_change"
    #: Signing in through the bot: the code is delivered in Telegram itself.
    TELEGRAM_LOGIN = "telegram_login"
    TELEGRAM_PHONE_CHANGE = "telegram_phone_change"


class OTPError(Exception):
    code = "OTP_ERROR"
    message = "Tasdiqlash kodi bilan bog'liq xatolik."


class OTPCooldownError(OTPError):
    code = "OTP_COOLDOWN"
    message = "Yangi kod so'rash uchun biroz kuting."

    def __init__(self, seconds: int):
        self.seconds = seconds
        super().__init__(f"Yangi kodni {seconds} soniyadan so'ng so'rashingiz mumkin.")


class OTPNotFoundError(OTPError):
    code = "OTP_EXPIRED"
    message = "Tasdiqlash kodi topilmadi yoki muddati tugagan."


class OTPInvalidError(OTPError):
    code = "INVALID_OTP"
    message = "Tasdiqlash kodi noto'g'ri."

    def __init__(self, attempts_left: int):
        self.attempts_left = attempts_left
        super().__init__(self.message)


class OTPAttemptsExceededError(OTPError):
    code = "OTP_ATTEMPTS_EXCEEDED"
    message = "Urinishlar soni tugadi. Yangi kod so'rang."


@dataclass(frozen=True)
class OTPIssueResult:
    ttl_seconds: int
    resend_after_seconds: int
    # Populated only when OTP_EXPOSE_IN_RESPONSE is on (dev convenience).
    debug_code: str | None = None
    #: False when the configured provider only prints or discards the message.
    #: The caller is expected to say so rather than claim the code was sent.
    delivered: bool = True


def _digest(code: str, key: str) -> str:
    return hmac.new(
        settings.SECRET_KEY.encode(), f"{key}:{code}".encode(), hashlib.sha256
    ).hexdigest()


class OTPService:
    def __init__(self, purpose: OTPPurpose, identifier: str):
        """``identifier`` is whatever the OTP is bound to (a phone number, a
        registration session id, ...). It is hashed into the cache key."""
        self.purpose = purpose
        self.identifier = identifier
        self._key_hash = hashlib.sha256(
            f"{purpose.value}:{identifier}".encode()
        ).hexdigest()

    @property
    def _code_key(self) -> str:
        return f"otp:{self.purpose.value}:{self._key_hash}"

    @property
    def _cooldown_key(self) -> str:
        return f"otp:cooldown:{self.purpose.value}:{self._key_hash}"

    @property
    def config(self) -> dict:
        return settings.OTP

    def cooldown_remaining(self) -> int:
        return int(cache.ttl(self._cooldown_key) or 0)

    def issue(
        self,
        phone: str,
        *,
        template: str | None = None,
        code: str | None = None,
        send=None,
    ) -> OTPIssueResult:
        """Mint a code, store its hash and deliver it.

        ``code`` lets a caller supply one that follows its own rules (the
        Telegram login code is four digits with a repeat). ``send`` swaps the
        delivery channel — Telegram instead of SMS — while the storage,
        attempt counting and cooldown stay identical.
        """
        remaining = self.cooldown_remaining()
        if remaining > 0:
            raise OTPCooldownError(remaining)

        code = code or "".join(
            secrets.choice("0123456789") for _ in range(self.config["LENGTH"])
        )
        ttl = self.config["TTL_SECONDS"]
        cache.set(
            self._code_key,
            {"digest": _digest(code, self._key_hash), "attempts": 0},
            timeout=ttl,
        )
        cache.set(self._cooldown_key, 1, timeout=self.config["RESEND_COOLDOWN_SECONDS"])

        text = (template or "Maktab davomat tizimi. Tasdiqlash kodi: {code}").format(
            code=code, minutes=ttl // 60
        )
        delivered = True
        try:
            if send is not None:
                send(text)
            else:
                provider = get_sms_provider()
                provider.send(
                    SMSMessage(to=phone, text=text, purpose=f"otp:{self.purpose.value}")
                )
                delivered = provider.delivers
        except Exception:
            # Nothing was delivered, so nothing may be left behind to verify
            # against — otherwise the user is locked into a cooldown for a code
            # they never received.
            cache.delete(self._code_key)
            cache.delete(self._cooldown_key)
            raise

        logger.info(
            "OTP issued purpose=%s identifier_hash=%s", self.purpose.value, self._key_hash[:12]
        )
        return OTPIssueResult(
            ttl_seconds=ttl,
            resend_after_seconds=self.config["RESEND_COOLDOWN_SECONDS"],
            debug_code=code if self.config["EXPOSE_IN_RESPONSE"] else None,
            delivered=delivered,
        )

    def verify(self, code: str) -> bool:
        record = cache.get(self._code_key)
        if not record:
            raise OTPNotFoundError(OTPNotFoundError.message)

        attempts = record["attempts"] + 1
        max_attempts = self.config["MAX_ATTEMPTS"]

        if hmac.compare_digest(record["digest"], _digest(str(code).strip(), self._key_hash)):
            cache.delete(self._code_key)
            return True

        if attempts >= max_attempts:
            cache.delete(self._code_key)
            raise OTPAttemptsExceededError(OTPAttemptsExceededError.message)

        ttl = cache.ttl(self._code_key) or self.config["TTL_SECONDS"]
        record["attempts"] = attempts
        cache.set(self._code_key, record, timeout=int(ttl))
        raise OTPInvalidError(max_attempts - attempts)

    def clear(self) -> None:
        cache.delete(self._code_key)
        cache.delete(self._cooldown_key)
