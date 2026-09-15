"""Endpoints consumed exclusively by the aiogram bot.

All business logic (permissions, aggregation, formatting inputs) stays here so
the bot process is a thin presentation layer:

    Telegram → aiogram → Django REST API → PostgreSQL
"""
from __future__ import annotations

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.attendance.services import (
    build_daily_presence,
    build_monthly_presence,
    build_weekly_presence,
    build_yearly_presence,
    student_card,
)
from apps.attendance.services.periods import today
from apps.common.exceptions import NotFoundError
from apps.guardians.selectors import children_links
from apps.notifications.models import Notification

from .authentication import IsBotService
from .models import TelegramAccount
from .serializers import (
    BotActiveChildSerializer,
    BotAttendanceSerializer,
    BotAuthVerifySerializer,
    BotContactSerializer,
    BotIdentitySerializer,
    BotLinkSerializer,
    BotNotificationsSerializer,
    BotSettingsSerializer,
)
from .services import consume_link_token, unlink_telegram_account


class BotServiceView(APIView):
    """Base view: shared-secret auth, no session, no user JWT."""

    permission_classes = [IsBotService]
    authentication_classes: list = []

    def get_account(self, telegram_id: int) -> TelegramAccount:
        account = (
            TelegramAccount.objects.select_related("user", "active_student")
            .filter(telegram_id=telegram_id, is_active=True)
            .first()
        )
        if account is None or not account.user.is_active:
            raise NotFoundError(
                "Telegram akkaunt ulanmagan. Saytdagi kodni yuboring.",
                code="TELEGRAM_NOT_LINKED",
            )
        return account

    def resolve_student(self, account: TelegramAccount, student_id=None):
        links = children_links(account.user)
        if student_id:
            link = links.filter(student_id=student_id).first()
            if link is None:
                raise NotFoundError("Farzand topilmadi.", code="STUDENT_NOT_FOUND")
            return link.student
        if account.active_student_id:
            link = links.filter(student_id=account.active_student_id).first()
            if link is not None:
                return link.student
        link = links.first()
        if link is None:
            raise NotFoundError(
                "Sizga biriktirilgan farzand topilmadi.", code="NO_CHILDREN"
            )
        return link.student


@extend_schema(
    tags=["bot"],
    request=BotLinkSerializer,
    responses={201: OpenApiResponse(description="Ulandi")},
    summary="Telegramni akkauntga ulash",
)
class BotLinkView(BotServiceView):
    def post(self, request):
        serializer = BotLinkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        account = consume_link_token(
            serializer.validated_data["token"],
            telegram_id=serializer.validated_data["telegram_id"],
            profile=serializer.validated_data.get("profile") or {},
        )
        return Response(
            {
                "linked": True,
                "user": {"username": account.user.username, "full_name": account.user.full_name},
            },
            status=status.HTTP_201_CREATED,
        )


@extend_schema(
    tags=["bot"],
    request=BotIdentitySerializer,
    responses={200: OpenApiResponse(description="Foydalanuvchi va farzandlar")},
    summary="Bot foydalanuvchisi",
)
class BotMeView(BotServiceView):
    def post(self, request):
        serializer = BotIdentitySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        account = self.get_account(serializer.validated_data["telegram_id"])
        account.touch()
        links = list(children_links(account.user))
        return Response(
            {
                "user": {
                    "username": account.user.username,
                    "full_name": account.user.full_name,
                },
                "notifications_enabled": account.notifications_enabled,
                "active_student_id": str(account.active_student_id)
                if account.active_student_id
                else (str(links[0].student_id) if links else None),
                "children": [
                    student_card(link.student, relation=link.relation) for link in links
                ],
            }
        )


@extend_schema(
    tags=["bot"],
    request=BotIdentitySerializer,
    responses={200: OpenApiResponse(description="Farzandlar")},
    summary="Farzandlar ro'yxati",
)
class BotChildrenView(BotServiceView):
    def post(self, request):
        serializer = BotIdentitySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        account = self.get_account(serializer.validated_data["telegram_id"])
        links = list(children_links(account.user))
        # Report the child the bot would actually answer about, so the caller
        # can highlight it even before an explicit choice has been made.
        active_ids = {str(link.student_id) for link in links}
        active_id = str(account.active_student_id) if account.active_student_id else None
        if active_id not in active_ids:
            active_id = str(links[0].student_id) if links else None
        return Response(
            {
                "active_student_id": active_id,
                "results": [student_card(link.student, relation=link.relation) for link in links],
            }
        )


@extend_schema(
    tags=["bot"],
    request=BotActiveChildSerializer,
    responses={200: OpenApiResponse(description="Faol farzand")},
    summary="Faol farzandni tanlash",
)
class BotSetActiveChildView(BotServiceView):
    def post(self, request):
        serializer = BotActiveChildSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        account = self.get_account(serializer.validated_data["telegram_id"])
        student = self.resolve_student(account, serializer.validated_data["student"])
        account.active_student = student
        account.save(update_fields=["active_student", "updated_at"])
        return Response({"active_student": student_card(student)})


