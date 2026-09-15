"""drf-spectacular extensions so the schema documents our custom auth."""
from __future__ import annotations

from drf_spectacular.extensions import OpenApiAuthenticationExtension


class BearerJWTScheme(OpenApiAuthenticationExtension):
    target_class = "apps.accounts.authentication.BearerJWTAuthentication"
    name = "jwtAuth"

    def get_security_definition(self, auto_schema):
        return {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": (
                "Short-lived access token from `POST /api/v1/auth/login/`. "
                "The refresh token is delivered as an HttpOnly cookie and is "
                "only accepted by the `/api/v1/auth/` endpoints."
            ),
        }
