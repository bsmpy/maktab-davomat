"""Sozlamalar → Integratsiyalar: who may look, who may change, what leaks."""
from __future__ import annotations

import pytest
from django.urls import reverse

from apps.accounts.constants import Role
from apps.accounts.models import User
from apps.accounts.services.auth import issue_tokens
from apps.integrations.constants import IntegrationKind
from apps.integrations.models import Integration, Terminal

pytestmark = pytest.mark.django_db

PASSWORD = "Test!Parol2026"


def make_user(username: str, role: str) -> User:
    return User.objects.create_user(username=username, password=PASSWORD, role=role)


def as_user(api, user):
    access, _refresh, _ttl = issue_tokens(user)
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return api


@pytest.fixture
def developer(db):
    return make_user("dev.user", Role.DEVELOPER)


@pytest.fixture
def super_admin(db):
    return make_user("super.admin", Role.SUPER_ADMIN)


# --------------------------------------------------------------------------- #
# Access control
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("role", "expected"),
    [
        (Role.DEVELOPER, 200),
        (Role.SUPER_ADMIN, 200),
        # A school administrator opens the section for Mavzular and
        # Zarrachalar. The integrations inside it stay shut — see the test
        # below, which is what actually guards the credentials.
        (Role.ADMIN, 200),
        # O'quvchilar and Lavozimlar live inside Sozlamalar, and a moderator
        # reads both. Opening the shell writes nothing.
        (Role.MODERATOR, 200),
        (Role.TEACHER, 403),
        (Role.CURATOR, 403),
        (Role.STAFF, 403),
        (Role.PARENT, 403),
    ],
)
def test_who_can_open_settings(api, role, expected):
    user = make_user(f"user.{role.lower()}", role)
    assert as_user(api, user).get(reverse("settings:overview")).status_code == expected


def test_an_admin_is_offered_appearance_but_not_integrations(api):
    """Opening Sozlamalar is not the same as being handed the credentials."""
    admin = make_user("sections.admin", Role.ADMIN)
    sections = {
        row["key"]: row["available"]
        for row in as_user(api, admin).get(reverse("settings:overview")).data["sections"]
    }
    assert sections["appearance"] is True
    assert sections["integrations"] is False


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        (Role.DEVELOPER, 200),
        (Role.SUPER_ADMIN, 200),
        (Role.ADMIN, 403),
        (Role.MODERATOR, 403),
        (Role.TEACHER, 403),
        (Role.CURATOR, 403),
        (Role.STAFF, 403),
        (Role.PARENT, 403),
    ],
)
def test_who_can_read_integrations(api, role, expected):
    user = make_user(f"int.{role.lower()}", role)
    assert as_user(api, user).get(reverse("settings:integrations")).status_code == expected


def test_only_the_developer_may_change_credentials(api, super_admin, developer):
    url = reverse("settings:integration", args=[IntegrationKind.SMS_ESKIZ])
    payload = {"is_enabled": True, "secrets": {"password": "hunter2"}}

    assert as_user(api, super_admin).put(url, payload, format="json").status_code == 403
    assert as_user(api, developer).put(url, payload, format="json").status_code == 200


def test_a_parent_cannot_reach_the_terminal_endpoints(auth_client, school):
    assert auth_client.get(reverse("settings:terminals")).status_code == 403
    assert auth_client.get(reverse("settings:integrations")).status_code == 403


def test_settings_overview_reports_the_role_capabilities(api, developer, super_admin):
    developer_view = as_user(api, developer).get(reverse("settings:overview")).data
    assert developer_view["can_manage_integrations"] is True
    integrations = next(s for s in developer_view["sections"] if s["key"] == "integrations")
    assert integrations["available"] is True
    assert {child["key"] for child in integrations["children"]} == {
        "TELEGRAM_BOT", "SMS_ESKIZ", "FACE_ID", "TERMINALS",
    }

    # A SUPER_ADMIN may open the section but not touch the credentials in it.
    admin_view = as_user(api, super_admin).get(reverse("settings:overview")).data
    assert admin_view["can_manage_integrations"] is False
    assert next(s for s in admin_view["sections"] if s["key"] == "integrations")["available"] is True


