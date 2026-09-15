"""Telegram linking and the server-to-server bot API."""
from __future__ import annotations

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.common.exceptions import ConflictError, NotFoundError
from apps.telegram.authentication import HEADER
from apps.telegram.models import TelegramAccount, TelegramLinkToken
from apps.telegram.services import consume_link_token, issue_link_token

pytestmark = pytest.mark.django_db

TELEGRAM_ID = 700100200
SERVICE_TOKEN = "test-bot-service-token"


@pytest.fixture(autouse=True)
def _bot_settings(settings):
    settings.TELEGRAM = {
        **settings.TELEGRAM,
        "SERVICE_TOKEN": SERVICE_TOKEN,
        "BOT_USERNAME": "davomat_bot",
    }


def bot(api, path, payload):
    return api.post(path, payload, format="json", **{f"HTTP_{HEADER.upper().replace('-', '_')}": SERVICE_TOKEN})


# --------------------------------------------------------------------------- #
# Link tokens
# --------------------------------------------------------------------------- #
def test_link_code_is_issued_to_an_authenticated_parent(auth_client):
    response = auth_client.post(reverse("telegram-link-code"), {}, format="json")
    assert response.status_code == 200
    assert len(response.data["code"]) == 6
    assert response.data["code"].isdigit()
    assert response.data["deep_link"].startswith("https://t.me/davomat_bot?start=")


def test_tokens_are_stored_hashed_not_in_plaintext(parent_user):
    issued = issue_link_token(parent_user)
    token = TelegramLinkToken.objects.get(user=parent_user)
    assert issued.code not in (token.code_hash, token.token_hash)
    assert len(token.code_hash) == 64


def test_issuing_a_new_code_invalidates_the_previous_one(parent_user):
    first = issue_link_token(parent_user)
    issue_link_token(parent_user)
    with pytest.raises(NotFoundError):
        consume_link_token(first.code, telegram_id=TELEGRAM_ID)


def test_code_links_the_account(parent_user):
    issued = issue_link_token(parent_user)
    account = consume_link_token(
        issued.code, telegram_id=TELEGRAM_ID, profile={"username": "azizbek_ota"}
    )
    assert account.user == parent_user
    assert account.telegram_id == TELEGRAM_ID
    assert account.telegram_username == "azizbek_ota"


def test_deep_link_token_also_works(parent_user):
    issued = issue_link_token(parent_user)
    raw = issued.deep_link.split("start=")[1]
    assert consume_link_token(raw, telegram_id=TELEGRAM_ID).user == parent_user


def test_a_token_is_single_use(parent_user):
    issued = issue_link_token(parent_user)
    consume_link_token(issued.code, telegram_id=TELEGRAM_ID)
    with pytest.raises(NotFoundError):
        consume_link_token(issued.code, telegram_id=999999)


def test_an_expired_token_is_rejected(parent_user):
    issued = issue_link_token(parent_user)
    TelegramLinkToken.objects.filter(user=parent_user).update(
        expires_at=timezone.now() - timedelta(seconds=1)
    )
    with pytest.raises(NotFoundError):
        consume_link_token(issued.code, telegram_id=TELEGRAM_ID)


def test_a_telegram_id_cannot_be_stolen_from_another_account(parent_user, other_parent):
    consume_link_token(issue_link_token(parent_user).code, telegram_id=TELEGRAM_ID)
    with pytest.raises(ConflictError):
        consume_link_token(issue_link_token(other_parent).code, telegram_id=TELEGRAM_ID)


def test_link_status_and_unlink(auth_client, parent_user):
    consume_link_token(issue_link_token(parent_user).code, telegram_id=TELEGRAM_ID)
    status = auth_client.get(reverse("telegram-status"))
    assert status.data["linked"] is True

    unlinked = auth_client.post(reverse("telegram-unlink"), {}, format="json")
    assert unlinked.data["unlinked"] is True
    assert unlinked.data["linked"] is False
    assert not TelegramAccount.objects.filter(user=parent_user).exists()


def test_linking_is_audited(parent_user):
    from apps.audit.constants import AuditAction
    from apps.audit.models import AuditLog

    consume_link_token(issue_link_token(parent_user).code, telegram_id=TELEGRAM_ID)
    assert AuditLog.objects.filter(action=AuditAction.TELEGRAM_LINK).exists()


# --------------------------------------------------------------------------- #
# Bot service API
# --------------------------------------------------------------------------- #
def test_bot_endpoints_require_the_service_token(api, parent_user):
    response = api.post(reverse("bot:bot-me"), {"telegram_id": TELEGRAM_ID}, format="json")
    assert response.status_code == 403


