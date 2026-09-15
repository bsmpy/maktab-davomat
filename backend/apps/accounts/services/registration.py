"""Step-by-step guardian registration.

Threat model
------------
Knowing a pupil's name is not a credential. The applicant must additionally
prove that they are a guardian the school already registered:

1. the JSHSHIR they type must hash to a guardian row in that pupil's school;
2. that guardian must already be linked to that exact pupil (with the kinship
   they claimed);
3. the last four digits of the phone must match the *registered* number;
4. an OTP must be delivered to that registered number and typed back.

The phone number is never taken from the request — it always comes from the
guardian record — so an attacker cannot redirect the OTP.

Every failure returns one identical error, so the endpoint cannot be used as an
oracle for "does this JSHSHIR exist" or "is this pupil's parent registered".
Attempts are counted per registration attempt *and* per pupil.
"""
from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass
from datetime import date

from django.conf import settings
from django.contrib.postgres.search import TrigramWordSimilarity
from django.core.cache import cache
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.audit.constants import AuditAction
from apps.audit.services import log_action
from apps.common.crypto import mask_phone, normalize_jshshir
from apps.common.exceptions import AppError, ConflictError, NotFoundError
from apps.common.otp import OTPPurpose, OTPService
from apps.common.phone import last_digits
from apps.common.text import transliterate

logger = logging.getLogger(__name__)

#: Minimum trigram word-similarity for a fuzzy name match. Word-level (rather
#: than whole-string) similarity keeps a one-word query from being diluted by
#: the rest of the full name.
SIMILARITY_THRESHOLD = 0.4

GENERIC_IDENTITY_ERROR = (
    "Ma'lumotlar mos kelmadi. Tanlangan o'quvchi, qarindoshlik, JSHSHIR va "
    "telefon raqami maktab ma'lumotlar bazasidagi ma'lumotlar bilan mos "
    "bo'lishi kerak."
)


class RegistrationError(AppError):
    default_code = "REGISTRATION_FAILED"
    default_detail = GENERIC_IDENTITY_ERROR


class IdentityMismatchError(RegistrationError):
    default_code = "IDENTITY_MISMATCH"


class AlreadyRegisteredError(ConflictError):
    default_code = "ALREADY_REGISTERED"
    default_detail = (
        "Bu ota-ona uchun akkaunt allaqachon mavjud. Iltimos, tizimga kiring "
        "yoki parolni tiklang."
    )


class RegistrationSessionError(AppError):
    status_code = 400
    default_code = "REGISTRATION_SESSION_INVALID"
    default_detail = "Ro'yxatdan o'tish sessiyasi tugagan. Qaytadan boshlang."


@dataclass(frozen=True)
class RegistrationSession:
    token: str
    data: dict

    @property
    def phone_verified(self) -> bool:
        return bool(self.data.get("phone_verified"))


def _session_key(token: str) -> str:
    return f"registration:session:{token}"


def _attempt_key(student_id: str) -> str:
    return f"registration:identify:{student_id}"


def _ttl() -> int:
    return settings.REGISTRATION["SESSION_TTL_SECONDS"]


# --------------------------------------------------------------------------- #
# Step 1-3: catalogue + safe student search
# --------------------------------------------------------------------------- #
def search_students(*, class_group, query: str, student_code: str = "") -> list:
    """Bounded, privacy-preserving search inside one class group.

    Returns at most ``STUDENT_SEARCH_MAX_RESULTS`` rows and never the whole
    class: a short query is rejected outright, so the endpoint cannot be walked
    to dump the register.
    """
    from apps.students.models import Student

    config = settings.REGISTRATION
    query = (query or "").strip()
    student_code = (student_code or "").strip()

    if not student_code and len(query) < config["STUDENT_SEARCH_MIN_QUERY"]:
        raise RegistrationError(
            f"Qidiruv uchun kamida {config['STUDENT_SEARCH_MIN_QUERY']} ta belgi kiriting.",
            code="QUERY_TOO_SHORT",
        )

    queryset = Student.objects.active().for_class_group(class_group.id).with_class()
    if student_code:
        return list(
            queryset.filter(student_code__iexact=student_code)[
                : config["STUDENT_SEARCH_MAX_RESULTS"]
            ]
        )

    # ``search_name`` holds the latin-folded full name. A plain substring match
    # covers the common case; trigram similarity additionally bridges spelling
    # differences between Uzbek Latin and Russian Cyrillic ("Валиев" →
    # "valiev" vs. the register's "valiyev").
    needle = transliterate(query)
    queryset = (
        queryset.annotate(match=TrigramWordSimilarity(needle, "search_name"))
        .filter(Q(search_name__icontains=needle) | Q(match__gte=SIMILARITY_THRESHOLD))
        .order_by("-match", "last_name", "first_name")
    )
    return list(queryset[: config["STUDENT_SEARCH_MAX_RESULTS"]])


