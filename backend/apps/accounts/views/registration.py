"""Public, heavily rate-limited registration endpoints.

Nothing here trusts client input beyond what it can prove: the pupil list is
scoped and bounded, the phone number comes from the school registry, and the
OTP is the only thing that turns a claim into an account.
"""
from __future__ import annotations

from django.conf import settings
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.exceptions import NotFoundError
from apps.common.otp import OTPError
from apps.common.throttling import (
    OTPRequestThrottle,
    OTPVerifyThrottle,
    RegistrationThrottle,
    StudentSearchThrottle,
)
from apps.schools.models import ClassGroup
from apps.students.models import Student

from ..serializers import (
    RegistrationCompleteSerializer,
    RegistrationIdentifySerializer,
    RegistrationOTPRequestSerializer,
    RegistrationOTPVerifySerializer,
    RegistrationSessionSerializer,
    StudentSearchResultSerializer,
    StudentSearchSerializer,
)
from ..services import registration as registration_service
from .auth import _token_response


def _otp_error(exc: OTPError, status_code: int = status.HTTP_400_BAD_REQUEST) -> Response:
    return Response(
        {"success": False, "error": {"code": exc.code, "message": str(exc), "fields": {}}},
        status=status_code,
    )


class PublicRegistrationView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []


@extend_schema(tags=["registration"])
class RegistrationRelationsView(PublicRegistrationView):
    throttle_classes = [RegistrationThrottle]

    @extend_schema(
        responses={200: OpenApiResponse(description="Qarindoshlik turlari")},
        summary="Qarindoshlik turlari",
    )
    def get(self, request):
        return Response({"results": registration_service.available_relations()})


@extend_schema(tags=["registration"])
class StudentSearchView(PublicRegistrationView):
    """Search inside one class group only, with a minimum query length and a
    hard result cap — the register can never be dumped through this endpoint."""

    throttle_classes = [StudentSearchThrottle]

    @extend_schema(
        request=StudentSearchSerializer,
        responses={200: StudentSearchResultSerializer(many=True)},
        summary="O'quvchini qidirish",
    )
    def post(self, request):
        serializer = StudentSearchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        class_group = (
            ClassGroup.objects.select_related("grade", "school")
            .filter(pk=serializer.validated_data["class_group"], is_active=True)
            .first()
        )
        if class_group is None:
            raise NotFoundError("Sinf topilmadi.", code="CLASS_GROUP_NOT_FOUND")

        students = registration_service.search_students(
            class_group=class_group,
            query=serializer.validated_data.get("query", ""),
            student_code=serializer.validated_data.get("student_code", ""),
        )
        return Response(
            {
                "count": len(students),
                "results": [registration_service.student_search_payload(s) for s in students],
            }
        )


@extend_schema(tags=["registration"])
class RegistrationIdentifyView(PublicRegistrationView):
    """Verify the applicant against the school registry (JSHSHIR + phone tail)."""

    throttle_classes = [RegistrationThrottle]

    @extend_schema(
        request=RegistrationIdentifySerializer,
        responses={200: RegistrationSessionSerializer},
        summary="Shaxsni tekshirish",
    )
    def post(self, request):
        serializer = RegistrationIdentifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        student = (
            Student.objects.with_class()
            .filter(pk=serializer.validated_data["student"], is_active=True)
            .first()
        )
        if student is None:
            raise NotFoundError("O'quvchi topilmadi.", code="STUDENT_NOT_FOUND")

        session = registration_service.identify_guardian(
            student=student,
            relation=serializer.validated_data["relation"],
            jshshir=serializer.validated_data["jshshir"],
            phone_last4=serializer.validated_data["phone_last4"],
        )
        return Response(registration_service.session_context(session))


@extend_schema(tags=["registration"])
class RegistrationOTPRequestView(PublicRegistrationView):
    """Send the OTP to the number the *school* has on file, not to user input."""

    throttle_classes = [OTPRequestThrottle]

    @extend_schema(
        request=RegistrationOTPRequestSerializer,
        responses={200: OpenApiResponse(description="Kod yuborildi")},
        summary="OTP kod so'rash",
    )
    def post(self, request):
        serializer = RegistrationOTPRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        session = registration_service.load_session(serializer.validated_data["session_token"])
        try:
            result = registration_service.request_registration_otp(session)
        except OTPError as exc:
            return _otp_error(exc, status.HTTP_429_TOO_MANY_REQUESTS)

        context = registration_service.session_context(session)
        return Response(
            {
                # "Sent" only if a provider that actually reaches a phone took
                # it. With SMS unconfigured the wizard would otherwise look
                # fine and then reject every code the parent guesses.
                "sent": result.delivered,
                "delivered": result.delivered,
                "masked_phone": context["masked_phone"],
                "ttl_seconds": result.ttl_seconds,
                "resend_after_seconds": result.resend_after_seconds,
                "debug_code": result.debug_code,
                # The input field sizes itself from this rather than hardcoding.
                "code_length": settings.OTP["LENGTH"],
            }
        )


@extend_schema(tags=["registration"])
class RegistrationOTPVerifyView(PublicRegistrationView):
    throttle_classes = [OTPVerifyThrottle]

    @extend_schema(
        request=RegistrationOTPVerifySerializer,
        responses={200: RegistrationSessionSerializer},
        summary="OTP kodni tasdiqlash",
    )
    def post(self, request):
        serializer = RegistrationOTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        session = registration_service.load_session(serializer.validated_data["session_token"])
        try:
            registration_service.verify_registration_otp(
                session, serializer.validated_data["code"]
            )
        except OTPError as exc:
            return _otp_error(exc)
        return Response(registration_service.session_context(session))


@extend_schema(tags=["registration"])
class RegistrationCompleteView(PublicRegistrationView):
    """Create the account, generate the username and sign the parent straight in."""

    throttle_classes = [RegistrationThrottle]

    @extend_schema(
        request=RegistrationCompleteSerializer,
        responses={201: OpenApiResponse(description="Yaratilgan akkaunt va access token")},
        summary="Akkauntni yaratish",
    )
    def post(self, request):
        serializer = RegistrationCompleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        session = registration_service.load_session(serializer.validated_data["session_token"])
        user, guardian = registration_service.complete_registration(
            session, password=serializer.validated_data["password"], request=request
        )
        response = _token_response(
            user,
            status_code=status.HTTP_201_CREATED,
            extra={
                "username": user.username,
                "detail": (
                    f"Akkaunt yaratildi. Sizning loginingiz: {user.username}. "
                    "Uni keyingi kirishlar uchun saqlab qo'ying."
                ),
            },
        )
        return response
