"""Signing in by sharing a contact in the bot.

The parent opens the bot, shares their own number, and gets a four-digit code
in Telegram. Possession of the number the school recorded is the proof — there
is no JSHSHIR step on this path — so what the endpoint refuses to reveal
matters as much as what it does.
"""
from __future__ import annotations

import pytest
from django.urls import reverse

from apps.accounts.models import User
from apps.common.exceptions import AppError
from apps.telegram.models import TelegramAccount
from apps.telegram.services.auth import (
    CODE_LENGTH,
    generate_code,
    request_login_code,
    verify_login_code,
)

pytestmark = pytest.mark.django_db

TELEGRAM_ID = 770001


@pytest.fixture(autouse=True)
def _capture_telegram(monkeypatch):
    """Codes are delivered by the backend, so the tests read them here."""
    sent: list[tuple[int, str]] = []
    monkeypatch.setattr(
        "apps.telegram.services.auth.send_message",
        lambda chat_id, text, **kwargs: sent.append((chat_id, text)) or {"message_id": 1},
    )
    return sent


def code_from(sent) -> str:
    import re

    match = re.search(r"<b>(\d{4})</b>", sent[-1][1])
    assert match, sent[-1][1]
    return match.group(1)


# --------------------------------------------------------------------------- #
# The code itself
# --------------------------------------------------------------------------- #
def test_the_code_is_four_digits():
    for _ in range(200):
        code = generate_code()
        assert len(code) == CODE_LENGTH
        assert code.isdigit()


def test_every_code_repeats_at_least_one_digit():
    """1282, 4843 — never four distinct digits."""
    for _ in range(500):
        code = generate_code()
        assert len(set(code)) < CODE_LENGTH, code


def test_codes_are_not_all_the_same():
    """A constraint is not an excuse to stop being random."""
    assert len({generate_code() for _ in range(200)}) > 50


# --------------------------------------------------------------------------- #
# Requesting a code
# --------------------------------------------------------------------------- #
def test_a_known_number_gets_a_code_in_telegram(guardian, _capture_telegram):
    result = request_login_code(telegram_id=TELEGRAM_ID, phone=guardian.phone)

    assert result["sent"] is True
    assert result["code_length"] == CODE_LENGTH
    assert len(_capture_telegram) == 1
    chat_id, text = _capture_telegram[0]
    assert chat_id == TELEGRAM_ID
    assert len(code_from(_capture_telegram)) == CODE_LENGTH


def test_an_unknown_number_is_refused_without_saying_why(db, _capture_telegram):
    with pytest.raises(AppError) as caught:
        request_login_code(telegram_id=TELEGRAM_ID, phone="+998900000000")

    assert caught.value.code == "PHONE_NOT_REGISTERED"
    # Nothing was sent: the endpoint is not an oracle for the register.
    assert _capture_telegram == []


def test_a_malformed_number_is_refused_the_same_way(db, _capture_telegram):
    with pytest.raises(AppError) as caught:
        request_login_code(telegram_id=TELEGRAM_ID, phone="12345")
    assert caught.value.code == "PHONE_NOT_REGISTERED"


def test_a_failed_delivery_leaves_no_code_behind(guardian, monkeypatch):
    """Otherwise the parent sits in a cooldown for a code they never got."""
    from apps.telegram.services.client import TelegramError

    def explode(*args, **kwargs):
        raise TelegramError("blocked")

    monkeypatch.setattr("apps.telegram.services.auth.send_message", explode)

    with pytest.raises(TelegramError):
        request_login_code(telegram_id=TELEGRAM_ID, phone=guardian.phone)

    # The next attempt is allowed immediately rather than hitting the cooldown.
    monkeypatch.setattr(
        "apps.telegram.services.auth.send_message", lambda *a, **k: {"message_id": 1}
    )
    assert request_login_code(telegram_id=TELEGRAM_ID, phone=guardian.phone)["sent"]


# --------------------------------------------------------------------------- #
# Verifying it
# --------------------------------------------------------------------------- #
def test_the_first_sign_in_creates_the_account(
    guardian, guardian_links, _capture_telegram
):
    assert guardian.user_id is None

    request_login_code(telegram_id=TELEGRAM_ID, phone=guardian.phone)
    result = verify_login_code(
        telegram_id=TELEGRAM_ID, code=code_from(_capture_telegram), phone=guardian.phone
    )

    assert result["is_new_account"] is True
    assert result["needs_password"] is True
    assert result["username"]
    assert result["login_url"].startswith("http")

    guardian.refresh_from_db()
    assert guardian.user is not None
    assert TelegramAccount.objects.get(telegram_id=TELEGRAM_ID).user == guardian.user


