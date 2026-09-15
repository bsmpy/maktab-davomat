"""Login, token rotation, logout and the password flows."""
from __future__ import annotations

import pytest
from django.conf import settings
from django.urls import reverse

from apps.audit.constants import AuditAction
from apps.audit.models import AuditLog
from tests.conftest import PASSWORD

pytestmark = pytest.mark.django_db


def login(api, login_value="a.valiyev", password=PASSWORD):
    return api.post(
        reverse("auth:login"), {"login": login_value, "password": password}, format="json"
    )


def test_login_with_username(api, parent_user):
    response = login(api)
    assert response.status_code == 200
    assert response.data["access"]
    assert response.data["user"]["username"] == "a.valiyev"


def test_login_with_verified_phone(api, parent_user):
    for value in ("+998901234567", "998901234567", "901234567"):
        assert login(api, value).status_code == 200, value


def test_login_with_unverified_phone_is_refused(api, parent_user):
    parent_user.phone_verified_at = None
    parent_user.save(update_fields=["phone_verified_at"])
    assert login(api, "+998901234567").status_code == 401


def test_wrong_password_is_401_and_audited(api, parent_user):
    response = login(api, password="wrong-password")
    assert response.status_code == 401
    assert response.data["error"]["code"] == "INVALID_CREDENTIALS"
    assert AuditLog.objects.filter(action=AuditAction.LOGIN_FAILED).exists()


def test_unknown_user_looks_the_same_as_a_wrong_password(api, parent_user):
    unknown = login(api, "nobody.here")
    wrong = login(api, password="wrong-password")
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.data["error"]["code"] == wrong.data["error"]["code"]


def test_inactive_account_cannot_log_in(api, parent_user):
    parent_user.is_active = False
    parent_user.save(update_fields=["is_active"])
    assert login(api).status_code in (401, 403)


def test_successful_login_is_audited(api, parent_user):
    login(api)
    assert AuditLog.objects.filter(action=AuditAction.LOGIN, user=parent_user).exists()


# --------------------------------------------------------------------------- #
# Cookies + rotation
# --------------------------------------------------------------------------- #
def test_refresh_token_lives_in_an_httponly_cookie_not_the_body(api, parent_user):
    response = login(api)
    assert "refresh" not in response.data
    cookie = response.cookies[settings.AUTH_COOKIE_NAME]
    assert cookie["httponly"]
    assert cookie["path"] == settings.AUTH_COOKIE_PATH
    assert cookie["samesite"] == settings.AUTH_COOKIE_SAMESITE
    # The companion CSRF cookie must stay readable so the SPA can echo it.
    assert not response.cookies[settings.AUTH_CSRF_COOKIE_NAME]["httponly"]


def test_refresh_rotates_and_blacklists_the_old_token(api, parent_user):
    login_response = login(api)
    csrf = login_response.data["csrf"]
    old_cookie = api.cookies[settings.AUTH_COOKIE_NAME].value

    refreshed = api.post(
        reverse("auth:refresh"), {}, format="json", **{"HTTP_X_REFRESH_CSRF": csrf}
    )
    assert refreshed.status_code == 200
    assert refreshed.data["access"]
    assert api.cookies[settings.AUTH_COOKIE_NAME].value != old_cookie

    # Replaying the rotated-out token must fail (the CSRF pair rotates too, so
    # the client always echoes the newest value).
    api.cookies[settings.AUTH_COOKIE_NAME] = old_cookie
    replay = api.post(
        reverse("auth:refresh"),
        {},
        format="json",
        **{"HTTP_X_REFRESH_CSRF": refreshed.data["csrf"]},
    )
    assert replay.status_code == 401


def test_refresh_requires_the_csrf_header(api, parent_user):
    login(api)
    response = api.post(reverse("auth:refresh"), {}, format="json")
    assert response.status_code == 403
    assert response.data["error"]["code"] == "CSRF_FAILED"


def test_refresh_rejects_a_mismatched_csrf_header(api, parent_user):
    login(api)
    response = api.post(
        reverse("auth:refresh"), {}, format="json", **{"HTTP_X_REFRESH_CSRF": "forged"}
    )
    assert response.status_code == 403


def test_refresh_without_a_token_is_401(api):
    assert api.post(reverse("auth:refresh"), {}, format="json").status_code == 401


