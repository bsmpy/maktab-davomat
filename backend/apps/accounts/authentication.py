"""JWT authentication.

The access token is only ever accepted from the ``Authorization`` header. It is
deliberately *not* readable from a cookie: the SPA keeps it in memory, so a
stolen cookie jar yields no API access, and there is no ambient credential for
a CSRF attack to ride on.

The refresh token does live in a cookie, but it is scoped to
``/api/v1/auth/`` and its endpoints additionally require a double-submit CSRF
header (see :mod:`apps.accounts.cookies`).
"""
from __future__ import annotations

from rest_framework_simplejwt.authentication import JWTAuthentication


class BearerJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        result = super().authenticate(request)
        if result is None:
            return None
        user, token = result
        if not user.is_active:
            return None
        return user, token