# --------------------------------------------------------------------------- #
# Step 4-6: identity verification
# --------------------------------------------------------------------------- #
def _count_attempt(student_id: str) -> None:
    key = _attempt_key(student_id)
    attempts = cache.get(key, 0) + 1
    cache.set(key, attempts, timeout=3600)
    if attempts > settings.REGISTRATION["IDENTIFY_MAX_ATTEMPTS"]:
        raise RegistrationError(
            "Urinishlar soni oshib ketdi. Iltimos, keyinroq qayta urinib ko'ring "
            "yoki maktab ma'muriyatiga murojaat qiling.",
            code="TOO_MANY_ATTEMPTS",
        )


def identify_guardian(
    *, student, relation: str, jshshir: str, phone_last4: str
) -> RegistrationSession:
    from apps.guardians.models import Guardian, GuardianStudent

    _count_attempt(str(student.id))

    try:
        normalized = normalize_jshshir(jshshir)
    except ValueError:
        raise RegistrationError(
            "JSHSHIR 14 ta raqamdan iborat bo'lishi kerak.", code="INVALID_JSHSHIR"
        ) from None

    guardian = (
        Guardian.objects.find_by_jshshir(normalized)
        .filter(school_id=student.school_id, is_active=True)
        .first()
    )
    link = (
        GuardianStudent.objects.filter(guardian=guardian, student=student).first()
        if guardian
        else None
    )

    # One error for every failure mode: no enumeration oracle.
    if (
        guardian is None
        or link is None
        or link.relation != relation
        or last_digits(guardian.phone) != (phone_last4 or "").strip()
    ):
        logger.info(
            "Registration identity mismatch for student=%s (attempt recorded)", student.id
        )
        raise IdentityMismatchError()

    if guardian.user_id is not None:
        raise AlreadyRegisteredError()

    cache.delete(_attempt_key(str(student.id)))

    token = secrets.token_urlsafe(32)
    data = {
        "student_id": str(student.id),
        "guardian_id": str(guardian.id),
        "relation": relation,
        "phone_verified": False,
        "created_at": timezone.now().isoformat(),
    }
    cache.set(_session_key(token), data, timeout=_ttl())

    return RegistrationSession(token=token, data=data)


def load_session(token: str) -> RegistrationSession:
    data = cache.get(_session_key(token or ""))
    if not data:
        raise RegistrationSessionError()
    return RegistrationSession(token=token, data=data)


def save_session(session: RegistrationSession) -> None:
    cache.set(_session_key(session.token), session.data, timeout=_ttl())


def session_context(session: RegistrationSession) -> dict:
    """Safe summary of a session for the UI (masked phone, names)."""
    from apps.guardians.models import Guardian
    from apps.students.models import Student

    guardian = Guardian.objects.filter(pk=session.data["guardian_id"]).first()
    student = (
        Student.objects.with_class().filter(pk=session.data["student_id"]).first()
    )
    if guardian is None or student is None:
        raise RegistrationSessionError()
    return {
        "session_token": session.token,
        "guardian_name": guardian.full_name,
        "masked_phone": mask_phone(guardian.phone),
        "student_name": student.full_name,
        "class_group": student.class_group.display_name,
        "relation": session.data["relation"],
        "phone_verified": session.phone_verified,
    }


# --------------------------------------------------------------------------- #
# Step 7: OTP on the *registered* phone
# --------------------------------------------------------------------------- #
def _otp_service(session: RegistrationSession) -> OTPService:
    return OTPService(OTPPurpose.REGISTRATION, session.token)


def request_registration_otp(session: RegistrationSession):
    """Raise a code and deliver it to the parent's Telegram chat.

    The code is *typed on the website*; Telegram is only the delivery channel,
    the way SMS used to be. A parent who has shared their contact with the bot
    has a chat we can reach; anyone else falls back to SMS, which the response
    reports honestly as undelivered when no gateway is configured.
    """
    from apps.guardians.models import Guardian
    from apps.telegram.services.auth import chat_for_phone, generate_code

    guardian = Guardian.objects.filter(pk=session.data["guardian_id"]).first()
    if guardian is None:
        raise RegistrationSessionError()

    service = _otp_service(session)
    chat_id = chat_for_phone(guardian.phone)

    if chat_id is not None:
        from apps.telegram.services.client import send_message

        return service.issue(
            guardian.phone,
            code=generate_code(),
            template=(
                "🔐 <b>{code}</b>\n\n"
                "Saytda ro'yxatdan o'tish uchun tasdiqlash kodi.\n"
                "Uni <b>saytga</b> kiriting. Kod {minutes} daqiqa amal qiladi.\n\n"
                "Bu kodni hech kimga bermang."
            ),
            send=lambda text: send_message(chat_id, text),
        )

    return service.issue(
        guardian.phone,
        template="Maktab davomat tizimi. Ro'yxatdan o'tish kodi: {code}. Kod {minutes} daqiqa amal qiladi.",
    )


