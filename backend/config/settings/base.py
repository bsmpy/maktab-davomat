"""Shared Django settings.

Environment specific overrides live in ``dev.py`` / ``prod.py`` / ``test.py``.
Select one with ``DJANGO_SETTINGS_MODULE`` (defaults to ``config.settings.dev``).
"""
from __future__ import annotations

from datetime import timedelta

import dj_database_url

from config.env import BASE_DIR, env, env_bool, env_int, env_list

# --------------------------------------------------------------------------- #
# Core
# --------------------------------------------------------------------------- #
SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env_bool("DJANGO_DEBUG", False)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", ["localhost", "127.0.0.1"])

# Public URLs used to build links (Telegram deep-links, password reset, ...).
FRONTEND_URL = env("FRONTEND_URL", "http://localhost:5173").rstrip("/")
BACKEND_URL = env("BACKEND_URL", "http://localhost:8000").rstrip("/")

# A demo clock: seconds added to every time the application reads, so a
# timetable can be shown on a weekday that has not arrived yet. 0 = real time,
# which is what a real deployment runs on. See apps/common/clock.py.
CLOCK_OFFSET_SECONDS = env_int("CLOCK_OFFSET_SECONDS", 0)

INSTALLED_APPS = [
    # No "django.contrib.admin": administration is the SPA's /admin/ route,
    # talking to /api/v1/management/. Leaving the built-in
    # one installed would keep a second, session-cookie login surface alive for
    # no reason.
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    # third party
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_filters",
    "drf_spectacular",
    "django_celery_beat",
    # local
    "apps.common",
    "apps.accounts",
    "apps.schools",
    "apps.students",
    "apps.guardians",
    "apps.attendance",
    "apps.notifications",
    "apps.telegram",
    "apps.integrations",
    "apps.audit",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.audit.middleware.RequestContextMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
            ],
        },
    },
]

# --------------------------------------------------------------------------- #
# Database
# --------------------------------------------------------------------------- #
DATABASES = {
    "default": dj_database_url.parse(
        env("DATABASE_URL"),
        conn_max_age=env_int("DATABASE_CONN_MAX_AGE", 60),
        conn_health_checks=True,
    )
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --------------------------------------------------------------------------- #
# Cache / Celery
# --------------------------------------------------------------------------- #
REDIS_URL = env("REDIS_URL", "redis://127.0.0.1:6379/0")

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
        "KEY_PREFIX": env("CACHE_KEY_PREFIX", "attendance"),
    }
}

CELERY_BROKER_URL = env("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", REDIS_URL)
CELERY_TASK_ALWAYS_EAGER = env_bool("CELERY_TASK_ALWAYS_EAGER", False)
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_TIMEZONE = "Asia/Tashkent"
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

# --------------------------------------------------------------------------- #
# Auth
# --------------------------------------------------------------------------- #
AUTH_USER_MODEL = "accounts.User"

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
    {"NAME": "apps.accounts.validators.PasswordStrengthValidator"},
]

# --------------------------------------------------------------------------- #
# i18n / timezone
# --------------------------------------------------------------------------- #
LANGUAGE_CODE = "uz"
TIME_ZONE = "Asia/Tashkent"
USE_I18N = True
USE_TZ = True

# --------------------------------------------------------------------------- #
# Static / media
# --------------------------------------------------------------------------- #
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# --------------------------------------------------------------------------- #
# DRF
# --------------------------------------------------------------------------- #
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "apps.accounts.authentication.BearerJWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_RENDERER_CLASSES": ("rest_framework.renderers.JSONRenderer",),
    "DEFAULT_PAGINATION_CLASS": "apps.common.pagination.DefaultPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": ("django_filters.rest_framework.DjangoFilterBackend",),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "apps.common.exceptions.api_exception_handler",
    "DEFAULT_THROTTLE_CLASSES": (),
    "DEFAULT_THROTTLE_RATES": {
        "otp_request": env("THROTTLE_OTP_REQUEST", "5/hour"),
        "otp_verify": env("THROTTLE_OTP_VERIFY", "10/hour"),
        "login": env("THROTTLE_LOGIN", "10/hour"),
        "registration": env("THROTTLE_REGISTRATION", "20/hour"),
        "student_search": env("THROTTLE_STUDENT_SEARCH", "30/hour"),
        "password_reset": env("THROTTLE_PASSWORD_RESET", "5/hour"),
        "user": env("THROTTLE_USER", "1000/hour"),
    },
    "UNAUTHENTICATED_USER": None,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Maktab Davomat API",
    "DESCRIPTION": (
        "Parent-facing school attendance API. "
        "JWT access tokens are sent in the `Authorization: Bearer` header; "
        "the refresh token lives in an HttpOnly cookie."
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SCHEMA_PATH_PREFIX": "/api/v1",
    "COMPONENT_SPLIT_REQUEST": True,
    "SORT_OPERATIONS": False,
    # Several models legitimately have "status"/"direction" choice fields;
    # name their enums explicitly so the schema stays readable.
    "ENUM_NAME_OVERRIDES": {
        "IntegrationStatusEnum": "apps.integrations.constants.IntegrationStatus.choices",
        "TerminalDirectionEnum": "apps.integrations.constants.TerminalDirection.choices",
        "EventDirectionEnum": "apps.integrations.constants.EventDirection.choices",
        "AbsenceRequestStatusEnum": "apps.attendance.constants.AbsenceRequestStatus.choices",
        "AttendanceStatusEnum": "apps.attendance.constants.AttendanceStatus.choices",
        "DeliveryStatusEnum": "apps.notifications.constants.DeliveryStatus.choices",
        "SyncStateEnum": "apps.integrations.constants.SyncState.choices",
    },
}