@extend_schema(
    tags=["bot"],
    request=BotAttendanceSerializer,
    responses={200: OpenApiResponse(description="Davomat hisoboti")},
    summary="Davomat hisoboti",
)
class BotAttendanceView(BotServiceView):
    def post(self, request):
        serializer = BotAttendanceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        account = self.get_account(data["telegram_id"])
        account.touch()
        student = self.resolve_student(account, data["student"])
        day = data["date"] or today()

        if data["period"] == "weekly":
            report = build_weekly_presence(student, day)
        elif data["period"] == "monthly":
            report = build_monthly_presence(student, day.year, day.month, include_grid=False)
        elif data["period"] == "yearly":
            report = build_yearly_presence(student)
        else:
            report = build_daily_presence(student, day)

        return Response(
            {"period": data["period"], "student": student_card(student), "report": report}
        )


@extend_schema(
    tags=["bot"],
    request=BotNotificationsSerializer,
    responses={200: OpenApiResponse(description="Bildirishnomalar")},
    summary="Bildirishnomalar",
)
class BotNotificationsView(BotServiceView):
    def post(self, request):
        serializer = BotNotificationsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        account = self.get_account(data["telegram_id"])

        queryset = Notification.objects.for_user(account.user).with_student().order_by("-created_at")
        if data["only_unread"]:
            queryset = queryset.unread()

        return Response(
            {
                "unread_count": Notification.objects.for_user(account.user).unread().count(),
                "results": [
                    {
                        "id": str(item.id),
                        "type": item.type,
                        "title": item.title,
                        "message": item.message,
                        "is_read": item.is_read,
                        "created_at": item.created_at.isoformat(),
                        "student": item.student.display_name if item.student else None,
                    }
                    for item in queryset[: data["limit"]]
                ],
            }
        )


@extend_schema(
    tags=["bot"],
    request=BotSettingsSerializer,
    responses={200: OpenApiResponse(description="Sozlamalar")},
    summary="Bot sozlamalari",
)
class BotSettingsView(BotServiceView):
    def post(self, request):
        serializer = BotSettingsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        account = self.get_account(serializer.validated_data["telegram_id"])
        account.notifications_enabled = serializer.validated_data["notifications_enabled"]
        account.save(update_fields=["notifications_enabled", "updated_at"])
        return Response({"notifications_enabled": account.notifications_enabled})


@extend_schema(
    tags=["bot"],
    request=BotIdentitySerializer,
    responses={200: OpenApiResponse(description="Uzildi")},
    summary="Telegramni uzish",
)
class BotUnlinkView(BotServiceView):
    def post(self, request):
        serializer = BotIdentitySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        account = self.get_account(serializer.validated_data["telegram_id"])
        unlink_telegram_account(account.user)
        return Response({"unlinked": True})


# --------------------------------------------------------------------------- #
# Signing in by sharing a contact
# --------------------------------------------------------------------------- #
@extend_schema(
    tags=["bot"],
    request=BotContactSerializer,
    responses={200: OpenApiResponse(description="Kod yuborildi")},
    summary="Kontakt orqali kirish: kod so'rash",
)
class BotAuthContactView(BotServiceView):
    """The parent shared their own contact.

    No code is sent here: codes are typed on the website, so this only records
    that the chat owns the number and tells the bot what to say next.
    """

    def post(self, request):
        serializer = BotContactSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        from .services.auth import accept_contact

        return Response(
            accept_contact(telegram_id=data["telegram_id"], phone=data["phone"])
        )


@extend_schema(
    tags=["bot"],
    request=BotAuthVerifySerializer,
    responses={200: OpenApiResponse(description="Kirish muvaffaqiyatli")},
    summary="Kontakt orqali kirish: kodni tasdiqlash",
)
class BotAuthVerifyView(BotServiceView):
    def post(self, request):
        serializer = BotAuthVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        from .services.auth import verify_login_code

        return Response(
            verify_login_code(
                telegram_id=data["telegram_id"],
                code=data["code"],
                phone=data["phone"],
                profile=data.get("profile") or {},
            )
        )


@extend_schema(
    tags=["bot"],
    request=BotContactSerializer,
    responses={200: OpenApiResponse(description="Kod yuborildi")},
    summary="Telefonni o'zgartirish: kod so'rash",
)
class BotPhoneChangeRequestView(BotServiceView):
    def post(self, request):
        serializer = BotContactSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        from .services.auth import request_phone_change

        return Response(
            request_phone_change(telegram_id=data["telegram_id"], phone=data["phone"])
        )


@extend_schema(
    tags=["bot"],
    request=BotAuthVerifySerializer,
    responses={200: OpenApiResponse(description="Telefon yangilandi")},
    summary="Telefonni o'zgartirish: tasdiqlash",
)
class BotPhoneChangeVerifyView(BotServiceView):
    def post(self, request):
        serializer = BotAuthVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        from .services.auth import verify_phone_change

        return Response(
            verify_phone_change(
                telegram_id=data["telegram_id"], code=data["code"], phone=data["phone"]
            )
        )


@extend_schema(
    tags=["bot"],
    request=BotIdentitySerializer,
    responses={200: OpenApiResponse(description="Eslab qolingan raqam")},
    summary="Chat uchun eslab qolingan raqam",
)
class BotKnownPhoneView(BotServiceView):
    """Has this chat already proved a number?

    Lets the bot skip the contact button on a repeat visit instead of asking
    for the same number again.
    """

    def post(self, request):
        serializer = BotIdentitySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        from .services.auth import known_phone

        phone = known_phone(serializer.validated_data["telegram_id"])
        return Response({"phone": phone, "known": bool(phone)})
