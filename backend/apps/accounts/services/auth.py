"""Login, token issuing and rotation."""
from __future__ import annotations

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.db.models import Q
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.audit.constants import AuditAction
from apps.audit.services import log_action
from apps.common.exceptions import AppError
from apps.common.phone import InvalidPhoneNumber, normalize_phone
from apps.common.throttling import client_ip


class InvalidCredentialsError(AppError):
    status_code = 401
    default_code = "INVALID_CREDENTIALS"
    default_detail = "Login yoki parol noto'g'ri."


class AccountDisabledError(AppError):
    status_code = 403
    default_code = "ACCOUNT_DISABLED"
    default_detail = "Akkaunt bloklangan. Maktab ma'muriyatiga murojaat qiling."


class InvalidRefreshTokenError(AppError):
    status_code = 401
    default_code = "INVALID_REFRESH_TOKEN"
    default_detail = "Sessiya muddati tugagan. Iltimos, qaytadan kiring."


def resolve_user(login: str):
    """Look a user up by username *or* verified phone number."""
    from apps.accounts.models import User

    login = (login or "").strip()
    if not login:
        return None

    lookup = Q(username__iexact=login)
    try:
        lookup |= Q(phone=normalize_phone(login), phone_verified_at__isnull=False)
    except InvalidPhoneNumber:
        pass
    return User.objects.filter(lookup).first()


def login_user(*, login: str, password: str, request=None):
    user = resolve_user(login)
    if user is None:
        # Run the hasher anyway so a missing account is not distinguishable
        # from a wrong password by response time.
        from apps.accounts.models import User as UserModel

        UserModel().set_password(password)
        user_login_failed.send(
            sender=__name__, credentials={"username": login}, request=request
        )
        raise InvalidCredentialsError()

    authenticated = authenticate(request=request, username=user.username, password=password)
    if authenticated is None:
        if not user.is_active:
            raise AccountDisabledError()
        raise InvalidCredentialsError()
    if not authenticated.is_active:
        raise AccountDisabledError()

    record_login(authenticated, request)
    return authenticated


def record_login(user, request=None):
    """Stamp the sign-in. Shared by every route into an account.

    A Telegram sign-in is as much a login as a password one — same IP stamp,
    same ``last_login`` update, same signal — so both go through here.
    """
    if request is not None:
        ip = client_ip(request)
        if ip and ip != "unknown":
            user.last_login_ip = ip
            user.save(update_fields=["last_login_ip", "updated_at"])
    user_logged_in.send(sender=user.__class__, request=request, user=user)
    return user


def issue_tokens(user) -> tuple[str, str, int]:
    """Returns ``(access, refresh, access_expires_in_seconds)``."""
    refresh = RefreshToken.for_user(user)
    refresh["role"] = user.role
    access = refresh.access_token
    access["role"] = user.role
    lifetime = int(settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"].total_seconds())
    return str(access), str(refresh), lifetime


def rotate_refresh_token(raw_refresh: str) -> tuple[str, str, int, object]:
    """Validate, blacklist and re-issue. Returns ``(access, refresh, ttl, user)``."""
    from apps.accounts.models import User

    try:
        token = RefreshToken(raw_refresh)
    except TokenError as exc:
        raise InvalidRefreshTokenError() from exc

    user = User.objects.filter(pk=token.get("user_id"), is_active=True).first()
    if user is None:
        raise InvalidRefreshTokenError()

    if settings.SIMPLE_JWT.get("BLACKLIST_AFTER_ROTATION"):
        try:
            token.blacklist()
        except AttributeError:  # pragma: no cover - blacklist app disabled
            pass

    access, refresh, ttl = issue_tokens(user)
    return access, refresh, ttl, user


def logout_user(raw_refresh: str | None, *, user=None, request=None) -> None:
    if raw_refresh:
        try:
            RefreshToken(raw_refresh).blacklist()
        except (TokenError, AttributeError):
            # An already-expired or already-blacklisted token is a no-op.
            pass
    log_action(AuditAction.LOGOUT, user=user, request=request)