# --------------------------------------------------------------------------- #
# JWT
# --------------------------------------------------------------------------- #
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=env_int("JWT_ACCESS_MINUTES", 15)),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=env_int("JWT_REFRESH_DAYS", 14)),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": env("JWT_SIGNING_KEY", SECRET_KEY),
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "TOKEN_TYPE_CLAIM": "token_type",
    "JTI_CLAIM": "jti",
}

# Refresh token cookie. The access token is never persisted by the SPA: it is
# kept in memory only, so an XSS payload cannot read a long-lived credential.
AUTH_COOKIE_NAME = env("AUTH_COOKIE_NAME", "refresh_token")
AUTH_COOKIE_PATH = env("AUTH_COOKIE_PATH", "/api/v1/auth/")
AUTH_COOKIE_DOMAIN = env("AUTH_COOKIE_DOMAIN", "") or None
AUTH_COOKIE_SECURE = env_bool("AUTH_COOKIE_SECURE", not DEBUG)
AUTH_COOKIE_SAMESITE = env("AUTH_COOKIE_SAMESITE", "Lax")
# Readable companion cookie used for double-submit CSRF protection on the
# cookie-authenticated endpoints (refresh / logout).
AUTH_CSRF_COOKIE_NAME = env("AUTH_CSRF_COOKIE_NAME", "refresh_csrf")
AUTH_CSRF_HEADER_NAME = "X-Refresh-CSRF"

# --------------------------------------------------------------------------- #
# CORS / CSRF
# --------------------------------------------------------------------------- #
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", ["http://localhost:5173"])
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = (
    "accept",
    "accept-language",
    "authorization",
    "content-type",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
    "x-refresh-csrf",
    "accept-encoding",
)
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", ["http://localhost:5173"])
CSRF_COOKIE_HTTPONLY = False
SESSION_COOKIE_HTTPONLY = True

# --------------------------------------------------------------------------- #
# Domain configuration
# --------------------------------------------------------------------------- #
# Sensitive-field encryption / hashing. Generate with:
#   python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())"
FIELD_ENCRYPTION_KEY = env("FIELD_ENCRYPTION_KEY")
# Pepper for the deterministic JSHSHIR lookup hash. Rotating it invalidates lookups.
JSHSHIR_HASH_KEY = env("JSHSHIR_HASH_KEY")

OTP = {
    "LENGTH": env_int("OTP_LENGTH", 6),
    "TTL_SECONDS": env_int("OTP_TTL_SECONDS", 300),
    "MAX_ATTEMPTS": env_int("OTP_MAX_ATTEMPTS", 5),
    "RESEND_COOLDOWN_SECONDS": env_int("OTP_RESEND_COOLDOWN_SECONDS", 60),
    # Never enable in production: echoes the code into the API response/logs.
    "EXPOSE_IN_RESPONSE": env_bool("OTP_EXPOSE_IN_RESPONSE", False),
}
SMS_PROVIDER = env("SMS_PROVIDER", "console")  # console | eskiz | http | dummy
SMS_PROVIDER_SETTINGS = {
    "base_url": env("SMS_API_URL", ""),
    "token": env("SMS_API_TOKEN", ""),
    "sender": env("SMS_SENDER", ""),
    "timeout": env_int("SMS_TIMEOUT", 10),
}

REGISTRATION = {
    "SESSION_TTL_SECONDS": env_int("REGISTRATION_SESSION_TTL_SECONDS", 1800),
    "STUDENT_SEARCH_MIN_QUERY": env_int("STUDENT_SEARCH_MIN_QUERY", 3),
    "STUDENT_SEARCH_MAX_RESULTS": env_int("STUDENT_SEARCH_MAX_RESULTS", 8),
    "IDENTIFY_MAX_ATTEMPTS": env_int("REGISTRATION_IDENTIFY_MAX_ATTEMPTS", 5),
}

TELEGRAM = {
    "BOT_TOKEN": env("TELEGRAM_BOT_TOKEN", ""),
    "BOT_USERNAME": env("TELEGRAM_BOT_USERNAME", ""),
    # Shared secret for server-to-server calls from the aiogram process.
    "SERVICE_TOKEN": env("BOT_SERVICE_TOKEN", ""),
    "LINK_TOKEN_TTL_SECONDS": env_int("TELEGRAM_LINK_TOKEN_TTL_SECONDS", 900),
    "API_TIMEOUT": env_int("TELEGRAM_API_TIMEOUT", 10),
}

# --------------------------------------------------------------------------- #
# Logging — never log secrets, OTP codes, tokens or full JSHSHIR.
# --------------------------------------------------------------------------- #
LOG_LEVEL = env("LOG_LEVEL", "INFO")
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {"redact": {"()": "apps.common.logging.RedactingFilter"}},
    "formatters": {
        "standard": {
            "format": "%(asctime)s %(levelname)s [%(name)s] %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
            "filters": ["redact"],
        },
    },
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
    "loggers": {
        "django.db.backends": {"level": "WARNING", "handlers": ["console"], "propagate": False},
        "apps": {"level": LOG_LEVEL, "handlers": ["console"], "propagate": False},
    },
}