def test_signing_in_verifies_every_child_link(
    guardian, guardian_links, _capture_telegram
):
    from apps.guardians.models import GuardianStudent

    GuardianStudent.objects.filter(guardian=guardian).update(verified=False)

    request_login_code(telegram_id=TELEGRAM_ID, phone=guardian.phone)
    verify_login_code(
        telegram_id=TELEGRAM_ID, code=code_from(_capture_telegram), phone=guardian.phone
    )

    assert not GuardianStudent.objects.filter(guardian=guardian, verified=False).exists()


def test_signing_in_again_reuses_the_account(
    guardian, guardian_links, parent_user, _capture_telegram
):
    request_login_code(telegram_id=TELEGRAM_ID, phone=guardian.phone)
    result = verify_login_code(
        telegram_id=TELEGRAM_ID, code=code_from(_capture_telegram), phone=guardian.phone
    )

    assert result["is_new_account"] is False
    assert result["username"] == parent_user.username
    assert User.objects.filter(pk=parent_user.pk).count() == 1


def test_a_wrong_code_is_rejected(guardian, _capture_telegram):
    from apps.common.otp import OTPInvalidError

    request_login_code(telegram_id=TELEGRAM_ID, phone=guardian.phone)
    wrong = "1111" if code_from(_capture_telegram) != "1111" else "2222"

    with pytest.raises(OTPInvalidError):
        verify_login_code(telegram_id=TELEGRAM_ID, code=wrong, phone=guardian.phone)


def test_a_code_is_bound_to_the_chat_that_asked_for_it(guardian, _capture_telegram):
    """A code seen over someone's shoulder is useless in another chat."""
    from apps.common.otp import OTPNotFoundError

    request_login_code(telegram_id=TELEGRAM_ID, phone=guardian.phone)

    with pytest.raises(OTPNotFoundError):
        verify_login_code(
            telegram_id=999999, code=code_from(_capture_telegram), phone=guardian.phone
        )


# --------------------------------------------------------------------------- #
# The web ticket
# --------------------------------------------------------------------------- #
def test_the_ticket_signs_the_browser_in(api, guardian, guardian_links, _capture_telegram):
    request_login_code(telegram_id=TELEGRAM_ID, phone=guardian.phone)
    result = verify_login_code(
        telegram_id=TELEGRAM_ID, code=code_from(_capture_telegram), phone=guardian.phone
    )
    ticket = result["login_url"].split("ticket=")[1]

    response = api.post(reverse("auth:telegram-login"), {"ticket": ticket}, format="json")
    assert response.status_code == 200
    assert response.data["access"]
    assert response.data["must_set_password"] is True
    assert response.data["user"]["username"] == result["username"]


def test_a_ticket_works_exactly_once(api, guardian, guardian_links, _capture_telegram):
    request_login_code(telegram_id=TELEGRAM_ID, phone=guardian.phone)
    result = verify_login_code(
        telegram_id=TELEGRAM_ID, code=code_from(_capture_telegram), phone=guardian.phone
    )
    ticket = result["login_url"].split("ticket=")[1]

    assert api.post(reverse("auth:telegram-login"), {"ticket": ticket}, format="json").status_code == 200
    replayed = api.post(reverse("auth:telegram-login"), {"ticket": ticket}, format="json")
    assert replayed.status_code == 401
    assert replayed.data["error"]["code"] == "INVALID_TICKET"


def test_a_made_up_ticket_is_refused(api, db):
    response = api.post(
        reverse("auth:telegram-login"), {"ticket": "not-a-real-ticket"}, format="json"
    )
    assert response.status_code == 401


# --------------------------------------------------------------------------- #
# Setting the first password
# --------------------------------------------------------------------------- #
def test_a_telegram_account_sets_its_first_password(
    api, guardian, guardian_links, _capture_telegram
):
    """There is no old password to prove — the account never had one."""
    request_login_code(telegram_id=TELEGRAM_ID, phone=guardian.phone)
    result = verify_login_code(
        telegram_id=TELEGRAM_ID, code=code_from(_capture_telegram), phone=guardian.phone
    )
    ticket = result["login_url"].split("ticket=")[1]

    signed_in = api.post(reverse("auth:telegram-login"), {"ticket": ticket}, format="json")
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {signed_in.data['access']}")

    response = api.post(
        reverse("auth:password-change"),
        {"password": "Yangi!Parol2026", "password_confirm": "Yangi!Parol2026"},
        format="json",
    )
    assert response.status_code == 200

    user = User.objects.get(username=result["username"])
    assert user.check_password("Yangi!Parol2026")
    assert user.must_change_password is False


