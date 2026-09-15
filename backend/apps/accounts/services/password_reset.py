"""Forgotten-password flow driven by an OTP on the registered phone."""
from __future__ import annotations

import secrets

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.cache import cache
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError

from apps.audit.constants import AuditAction
from apps.audit.services import log_action
from apps.common.crypto import mask_phone
from apps.common.exceptions import AppError
from apps.common.otp import OTPPurpose, OTPService

TTL_SECONDS = 900


class PasswordResetSessionError(AppError):
    default_code = "RESET_SESSION_INVALID"
    default_detail = "Parolni tiklash sessiyasi tugagan. Qaytadan boshlang."


def _key(token: str) -> str:
    return f"password-reset:{token}"


def start_reset(login: str) -> dict:
    """Always reports success so the endpoint cannot enumerate accounts."""
    from .auth import resolve_user

    user = resolve_user(login)
    response = {
        "sent": False,
        "masked_phone": "",
        "session_token": "",
        "ttl_seconds": settings.OTP["TTL_SECONDS"],
        "debug_code": None,
    }
    if user is None or not user.phone or not user.is_phone_verified or not user.is_active:
        return response

    token = secrets.token_urlsafe(32)
    cache.set(_key(token), {"user_id": user.pk, "verified": False}, timeout=TTL_SECONDS)

    result = OTPService(OTPPurpose.PASSWORD_RESET, token).issue(
        user.phone,
        template="Maktab davomat tizimi. Parolni tiklash kodi: {code}. Kod {minutes} daqiqa amal qiladi.",
    )
    response.update(
        sent=True,
        masked_phone=mask_phone(user.phone),
        session_token=token,
        ttl_seconds=result.ttl_seconds,
        debug_code=result.debug_code,
    )
    return response


def _load(token: str) -> dict:
    data = cache.get(_key(token or ""))
    if not data:
        raise PasswordResetSessionError()
    return data


def verify_reset_otp(token: str, code: str) -> None:
    data = _load(token)
    OTPService(OTPPurpose.PASSWORD_RESET, token).verify(code)
    data["verified"] = True
    cache.set(_key(token), data, timeout=TTL_SECONDS)


def confirm_reset(token: str, new_password: str, *, request=None):
    from apps.accounts.models import User

    data = _load(token)
    if not data.get("verified"):
        raise PasswordResetSessionError(
            "Telefon raqami tasdiqlanmagan.", code="PHONE_NOT_VERIFIED"
        )

    user = User.objects.filter(pk=data["user_id"], is_active=True).first()
    if user is None:
        raise PasswordResetSessionError()

    try:
        validate_password(new_password, user)
    except DjangoValidationError as exc:
        raise ValidationError({"password": list(exc.messages)}) from exc

    user.set_password(new_password)
    user.must_change_password = False
    user.save(update_fields=["password", "must_change_password", "updated_at"])

    cache.delete(_key(token))
    OTPService(OTPPurpose.PASSWORD_RESET, token).clear()

    # Every existing session is invalidated: a reset must lock an attacker out.
    revoke_all_sessions(user)

    log_action(AuditAction.PASSWORD_RESET, user=user, entity=user, request=request)
    return user


def revoke_all_sessions(user) -> int:
    """Blacklist every outstanding refresh token for the user."""
    from rest_framework_simplejwt.token_blacklist.models import (
        BlacklistedToken,
        OutstandingToken,
    )

    count = 0
    for token in OutstandingToken.objects.filter(user=user):
        _, created = BlacklistedToken.objects.get_or_create(token=token)
        count += int(created)
    return count