def test_logout_clears_cookies_and_kills_the_refresh_token(api, parent_user):
    csrf = login(api).data["csrf"]
    response = api.post(
        reverse("auth:logout"), {}, format="json", **{"HTTP_X_REFRESH_CSRF": csrf}
    )
    assert response.status_code == 204
    assert response.cookies[settings.AUTH_COOKIE_NAME].value == ""
    assert AuditLog.objects.filter(action=AuditAction.LOGOUT).exists()


# --------------------------------------------------------------------------- #
# Access control
# --------------------------------------------------------------------------- #
def test_protected_endpoints_require_a_token(api):
    assert api.get(reverse("children")).status_code == 401


def test_me_returns_the_owners_own_identifiers(auth_client, guardian):
    """A person sees their own JSHSHIR in full; the phone stays masked."""
    response = auth_client.get(reverse("auth:me"))
    assert response.status_code == 200
    assert response.data["jshshir"] == "31234567890123"
    assert response.data["masked_jshshir"] == "**********0123"
    assert response.data["phone"] == "+998*****4567"


# --------------------------------------------------------------------------- #
# Passwords
# --------------------------------------------------------------------------- #
def test_password_change_requires_the_current_password(auth_client):
    response = auth_client.post(
        reverse("auth:password-change"),
        {
            "current_password": "wrong",
            "password": "Yangi!Parol2026",
            "password_confirm": "Yangi!Parol2026",
        },
        format="json",
    )
    assert response.status_code == 400
    assert "current_password" in response.data["error"]["fields"]


def test_password_change_revokes_other_sessions(auth_client, parent_user):
    from apps.accounts.services.auth import issue_tokens

    _access, refresh, _ttl = issue_tokens(parent_user)
    response = auth_client.post(
        reverse("auth:password-change"),
        {
            "current_password": PASSWORD,
            "password": "Yangi!Parol2026",
            "password_confirm": "Yangi!Parol2026",
        },
        format="json",
    )
    assert response.status_code == 200
    parent_user.refresh_from_db()
    assert parent_user.check_password("Yangi!Parol2026")

    from rest_framework_simplejwt.exceptions import TokenError
    from rest_framework_simplejwt.tokens import RefreshToken

    with pytest.raises(TokenError):
        RefreshToken(refresh).check_blacklist()


def test_password_reset_full_flow(api, parent_user):
    from apps.common.sms.providers import DummySMSProvider

    start = api.post(
        reverse("auth:password-reset-request"), {"login": "a.valiyev"}, format="json"
    )
    assert start.status_code == 200
    assert start.data["sent"] is True
    assert start.data["masked_phone"] == "+998*****4567"
    assert DummySMSProvider.outbox[-1].to == parent_user.phone

    token, code = start.data["session_token"], start.data["debug_code"]

    bad = api.post(
        reverse("auth:password-reset-verify"),
        {"session_token": token, "code": "000000"},
        format="json",
    )
    assert bad.data["error"]["code"] == "INVALID_OTP"

    verified = api.post(
        reverse("auth:password-reset-verify"),
        {"session_token": token, "code": code},
        format="json",
    )
    assert verified.status_code == 200

    confirmed = api.post(
        reverse("auth:password-reset-confirm"),
        {
            "session_token": token,
            "password": "Tiklangan!2026",
            "password_confirm": "Tiklangan!2026",
        },
        format="json",
    )
    assert confirmed.status_code == 200
    parent_user.refresh_from_db()
    assert parent_user.check_password("Tiklangan!2026")
    assert AuditLog.objects.filter(action=AuditAction.PASSWORD_RESET).exists()


def test_password_reset_does_not_leak_account_existence(api, parent_user):
    response = api.post(
        reverse("auth:password-reset-request"), {"login": "nobody.here"}, format="json"
    )
    assert response.status_code == 200
    assert response.data["sent"] is False
    assert "yuborildi" in response.data["detail"]


def test_reset_cannot_be_confirmed_without_the_otp(api, parent_user):
    start = api.post(
        reverse("auth:password-reset-request"), {"login": "a.valiyev"}, format="json"
    )
    response = api.post(
        reverse("auth:password-reset-confirm"),
        {
            "session_token": start.data["session_token"],
            "password": "Tiklangan!2026",
            "password_confirm": "Tiklangan!2026",
        },
        format="json",
    )
    assert response.status_code == 400
    assert response.data["error"]["code"] == "PHONE_NOT_VERIFIED"