def test_an_existing_password_still_has_to_be_proved(api, parent_user):
    """Setting a first password must not become a way to skip the old one."""
    from apps.accounts.services.auth import issue_tokens

    access, _refresh, _ttl = issue_tokens(parent_user)
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    response = api.post(
        reverse("auth:password-change"),
        {"password": "Yangi!Parol2026", "password_confirm": "Yangi!Parol2026"},
        format="json",
    )
    assert response.status_code == 400
    assert "current_password" in response.data["error"]["fields"]


# --------------------------------------------------------------------------- #
# Changing the number
# --------------------------------------------------------------------------- #
def test_the_number_can_be_replaced_the_same_way(
    guardian, guardian_links, parent_user, _capture_telegram
):
    from apps.telegram.services.auth import request_phone_change, verify_phone_change

    request_login_code(telegram_id=TELEGRAM_ID, phone=guardian.phone)
    verify_login_code(
        telegram_id=TELEGRAM_ID, code=code_from(_capture_telegram), phone=guardian.phone
    )

    request_phone_change(telegram_id=TELEGRAM_ID, phone="+998901119977")
    verify_phone_change(
        telegram_id=TELEGRAM_ID,
        code=code_from(_capture_telegram),
        phone="+998901119977",
    )

    parent_user.refresh_from_db()
    guardian.refresh_from_db()
    assert parent_user.phone == "+998901119977"
    # The register moves too, or the next sign-in would not find them.
    assert guardian.phone == "+998901119977"


def test_a_number_someone_else_uses_is_refused(
    guardian, guardian_links, parent_user, other_parent, _capture_telegram
):
    from apps.common.exceptions import ConflictError
    from apps.telegram.services.auth import request_phone_change

    request_login_code(telegram_id=TELEGRAM_ID, phone=guardian.phone)
    verify_login_code(
        telegram_id=TELEGRAM_ID, code=code_from(_capture_telegram), phone=guardian.phone
    )

    with pytest.raises(ConflictError) as caught:
        request_phone_change(telegram_id=TELEGRAM_ID, phone=other_parent.phone)
    assert caught.value.code == "PHONE_TAKEN"


def test_changing_a_number_needs_a_linked_chat(db):
    from apps.common.exceptions import ConflictError
    from apps.telegram.services.auth import request_phone_change

    with pytest.raises(ConflictError) as caught:
        request_phone_change(telegram_id=404404, phone="+998901119977")
    assert caught.value.code == "TELEGRAM_NOT_LINKED"


# --------------------------------------------------------------------------- #
# Resending, and remembering the chat
# --------------------------------------------------------------------------- #
def test_a_cooldown_is_an_api_error_not_a_crash(
    api, guardian, guardian_links, parent_user, settings, _capture_telegram
):
    """It escaped unhandled once and answered a 429 case with a 500.

    Checked on an endpoint that never caught it by hand, so it proves the
    central mapping rather than a local `try`.
    """
    from django.urls import reverse

    from apps.telegram.services.auth import verify_login_code

    settings.OTP = {**settings.OTP, "RESEND_COOLDOWN_SECONDS": 600}

    request_login_code(telegram_id=TELEGRAM_ID, phone=guardian.phone)
    verify_login_code(
        telegram_id=TELEGRAM_ID, code=code_from(_capture_telegram), phone=guardian.phone
    )

    payload = {"telegram_id": TELEGRAM_ID, "phone": "+998901119977"}
    headers = {"HTTP_X_BOT_TOKEN": settings.TELEGRAM["SERVICE_TOKEN"]}

    first = api.post(reverse("bot:bot-phone-request"), payload, format="json", **headers)
    assert first.status_code == 200

    second = api.post(reverse("bot:bot-phone-request"), payload, format="json", **headers)
    assert second.status_code == 429
    assert second.data["error"]["code"] == "OTP_COOLDOWN"


def test_resending_replaces_the_code(guardian, settings, _capture_telegram):
    """Pressing "Kodni qayta yuborish" must invalidate the previous one."""
    from apps.common.otp import OTPInvalidError

    settings.OTP = {**settings.OTP, "RESEND_COOLDOWN_SECONDS": 0}

    request_login_code(telegram_id=TELEGRAM_ID, phone=guardian.phone)
    first = code_from(_capture_telegram)
    request_login_code(telegram_id=TELEGRAM_ID, phone=guardian.phone)
    second = code_from(_capture_telegram)

    assert first != second
    with pytest.raises(OTPInvalidError):
        verify_login_code(telegram_id=TELEGRAM_ID, code=first, phone=guardian.phone)


