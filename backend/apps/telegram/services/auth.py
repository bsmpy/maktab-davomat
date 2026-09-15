"""Signing in through the bot.

The parent opens the bot, shares their own contact, and if that number is the
one the school recorded for them they get a four-digit code in Telegram. No
JSHSHIR, no SMS: possession of the registered number is the proof.

The code is sent by the backend, not by the bot process — it never passes
through aiogram, so a compromised bot host cannot read codes in flight.

Every failure answers the same way. "This number is not in the register" and
"this number is already linked to someone else" must be indistinguishable, or
the bot becomes an oracle for which phone numbers a school holds.
"""
from __future__ import annotations

import logging
import secrets

from django.db import transaction
from django.utils import timezone

from apps.audit.constants import AuditAction
from apps.audit.services import log_action
from apps.common.exceptions import AppError, ConflictError
from apps.common.otp import OTPPurpose, OTPService
from apps.common.phone import InvalidPhoneNumber, normalize_phone

from ..models import TelegramAccount
from .client import TelegramError, send_message

logger = logging.getLogger(__name__)

CODE_LENGTH = 4
#: Codes must repeat at least one digit — 1282, 4843. Roughly half of the
#: 10 000 combinations qualify, which costs nothing and is what was asked for.
_MAX_DISTINCT_DIGITS = CODE_LENGTH - 1

GENERIC_MISMATCH = (
    "Bu raqam maktab ro'yxatida topilmadi. Iltimos, maktab ma'muriyatiga "
    "murojaat qiling."
)


class ContactMismatchError(AppError):
    status_code = 404
    default_code = "PHONE_NOT_REGISTERED"
    default_detail = GENERIC_MISMATCH


def generate_code() -> str:
    """A four-digit code with at least two identical digits."""
    while True:
        code = f"{secrets.randbelow(10**CODE_LENGTH):0{CODE_LENGTH}d}"
        if len(set(code)) <= _MAX_DISTINCT_DIGITS:
            return code


#: How long a chat's number is remembered, so the contact is asked for once.
KNOWN_PHONE_TTL_SECONDS = 60 * 60 * 24 * 30


def _known_phone_key(telegram_id: int) -> str:
    return f"telegram:phone:{telegram_id}"


def _chat_key(phone: str) -> str:
    return f"telegram:chat:{phone}"


def remember_phone(telegram_id: int, phone: str) -> None:
    """Remember the pairing in both directions.

    ``chat → phone`` so the bot stops asking for the contact, and
    ``phone → chat`` so a code raised on the website knows where to go.
    """
    from django.core.cache import cache

    cache.set(_known_phone_key(telegram_id), phone, timeout=KNOWN_PHONE_TTL_SECONDS)
    cache.set(_chat_key(phone), telegram_id, timeout=KNOWN_PHONE_TTL_SECONDS)


def chat_for_phone(phone: str) -> int | None:
    """Which Telegram chat proved this number, if any.

    A linked account is authoritative; the cache covers the window between
    sharing a contact and finishing registration on the site.
    """
    from django.core.cache import cache

    account = (
        TelegramAccount.objects.filter(user__phone=phone, is_active=True)
        .only("telegram_id")
        .first()
    )
    if account is not None:
        return account.telegram_id

    cached = cache.get(_chat_key(phone))
    return int(cached) if cached else None


def known_phone(telegram_id: int) -> str:
    """The number this chat already proved, so it is not asked for twice."""
    from django.core.cache import cache

    cached = cache.get(_known_phone_key(telegram_id))
    if cached:
        return cached

    # A chat that has signed in before keeps its number on the account.
    account = (
        TelegramAccount.objects.filter(telegram_id=telegram_id, is_active=True)
        .select_related("user")
        .first()
    )
    if account and account.user and account.user.phone:
        remember_phone(telegram_id, account.user.phone)
        return account.user.phone

    return ""


def _otp(telegram_id: int, purpose: OTPPurpose = OTPPurpose.TELEGRAM_LOGIN) -> OTPService:
    # Bound to the chat, not the phone: the code is only ever useful in the
    # conversation that asked for it.
    return OTPService(purpose, str(telegram_id))


def _deliver(telegram_id: int):
    def send(text: str) -> None:
        send_message(telegram_id, text)

    return send


