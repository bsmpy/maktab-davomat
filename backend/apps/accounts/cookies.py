"""Refresh-token cookie handling + double-submit CSRF protection.

Why a cookie at all: a refresh token in ``localStorage`` is readable by any
injected script. HttpOnly removes that class of theft. The cost is CSRF, which
we pay for with a second, JS-readable cookie whose value must be echoed back in
the ``X-Refresh-CSRF`` header — something a cross-origin attacker cannot read.
"""
from __future__ import annotations

import secrets

from django.conf import settings

from apps.common.exceptions import AppError


class CSRFValidationError(AppError):
    status_code = 403
    default_code = "CSRF_FAILED"
    default_detail = "So'rov xavfsizlik tekshiruvidan o'tmadi. Sahifani yangilang."


#: The CSRF companion cookie is scoped to the whole site: the SPA lives at "/"
#: and a cookie is only readable from a matching path, so narrowing it the way
#: the refresh cookie is narrowed would make it unreadable. It carries no
#: authority on its own — its only job is to prove the request came from a page
#: that could read same-origin cookies.
CSRF_COOKIE_PATH = "/"


def _cookie_kwargs(path: str | None = None) -> dict:
    return {
        "domain": settings.AUTH_COOKIE_DOMAIN,
        "secure": settings.AUTH_COOKIE_SECURE,
        "samesite": settings.AUTH_COOKIE_SAMESITE,
        "path": path or settings.AUTH_COOKIE_PATH,
    }


def set_auth_cookies(response, refresh_token: str) -> str:
    """Attach the refresh + CSRF cookies. Returns the CSRF value for the body."""
    max_age = int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds())
    csrf_value = secrets.token_urlsafe(24)

    response.set_cookie(
        settings.AUTH_COOKIE_NAME,
        refresh_token,
        max_age=max_age,
        httponly=True,
        **_cookie_kwargs(),
    )
    response.set_cookie(
        settings.AUTH_CSRF_COOKIE_NAME,
        csrf_value,
        max_age=max_age,
        httponly=False,  # must be readable by the SPA to be echoed back
        **_cookie_kwargs(CSRF_COOKIE_PATH),
    )
    return csrf_value


def clear_auth_cookies(response) -> None:
    for name, path in (
        (settings.AUTH_COOKIE_NAME, settings.AUTH_COOKIE_PATH),
        (settings.AUTH_CSRF_COOKIE_NAME, CSRF_COOKIE_PATH),
    ):
        response.delete_cookie(
            name,
            path=path,
            domain=settings.AUTH_COOKIE_DOMAIN,
            samesite=settings.AUTH_COOKIE_SAMESITE,
        )


def get_refresh_token(request) -> str | None:
    """Prefer the cookie; fall back to the body for non-browser clients."""
    token = request.COOKIES.get(settings.AUTH_COOKIE_NAME)
    if token:
        return token
    data = getattr(request, "data", None) or {}
    return data.get("refresh") or None


def verify_csrf(request) -> None:
    """Enforce the double-submit check for cookie-authenticated endpoints."""
    if not request.COOKIES.get(settings.AUTH_COOKIE_NAME):
        # No cookie in play (body-supplied token) → nothing to protect against.
        return
    cookie_value = request.COOKIES.get(settings.AUTH_CSRF_COOKIE_NAME, "")
    header_value = request.headers.get(settings.AUTH_CSRF_HEADER_NAME, "")
    if not cookie_value or not header_value or not secrets.compare_digest(
        cookie_value, header_value
    ):
        raise CSRFValidationError()
