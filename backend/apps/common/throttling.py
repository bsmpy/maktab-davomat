"""Scoped throttles for the abuse-prone anonymous endpoints.

They key on the client IP (behind nginx, ``X-Forwarded-For``'s left-most entry)
so a single host cannot brute force OTPs, logins or the student search.
"""
from __future__ import annotations

from rest_framework.throttling import SimpleRateThrottle


def client_ip(request) -> str:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "") or "unknown"


class ScopedIPThrottle(SimpleRateThrottle):
    scope = "anon"

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": client_ip(request)}


class OTPRequestThrottle(ScopedIPThrottle):
    scope = "otp_request"


class OTPVerifyThrottle(ScopedIPThrottle):
    scope = "otp_verify"


class LoginThrottle(ScopedIPThrottle):
    scope = "login"


class RegistrationThrottle(ScopedIPThrottle):
    scope = "registration"


class StudentSearchThrottle(ScopedIPThrottle):
    scope = "student_search"


class PasswordResetThrottle(ScopedIPThrottle):
    scope = "password_reset"