# --------------------------------------------------------------------------- #
# Integrations
# --------------------------------------------------------------------------- #
def test_all_four_integrations_are_always_listed(api, developer):
    response = as_user(api, developer).get(reverse("settings:integrations"))
    assert response.status_code == 200
    assert {item["kind"] for item in response.data["results"]} == set(IntegrationKind.values)


def test_secrets_are_only_ever_returned_masked(api, developer):
    url = reverse("settings:integration", args=[IntegrationKind.TELEGRAM_BOT])
    client = as_user(api, developer)
    client.put(url, {"secrets": {"bot_token": "123456:SUPERSECRETTOKEN"}}, format="json")

    response = client.get(url)
    assert response.data["secrets"]["bot_token"] == "••••••OKEN"
    assert "SUPERSECRETTOKEN" not in str(response.data)


def test_secrets_are_encrypted_at_rest(api, developer):
    from django.db import connection

    url = reverse("settings:integration", args=[IntegrationKind.SMS_ESKIZ])
    as_user(api, developer).put(url, {"secrets": {"password": "eskiz-pass"}}, format="json")

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT secrets_encrypted FROM integrations_integration WHERE kind = %s",
            [IntegrationKind.SMS_ESKIZ],
        )
        ciphertext = cursor.fetchone()[0]
    assert "eskiz-pass" not in ciphertext

    integration = Integration.objects.get(kind=IntegrationKind.SMS_ESKIZ)
    assert integration.secret("password") == "eskiz-pass"


def test_a_blank_secret_keeps_the_stored_value(api, developer):
    url = reverse("settings:integration", args=[IntegrationKind.SMS_ESKIZ])
    client = as_user(api, developer)
    client.put(url, {"secrets": {"password": "original"}}, format="json")
    client.put(url, {"is_enabled": True, "secrets": {"password": ""}}, format="json")

    integration = Integration.objects.get(kind=IntegrationKind.SMS_ESKIZ)
    assert integration.secret("password") == "original"
    assert integration.is_enabled is True


def test_config_updates_merge_rather_than_replace(api, developer):
    url = reverse("settings:integration", args=[IntegrationKind.TERMINALS])
    client = as_user(api, developer)
    client.put(url, {"config": {"late_grace_minutes": 10}}, format="json")
    client.put(url, {"config": {"debounce_seconds": 30}}, format="json")

    config = Integration.objects.get(kind=IntegrationKind.TERMINALS).config
    assert config["late_grace_minutes"] == 10
    assert config["debounce_seconds"] == 30


def test_changing_an_integration_is_audited_without_the_secret(api, developer):
    from apps.audit.models import AuditLog

    url = reverse("settings:integration", args=[IntegrationKind.TELEGRAM_BOT])
    as_user(api, developer).put(url, {"secrets": {"bot_token": "leak-me"}}, format="json")

    entries = AuditLog.objects.filter(entity_type="integrations.Integration")
    assert entries.exists()
    assert "leak-me" not in str([e.new_data for e in entries] + [e.metadata for e in entries])


def test_unknown_integration_kind_is_404(api, developer):
    response = as_user(api, developer).get(reverse("settings:integration", args=["NOPE"]))
    assert response.status_code == 404


# --------------------------------------------------------------------------- #
# Terminals
# --------------------------------------------------------------------------- #
def test_creating_a_terminal_stores_the_password_encrypted(api, developer, school):
    response = as_user(api, developer).post(
        reverse("settings:terminals"),
        {
            "school": str(school.id),
            "name": "Asosiy kirish",
            "host": "192.168.1.64",
            "port": 80,
            "username": "admin",
            "password": "device-secret",
            "direction": "BOTH",
        },
        format="json",
    )
    assert response.status_code == 201
    assert "device-secret" not in str(response.data)
    assert response.data["has_password"] is True

    terminal = Terminal.objects.get()
    assert terminal.password == "device-secret"
    assert "device-secret" not in terminal.secrets_encrypted


