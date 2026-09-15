from __future__ import annotations

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.constants import AuditAction
from apps.audit.services import log_action
from apps.common.exceptions import error_response
from apps.common.otp import OTPError
from apps.common.throttling import LoginThrottle, OTPVerifyThrottle, PasswordResetThrottle

from ..cookies import clear_auth_cookies, get_refresh_token, set_auth_cookies, verify_csrf
from ..serializers import (
    ActiveRoleSerializer,
    LoginSerializer,
    PasswordChangeSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    PasswordResetVerifySerializer,
    ProfileSerializer,
    TelegramTicketSerializer,
    TokenResponseSerializer,
    UserSerializer,
)
from ..services import auth as auth_service
from ..services import password_reset as reset_service


def _token_response(user, *, status_code: int = status.HTTP_200_OK, extra: dict | None = None):
    """Access token in the body (kept in memory), refresh token in a cookie."""
    access, refresh, expires_in = auth_service.issue_tokens(user)
    payload = {
        "access": access,
        "expires_in": expires_in,
        "user": UserSerializer(user).data,
    }
    payload.update(extra or {})
    response = Response(payload, status=status_code)
    payload["csrf"] = set_auth_cookies(response, refresh)
    response.data = payload
    return response


@extend_schema(tags=["auth"])
class LoginView(APIView):
    """Sign in with a username **or** a verified phone number."""

    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_classes = [LoginThrottle]

    @extend_schema(
        request=LoginSerializer,
        responses={200: TokenResponseSerializer},
        summary="Tizimga kirish",
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = auth_service.login_user(
            login=serializer.validated_data["login"],
            password=serializer.validated_data["password"],
            request=request,
        )
        return _token_response(user)


@extend_schema(
    tags=["auth"],
    request=TelegramTicketSerializer,
    responses={200: OpenApiResponse(description="Kirish tokenlari")},
    summary="Telegram orqali kirish (bir martalik havola)",
    auth=[],
)
class TelegramTicketLoginView(APIView):
    """Exchange a one-time ticket from the bot for a real session.

    The bot has already proved who this is — the number the school recorded,
    confirmed by a code only that chat received. The ticket is single-use and
    lives for minutes, so a link forwarded to someone else is worthless within
    the hour and worthless immediately once the owner has clicked it.
    """

    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_classes = [LoginThrottle]

    def post(self, request):
        from ..services.onetime import redeem_login_ticket

        serializer = TelegramTicketSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = redeem_login_ticket(serializer.validated_data["ticket"])
        if user is None:
            return error_response(
                "INVALID_TICKET",
                "Havola eskirgan yoki allaqachon ishlatilgan. Botdan yangisini oling.",
                status_code=status.HTTP_401_UNAUTHORIZED,
            )

        auth_service.record_login(user, request)
        log_action(
            AuditAction.TELEGRAM_LOGIN, user=user, entity=user, request=request
        )
        response = _token_response(user)
        response.data["must_set_password"] = (
            not user.has_usable_password() or user.must_change_password
        )
        return response


@extend_schema(tags=["auth"])
class TokenRefreshView(APIView):
    """Rotate the refresh cookie and hand back a fresh access token."""

    permission_classes = [AllowAny]
    authentication_classes: list = []

    @extend_schema(request=None, responses={200: TokenResponseSerializer}, summary="Tokenni yangilash")
    def post(self, request):
        verify_csrf(request)
        raw = get_refresh_token(request)
        if not raw:
            raise auth_service.InvalidRefreshTokenError()
        access, refresh, expires_in, user = auth_service.rotate_refresh_token(raw)
        response = Response(
            {"access": access, "expires_in": expires_in, "user": UserSerializer(user).data}
        )
        response.data["csrf"] = set_auth_cookies(response, refresh)
        return response


@extend_schema(tags=["auth"])
class LogoutView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []

    @extend_schema(request=None, responses={204: None}, summary="Chiqish")
    def post(self, request):
        verify_csrf(request)
        auth_service.logout_user(get_refresh_token(request), request=request)
        response = Response(status=status.HTTP_204_NO_CONTENT)
        clear_auth_cookies(response)
        return response


@extend_schema(tags=["auth"])
class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: ProfileSerializer}, summary="Joriy foydalanuvchi")
    def get(self, request):
        return Response(ProfileSerializer(request.user).data)