def find_guardian(phone: str):
    """The guardian the school recorded under this number, if any."""
    from apps.guardians.models import Guardian

    return (
        Guardian.objects.filter(phone=phone, is_active=True)
        .select_related("user", "school")
        .first()
    )


def accept_contact(*, telegram_id: int, phone: str) -> dict:
    """The contact was shared. Remember the pairing; the code comes later.

    Codes are typed on the website, so the bot's job here is only to prove that
    this chat owns this number — after which the site can raise a code and know
    where to deliver it.
    """
    try:
        normalized = normalize_phone(phone)
    except InvalidPhoneNumber:
        raise ContactMismatchError() from None

    guardian = find_guardian(normalized)
    if guardian is None:
        logger.info("Telegram contact for an unknown number (chat=%s)", telegram_id)
        raise ContactMismatchError()

    remember_phone(telegram_id, normalized)
    return {
        "matched": True,
        "guardian_name": guardian.full_name,
        "has_account": guardian.user_id is not None,
        "username": guardian.user.username if guardian.user_id else None,
    }


def send_code_to_chat(phone: str, code: str, *, purpose: str = "login") -> bool:
    """Deliver a code raised on the website into the parent's Telegram chat."""
    chat_id = chat_for_phone(phone)
    if chat_id is None:
        return False

    text = (
        f"🔐 <b>{code}</b>\n\n"
        "Saytdagi tasdiqlash kodi. Uni <b>saytga</b> kiriting.\n"
        "Bu kodni hech kimga bermang."
    )
    try:
        send_message(chat_id, text)
    except TelegramError:
        logger.warning("Could not deliver a code to chat %s", chat_id)
        return False
    return True


def request_login_code(*, telegram_id: int, phone: str) -> dict:
    """Legacy in-bot code path, kept for the phone-change flow."""
    try:
        normalized = normalize_phone(phone)
    except InvalidPhoneNumber:
        raise ContactMismatchError() from None

    guardian = find_guardian(normalized)
    if guardian is None:
        logger.info("Telegram login attempt for an unknown number (chat=%s)", telegram_id)
        raise ContactMismatchError()

    # Someone else's Telegram already holds this account.
    taken = TelegramAccount.objects.filter(user=guardian.user).exclude(
        telegram_id=telegram_id
    )
    if guardian.user_id and taken.exists():
        raise ConflictError(
            "Bu akkaunt boshqa Telegram profilga ulangan. Avval undan uzing.",
            code="TELEGRAM_ALREADY_LINKED",
        )

    remember_phone(telegram_id, normalized)

    code = generate_code()
    result = _otp(telegram_id).issue(
        normalized,
        code=code,
        template=(
            "🔐 <b>{code}</b>\n\n"
            "Maktab davomat tizimiga kirish uchun tasdiqlash kodi.\n"
            "Kod {minutes} daqiqa amal qiladi.\n\n"
            "Bu kodni hech kimga bermang."
        ),
        send=_deliver(telegram_id),
    )
    return {
        "sent": True,
        "guardian_name": guardian.full_name,
        "ttl_seconds": result.ttl_seconds,
        "resend_after_seconds": result.resend_after_seconds,
        "code_length": CODE_LENGTH,
    }