def test_the_terminal_response_carries_the_ingest_url(api, developer, school):
    response = as_user(api, developer).post(
        reverse("settings:terminals"),
        {"school": str(school.id), "name": "Kirish", "host": "10.0.0.5", "password": "x"},
        format="json",
    )
    terminal = Terminal.objects.get()
    assert response.data["ingest_url"].endswith(f"/terminals/events/{terminal.ingest_token}/")


def test_updating_without_a_password_keeps_the_old_one(api, developer, school):
    client = as_user(api, developer)
    created = client.post(
        reverse("settings:terminals"),
        {"school": str(school.id), "name": "Kirish", "host": "10.0.0.5", "password": "keep-me"},
        format="json",
    ).data

    client.patch(
        reverse("settings:terminal", args=[created["id"]]), {"name": "Yangi nom"}, format="json"
    )
    terminal = Terminal.objects.get()
    assert terminal.name == "Yangi nom"
    assert terminal.password == "keep-me"


def test_deleting_a_terminal_is_soft(api, developer, school):
    client = as_user(api, developer)
    created = client.post(
        reverse("settings:terminals"),
        {"school": str(school.id), "name": "Kirish", "host": "10.0.0.5", "password": "x"},
        format="json",
    ).data

    assert client.delete(reverse("settings:terminal", args=[created["id"]])).status_code == 204
    assert not Terminal.objects.filter(pk=created["id"]).exists()
    assert Terminal.all_objects.filter(pk=created["id"]).exists()


def test_rotating_the_ingest_token_changes_it(api, developer, school):
    client = as_user(api, developer)
    created = client.post(
        reverse("settings:terminals"),
        {"school": str(school.id), "name": "Kirish", "host": "10.0.0.5", "password": "x"},
        format="json",
    ).data
    before = Terminal.objects.get().ingest_token

    client.post(reverse("settings:terminal-rotate-token", args=[created["id"]]), {}, format="json")
    assert Terminal.objects.get().ingest_token != before


def test_a_connection_test_reports_failure_instead_of_crashing(api, developer, school):
    """An unplugged turnstile must not surface as a 500 in the cabinet."""
    client = as_user(api, developer)
    created = client.post(
        reverse("settings:terminals"),
        {
            "school": str(school.id), "name": "Kirish",
            "host": "127.0.0.1", "port": 9, "password": "x",
        },
        format="json",
    ).data

    response = client.post(reverse("settings:terminal-test", args=[created["id"]]), {}, format="json")
    assert response.status_code == 200
    assert response.data["ok"] is False
    assert response.data["message"]

    Terminal.objects.get().refresh_from_db()
    assert Terminal.objects.get().status == "ERROR"


def test_integration_test_button_never_500s(api, developer):
    response = as_user(api, developer).post(
        reverse("settings:integration-test", args=[IntegrationKind.SMS_ESKIZ]), {}, format="json"
    )
    assert response.status_code == 200
    assert response.data["ok"] is False


# --------------------------------------------------------------------------- #
# The health probe and the clock
# --------------------------------------------------------------------------- #
def test_the_health_probe_answers_without_a_login(api):
    from django.urls import reverse

    response = api.get(reverse("health"))
    assert response.status_code == 200
    assert response.data["status"] == "ok"
    assert response.data["checks"] == {"database": True, "cache": True}


def test_the_clock_reports_the_day_the_app_runs_on(api, settings):
    from django.urls import reverse
    from django.utils import timezone

    response = api.get(reverse("clock"))
    assert response.status_code == 200
    assert response.data["date"] == timezone.localdate().isoformat()
    assert response.data["is_shifted"] is False
    assert response.data["offset_seconds"] == 0


def test_a_shifted_clock_moves_the_whole_application(settings):
    """The offset is constant, so time still runs — it just starts elsewhere."""
    from datetime import timedelta

    from django.utils import timezone

    from apps.common import clock

    real = clock.real_now()
    target = (real + timedelta(days=4)).replace(hour=10, minute=10, second=0, microsecond=0)
    seconds = clock.offset_for(target)

    settings.CLOCK_OFFSET_SECONDS = seconds
    try:
        clock.install()
        # Within a second of the target, and the day has moved with it.
        assert abs((timezone.now() - target).total_seconds()) < 2
        assert timezone.localdate() == timezone.localtime(target).date()
    finally:
        clock.uninstall()