def verify_registration_otp(session: RegistrationSession, code: str) -> RegistrationSession:
    _otp_service(session).verify(code)
    session.data["phone_verified"] = True
    session.data["phone_verified_at"] = timezone.now().isoformat()
    save_session(session)
    return session


# --------------------------------------------------------------------------- #
# Step 8-10: account creation
# --------------------------------------------------------------------------- #
@transaction.atomic
def complete_registration(session: RegistrationSession, *, password: str, request=None):
    """Create the account, verify every guardian↔student link, return the user."""
    from apps.accounts.constants import Role
    from apps.accounts.services.username import create_user_with_username
    from apps.guardians.models import Guardian, GuardianStudent

    if not session.phone_verified:
        raise RegistrationError(
            "Telefon raqami tasdiqlanmagan.", code="PHONE_NOT_VERIFIED"
        )

    guardian = (
        Guardian.objects.select_for_update().filter(pk=session.data["guardian_id"]).first()
    )
    if guardian is None:
        raise NotFoundError("Ota-ona ma'lumotlari topilmadi.")
    if guardian.user_id is not None:
        raise AlreadyRegisteredError()

    user = create_user_with_username(
        first_name=guardian.first_name,
        last_name=guardian.last_name,
        middle_name=guardian.middle_name,
        phone=guardian.phone,
        phone_verified_at=timezone.now(),
        role=Role.PARENT,
        password=password,
    )

    guardian.user = user
    guardian.save(update_fields=["user", "updated_at"])

    # Registering confirms *every* child the school already linked to this
    # guardian, not just the one used to prove identity.
    links = GuardianStudent.objects.filter(guardian=guardian)
    now = timezone.now()
    links.filter(verified=False).update(verified=True, verified_at=now)

    # The chat that proved this number becomes the account's Telegram link, so
    # the bot works immediately without a second pairing step.
    _link_known_chat(user, guardian.phone)

    cache.delete(_session_key(session.token))
    _otp_service(session).clear()

    log_action(
        AuditAction.REGISTRATION,
        user=user,
        entity=user,
        request=request,
        new_data={"username": user.username, "guardian_id": str(guardian.id)},
    )
    for link in links:
        log_action(
            AuditAction.GUARDIAN_STUDENT_LINK,
            user=user,
            entity=link,
            request=request,
            metadata={"student_id": str(link.student_id), "relation": link.relation},
        )

    return user, guardian


def _link_known_chat(user, phone: str) -> None:
    from apps.telegram.models import TelegramAccount
    from apps.telegram.services.auth import chat_for_phone

    chat_id = chat_for_phone(phone)
    if chat_id is None:
        return
    if TelegramAccount.objects.filter(telegram_id=chat_id).exclude(user=user).exists():
        # That chat belongs to somebody else; leave both alone.
        return

    TelegramAccount.objects.update_or_create(
        user=user,
        defaults={"telegram_id": chat_id, "is_active": True, "notifications_enabled": True},
    )


def available_relations() -> list[dict]:
    from apps.guardians.constants import Relation

    return [{"value": value, "label": label} for value, label in Relation.choices]


def student_search_payload(student) -> dict:
    """Only what the applicant needs to recognise their child.

    The photo is here so a parent can pick their child out of a class with
    several similar surnames — the masked name alone often cannot. It is the
    one personal thing this anonymous endpoint returns, which is why the search
    stays scoped to one class group, needs a real query, caps its results and
    is rate limited per IP.
    """
    from apps.common.media import absolute_media_url

    return {
        "id": str(student.id),
        "display_name": student.masked_full_name,
        "full_name": student.masked_full_name,
        "class_group": student.class_group.display_name,
        "birth_year": student.birth_date.year if student.birth_date else None,
        "photo": absolute_media_url(student.photo),
        "has_registered_guardian": student.guardian_links.filter(
            guardian__user__isnull=False
        ).exists(),
    }


def today() -> date:
    return timezone.localdate()
