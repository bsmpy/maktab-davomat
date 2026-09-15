from config.env import env_bool, env_int

from .base import *  # noqa: F401,F403
from .base import DEBUG

assert DEBUG is False, "DJANGO_DEBUG must be False in production."

# When a reverse proxy already redirects http→https (Caddy, a cloud LB), doing
# it again here risks a loop if X-Forwarded-Proto is ever missing.
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

if not SECURE_SSL_REDIRECT:
    # Deliberate: the proxy in front of us owns the redirect. Silencing the
    # check keeps `check --deploy` meaningful instead of permanently noisy.
    SILENCED_SYSTEM_CHECKS = ["security.W008"]
SECURE_HSTS_SECONDS = env_int("SECURE_HSTS_SECONDS", 31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

SESSION_COOKIE_SECURE = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_SAMESITE = "Lax"

# Refuse to boot with a wildcard CORS policy or a dev-only OTP leak.
from .base import CORS_ALLOWED_ORIGINS, OTP  # noqa: E402

assert "*" not in CORS_ALLOWED_ORIGINS, "CORS_ALLOWED_ORIGINS must be explicit in production."
assert not OTP["EXPOSE_IN_RESPONSE"], "OTP_EXPOSE_IN_RESPONSE must be False in production."