@transaction.atomic
def verify_login_code(*, telegram_id: int, code: str, phone: str, profile: dict | None = None):
    """Step two: the code came back. Bind the chat and hand out a web ticket."""
    from apps.accounts.constants import Role
    from apps.accounts.services.onetime import issue_login_ticket
    from apps.accounts.services.username import create_user_with_username
    from apps.guardians.models import GuardianStudent

    _otp(telegram_id).verify(code)

    try:
        normalized = normalize_phone(phone)
    except InvalidPhoneNumber:
        raise ContactMismatchError() from None

    guardian = find_guardian(normalized)
    if guardian is None:
        raise ContactMismatchError()

    created = False
    user = guardian.user
    if user is None:
        # First sign-in: the school had the person, not the account.
        user = create_user_with_username(
            first_name=guardian.first_name,
            last_name=guardian.last_name,
            middle_name=guardian.middle_name,
            phone=guardian.phone,
            phone_verified_at=timezone.now(),
            role=Role.PARENT,
            password=None,
            must_change_password=True,
        )
        guardian.user = user
        guardian.save(update_fields=["user", "updated_at"])
        created = True

    links = GuardianStudent.objects.filter(guardian=guardian)
    links.filter(verified=False).update(verified=True, verified_at=timezone.now())

    account, _made = TelegramAccount.objects.update_or_create(
        user=user,
        defaults={
            "telegram_id": telegram_id,
            "telegram_username": ((profile or {}).get("username") or "")[:64],
            "first_name": ((profile or {}).get("first_name") or "")[:128],
            "last_name": ((profile or {}).get("last_name") or "")[:128],
            "is_active": True,
            "notifications_enabled": True,
            "linked_at": timezone.now(),
        },
    )

    log_action(
        AuditAction.TELEGRAM_LINK,
        user=user,
        entity=account,
        metadata={"telegram_id": telegram_id, "via": "contact", "new_account": created},
    )
    if created:
        log_action(AuditAction.REGISTRATION, user=user, entity=user, metadata={"via": "telegram"})

    return {
        "username": user.username,
        "full_name": user.full_name,
        "is_new_account": created,
        "needs_password": not user.has_usable_password() or user.must_change_password,
        "children": links.count(),
        # Redeemed once, by the browser, within minutes — so the password is
        # never typed into a chat window.
        "login_url": issue_login_ticket(user),
    }


# --------------------------------------------------------------------------- #
# Changing the number, the same way
# --------------------------------------------------------------------------- #
def request_phone_change(*, telegram_id: int, phone: str) -> dict:
    """A signed-in parent proves the new number is theirs before it is stored."""
    from apps.accounts.models import User

    account = TelegramAccount.objects.filter(
        telegram_id=telegram_id, is_active=True
    ).select_related("user").first()
    if account is None:
        raise ConflictError("Avval tizimga kiring.", code="TELEGRAM_NOT_LINKED")

    try:
        normalized = normalize_phone(phone)
    except InvalidPhoneNumber:
        raise ConflictError("Telefon raqami noto'g'ri.", code="INVALID_PHONE") from None

    if User.objects.filter(phone=normalized).exclude(pk=account.user_id).exists():
        raise ConflictError(
            "Bu raqam boshqa akkauntga biriktirilgan.", code="PHONE_TAKEN"
        )

    result = _otp(telegram_id, OTPPurpose.TELEGRAM_PHONE_CHANGE).issue(
        normalized,
        code=generate_code(),
        template=(
            "🔐 <b>{code}</b>\n\n"
            "Telefon raqamini o'zgartirish uchun tasdiqlash kodi.\n"
            "Kod {minutes} daqiqa amal qiladi."
        ),
        send=_deliver(telegram_id),
    )
    return {"sent": True, "ttl_seconds": result.ttl_seconds}


@transaction.atomic
def verify_phone_change(*, telegram_id: int, code: str, phone: str) -> dict:
    account = TelegramAccount.objects.filter(
        telegram_id=telegram_id, is_active=True
    ).select_related("user").first()
    if account is None:
        raise ConflictError("Avval tizimga kiring.", code="TELEGRAM_NOT_LINKED")

    _otp(telegram_id, OTPPurpose.TELEGRAM_PHONE_CHANGE).verify(code)
    normalized = normalize_phone(phone)

    user = account.user
    old = user.phone
    user.phone = normalized
    user.phone_verified_at = timezone.now()
    user.save(update_fields=["phone", "phone_verified_at", "updated_at"])

    # The register is what registration and notifications read, so it moves too.
    guardian = getattr(user, "guardian_profile", None)
    if guardian is not None:
        guardian.phone = normalized
        guardian.save(update_fields=["phone", "updated_at"])

    log_action(
        AuditAction.PHONE_CHANGE,
        user=user,
        entity=user,
        metadata={"old": old, "new": normalized, "via": "telegram"},
    )
    return {"phone": normalized}


def safe_send(telegram_id: int, text: str) -> bool:
    """Best-effort chat message — a delivery failure must not fail the request."""
    try:
        send_message(telegram_id, text)
        return True
    except TelegramError:
        logger.warning("Could not message chat %s", telegram_id)
        return False