@extend_schema(tags=["auth"])
class ActiveRoleView(APIView):
    """Switch which of your roles you are working through.

    One person may be a TEACHER, a CURATOR and a STAFF member at once. Signing
    out and back in to change hats would be absurd, so the switch is a write to
    the account's active role and a fresh pair of tokens — the session, the
    cabinet and the API all follow it immediately, and a browser refresh lands
    on the same role because it is stored on the account rather than in a tab.

    The guard is the point: the role must be one this account actually holds.
    A browser that posts ``DEVELOPER`` gets a 403 whether or not such a role
    exists anywhere.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=ActiveRoleSerializer,
        responses={200: OpenApiResponse(description="Yangi tokenlar va foydalanuvchi")},
        summary="Faol rolni almashtirish",
    )
    def post(self, request):
        from .. import rbac
        from ..audit import log_active_role_switch

        serializer = ActiveRoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        previous = user.role
        rbac.set_active_role(user, serializer.validated_data["role"])
        log_active_role_switch(
            user=user, old_role=previous, new_role=user.role, request=request
        )

        # New tokens: the access token carries the role claim, and a stale one
        # would disagree with the account for as long as it lived.
        response = _token_response(user)
        response.data["user"] = ProfileSerializer(user).data
        return response


@extend_schema(tags=["auth"])
class PasswordChangeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=PasswordChangeSerializer, responses={200: None}, summary="Parolni o'zgartirish"
    )
    def post(self, request):
        serializer = PasswordChangeSerializer(
            data=request.data, context={"user": request.user}
        )
        serializer.is_valid(raise_exception=True)

        user = request.user
        user.set_password(serializer.validated_data["password"])
        user.must_change_password = False
        user.save(update_fields=["password", "must_change_password", "updated_at"])

        # Old refresh tokens must not survive a password change.
        reset_service.revoke_all_sessions(user)
        log_action(AuditAction.PASSWORD_CHANGE, user=user, entity=user, request=request)

        response = _token_response(user)
        response.data["detail"] = "Parol muvaffaqiyatli o'zgartirildi."
        return response


@extend_schema(tags=["auth"])
class PasswordResetRequestView(APIView):
    """Send a reset code to the account's registered phone.

    Responds identically whether or not the account exists.
    """

    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_classes = [PasswordResetThrottle]

    @extend_schema(
        request=PasswordResetRequestSerializer,
        responses={200: OpenApiResponse(description="Kod yuborildi (akkaunt mavjud bo'lsa)")},
        summary="Parolni tiklashni boshlash",
    )
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = reset_service.start_reset(serializer.validated_data["login"])
        except OTPError as exc:
            return Response(
                {
                    "success": False,
                    "error": {"code": exc.code, "message": str(exc), "fields": {}},
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        return Response(
            {
                "detail": (
                    "Agar bunday akkaunt mavjud bo'lsa, ro'yxatdan o'tgan telefon "
                    "raqamiga tasdiqlash kodi yuborildi."
                ),
                **result,
            }
        )


@extend_schema(tags=["auth"])
class PasswordResetVerifyView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_classes = [OTPVerifyThrottle]

    @extend_schema(
        request=PasswordResetVerifySerializer,
        responses={200: OpenApiResponse(description="Kod tasdiqlandi")},
        summary="Tiklash kodini tasdiqlash",
    )
    def post(self, request):
        serializer = PasswordResetVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            reset_service.verify_reset_otp(
                serializer.validated_data["session_token"], serializer.validated_data["code"]
            )
        except OTPError as exc:
            return Response(
                {"success": False, "error": {"code": exc.code, "message": str(exc), "fields": {}}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({"verified": True})


@extend_schema(tags=["auth"])
class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_classes = [PasswordResetThrottle]

    @extend_schema(
        request=PasswordResetConfirmSerializer,
        responses={200: OpenApiResponse(description="Yangi access token va foydalanuvchi")},
        summary="Yangi parolni saqlash",
    )
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = reset_service.confirm_reset(
            serializer.validated_data["session_token"],
            serializer.validated_data["password"],
            request=request,
        )
        return _token_response(user)
