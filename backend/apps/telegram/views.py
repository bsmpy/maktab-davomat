"""Web endpoints: a signed-in parent generates a one-time link code here."""
from __future__ import annotations

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.permissions import IsAuthenticatedActive

from .models import TelegramAccount
from .serializers import TelegramLinkStatusSerializer
from .services import issue_link_token, unlink_telegram_account


def _status_payload(user) -> dict:
    from django.conf import settings

    account = TelegramAccount.objects.filter(user=user, is_active=True).first()
    return {
        "linked": account is not None,
        "username": account.telegram_username if account else "",
        "notifications_enabled": account.notifications_enabled if account else False,
        "linked_at": account.linked_at.isoformat() if account else None,
        "bot_username": settings.TELEGRAM["BOT_USERNAME"],
    }


@extend_schema(tags=["telegram"], responses={200: TelegramLinkStatusSerializer})
class TelegramStatusView(APIView):
    permission_classes = [IsAuthenticatedActive]

    @extend_schema(summary="Telegram ulanish holati")
    def get(self, request):
        return Response(_status_payload(request.user))


@extend_schema(tags=["telegram"], responses={200: OpenApiResponse(description="Bir martalik kod va deep-link")})
class TelegramLinkCodeView(APIView):
    """Issue a single-use code + deep link. Any previous code is invalidated."""

    permission_classes = [IsAuthenticatedActive]

    @extend_schema(request=None, summary="Telegram ulash kodini olish")
    def post(self, request):
        issued = issue_link_token(request.user)
        return Response(
            {
                "code": issued.code,
                "deep_link": issued.deep_link,
                "bot_username": issued.bot_username,
                "expires_at": issued.expires_at.isoformat(),
            }
        )


@extend_schema(tags=["telegram"], responses={200: TelegramLinkStatusSerializer})
class TelegramUnlinkView(APIView):
    permission_classes = [IsAuthenticatedActive]

    @extend_schema(request=None, summary="Telegramni uzish")
    def post(self, request):
        unlinked = unlink_telegram_account(request.user)
        return Response({"unlinked": unlinked, **_status_payload(request.user)})


@extend_schema(tags=["telegram"], responses={200: TelegramLinkStatusSerializer})
class TelegramNotificationToggleView(APIView):
    permission_classes = [IsAuthenticatedActive]

    @extend_schema(request=None, summary="Telegram bildirishnomalarini yoqish/o'chirish")
    def post(self, request):
        account = TelegramAccount.objects.filter(user=request.user).first()
        if account is None:
            return Response(_status_payload(request.user))
        account.notifications_enabled = bool(request.data.get("enabled", not account.notifications_enabled))
        account.save(update_fields=["notifications_enabled", "updated_at"])
        return Response(_status_payload(request.user))