def test_a_wrong_service_token_is_rejected(api):
    response = api.post(
        reverse("bot:bot-me"),
        {"telegram_id": TELEGRAM_ID},
        format="json",
        **{f"HTTP_{HEADER.upper().replace('-', '_')}": "wrong"},
    )
    assert response.status_code == 403


def test_an_unlinked_telegram_id_gets_nothing(api, parent_user):
    response = bot(api, reverse("bot:bot-me"), {"telegram_id": 404404})
    assert response.status_code == 404
    assert response.data["error"]["code"] == "TELEGRAM_NOT_LINKED"


def test_bot_link_endpoint(api, parent_user):
    issued = issue_link_token(parent_user)
    response = bot(
        api,
        reverse("bot:bot-link"),
        {"token": issued.code, "telegram_id": TELEGRAM_ID, "profile": {"username": "ota"}},
    )
    assert response.status_code == 201
    assert response.data["user"]["username"] == "a.valiyev"


def test_bot_me_lists_children(api, parent_user, student, sibling):
    consume_link_token(issue_link_token(parent_user).code, telegram_id=TELEGRAM_ID)
    response = bot(api, reverse("bot:bot-me"), {"telegram_id": TELEGRAM_ID})
    assert response.status_code == 200
    names = {child["display_name"] for child in response.data["children"]}
    assert names == {"Azizbek Valiyev", "Madina Valiyeva"}


def test_bot_active_child_switching(api, parent_user, student, sibling):
    consume_link_token(issue_link_token(parent_user).code, telegram_id=TELEGRAM_ID)
    response = bot(
        api,
        reverse("bot:bot-active-child"),
        {"telegram_id": TELEGRAM_ID, "student": str(sibling.id)},
    )
    assert response.status_code == 200
    assert response.data["active_student"]["display_name"] == "Madina Valiyeva"

    account = TelegramAccount.objects.get(telegram_id=TELEGRAM_ID)
    assert account.active_student_id == sibling.id


def test_bot_cannot_switch_to_a_foreign_child(api, parent_user, other_student):
    consume_link_token(issue_link_token(parent_user).code, telegram_id=TELEGRAM_ID)
    response = bot(
        api,
        reverse("bot:bot-active-child"),
        {"telegram_id": TELEGRAM_ID, "student": str(other_student.id)},
    )
    assert response.status_code == 404


def test_bot_attendance_report(api, parent_user, student, present_day):
    from tests.conftest import TODAY

    consume_link_token(issue_link_token(parent_user).code, telegram_id=TELEGRAM_ID)
    response = bot(
        api,
        reverse("bot:bot-attendance"),
        {"telegram_id": TELEGRAM_ID, "period": "daily", "date": TODAY.isoformat()},
    )
    assert response.status_code == 200
    assert response.data["student"]["class_group"] == "7-A"

    report = response.data["report"]
    assert report["first_in"] == "08:24"
    assert report["last_out"] == "13:40"
    assert report["inside_minutes"] == 286
    assert report["summary"]["days_present"] == 1


@pytest.mark.parametrize("period", ["daily", "weekly", "monthly", "yearly"])
def test_bot_supports_every_period(api, parent_user, student, present_day, period):
    consume_link_token(issue_link_token(parent_user).code, telegram_id=TELEGRAM_ID)
    response = bot(
        api, reverse("bot:bot-attendance"), {"telegram_id": TELEGRAM_ID, "period": period}
    )
    assert response.status_code == 200
    assert "summary" in response.data["report"]


def test_bot_notifications_and_settings(api, parent_user, student, terminal, person):
    from apps.integrations.models import TerminalEvent
    from apps.notifications.services import notify_presence
    from tests.conftest import at, pass_through

    consume_link_token(issue_link_token(parent_user).code, telegram_id=TELEGRAM_ID)
    event = pass_through(terminal, "S1001", at(8, 24), serial=900)
    TerminalEvent.objects.filter(pk=event.pk).update(student=student)
    event.refresh_from_db()
    notify_presence(event)

    listed = bot(api, reverse("bot:bot-notifications"), {"telegram_id": TELEGRAM_ID, "limit": 5})
    assert listed.data["unread_count"] == 1
    assert len(listed.data["results"]) == 1

    muted = bot(
        api,
        reverse("bot:bot-settings"),
        {"telegram_id": TELEGRAM_ID, "notifications_enabled": False},
    )
    assert muted.data["notifications_enabled"] is False


def test_bot_unlink(api, parent_user):
    consume_link_token(issue_link_token(parent_user).code, telegram_id=TELEGRAM_ID)
    response = bot(api, reverse("bot:bot-unlink"), {"telegram_id": TELEGRAM_ID})
    assert response.data["unlinked"] is True
    assert not TelegramAccount.objects.filter(telegram_id=TELEGRAM_ID).exists()