def test_the_chat_number_is_remembered(guardian, _capture_telegram):
    """So a repeat visit is not asked for the same contact again."""
    from apps.telegram.services.auth import known_phone

    assert known_phone(TELEGRAM_ID) == ""
    request_login_code(telegram_id=TELEGRAM_ID, phone=guardian.phone)
    assert known_phone(TELEGRAM_ID) == guardian.phone


def test_a_signed_in_chat_keeps_its_number_without_the_cache(
    guardian, guardian_links, _capture_telegram
):
    from django.core.cache import cache

    from apps.telegram.services.auth import known_phone

    request_login_code(telegram_id=TELEGRAM_ID, phone=guardian.phone)
    verify_login_code(
        telegram_id=TELEGRAM_ID, code=code_from(_capture_telegram), phone=guardian.phone
    )

    cache.clear()
    # Falls back to the account, so a cache flush does not re-prompt everyone.
    assert known_phone(TELEGRAM_ID) == guardian.phone


# --------------------------------------------------------------------------- #
# The code is delivered by the bot but typed on the site
# --------------------------------------------------------------------------- #
def test_sharing_a_contact_does_not_send_a_code(guardian, _capture_telegram):
    """The bot only proves the number; the code is raised by the website."""
    from apps.telegram.services.auth import accept_contact

    result = accept_contact(telegram_id=TELEGRAM_ID, phone=guardian.phone)

    assert result["matched"] is True
    assert result["guardian_name"] == guardian.full_name
    assert _capture_telegram == []


def test_the_registration_code_goes_to_the_paired_chat(
    api, student, guardian, guardian_links, _capture_telegram, monkeypatch
):
    from django.urls import reverse

    from apps.accounts.services import registration as service
    from apps.telegram.services.auth import accept_contact

    sent: list[tuple[int, str]] = []
    monkeypatch.setattr(
        "apps.telegram.services.client.send_message",
        lambda chat_id, text, **kwargs: sent.append((chat_id, text)) or {"message_id": 1},
    )

    accept_contact(telegram_id=TELEGRAM_ID, phone=guardian.phone)

    session = service.identify_guardian(
        student=student,
        relation=guardian_links[0].relation,
        jshshir="31234567890123",
        phone_last4=guardian.phone[-4:],
    )
    result = api.post(
        reverse("registration:otp-request"),
        {"session_token": session.token},
        format="json",
    )

    assert result.status_code == 200
    assert result.data["delivered"] is True
    assert len(sent) == 1
    assert sent[0][0] == TELEGRAM_ID
    # It tells the parent where to type it.
    assert "saytga" in sent[0][1].lower()


def test_without_a_paired_chat_the_response_says_nothing_was_sent(
    api, student, guardian, guardian_links
):
    """No chat and no SMS gateway: say so rather than let them guess."""
    from django.test import override_settings
    from django.urls import reverse

    from apps.accounts.services import registration as service
    from apps.common.sms.registry import _build

    session = service.identify_guardian(
        student=student,
        relation=guardian_links[0].relation,
        jshshir="31234567890123",
        phone_last4=guardian.phone[-4:],
    )
    with override_settings(SMS_PROVIDER="console"):
        _build.cache_clear()
        try:
            response = api.post(
                reverse("registration:otp-request"),
                {"session_token": session.token},
                format="json",
            )
        finally:
            _build.cache_clear()

    assert response.status_code == 200
    assert response.data["delivered"] is False


def test_finishing_on_the_site_links_the_bot(
    api, student, guardian, guardian_links, _capture_telegram, monkeypatch
):
    """The chat that proved the number becomes the account's Telegram link."""
    from apps.accounts.services import registration as service
    from apps.telegram.models import TelegramAccount
    from apps.telegram.services.auth import accept_contact

    monkeypatch.setattr(
        "apps.telegram.services.client.send_message",
        lambda chat_id, text, **kwargs: {"message_id": 1},
    )
    accept_contact(telegram_id=TELEGRAM_ID, phone=guardian.phone)

    session = service.identify_guardian(
        student=student,
        relation=guardian_links[0].relation,
        jshshir="31234567890123",
        phone_last4=guardian.phone[-4:],
    )
    service.request_registration_otp(session)
    session.data["phone_verified"] = True
    service.save_session(session)

    user, _guardian = service.complete_registration(session, password="Yangi!Parol2026")

    assert TelegramAccount.objects.get(user=user).telegram_id == TELEGRAM_ID
