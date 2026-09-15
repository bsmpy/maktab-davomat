"""Sozlamalar → Integratsiyalar.

Read access is limited to DEVELOPER/SUPER_ADMIN and writes to DEVELOPER, because
everything here is a credential: bot tokens, SMS passwords and turnstile logins.
Every change is audited (with the secrets scrubbed).
"""
from __future__ import annotations

import logging

from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.constants import AuditAction
from apps.audit.services import log_action
from apps.common.exceptions import AppError, ConflictError, NotFoundError
from apps.common.media import absolute_media_url
from apps.common.permissions import CanOpenSettings, CanReadIntegrations, IsDeveloper

from .constants import IntegrationKind, IntegrationStatus
from .models import DailyPresence, Integration, Terminal, TerminalEvent, TerminalPerson
from .serializers import (
    AVAILABLE_KINDS,
    TERMINAL_DIRECTIONS,
    TERMINAL_VENDORS,
    DailyPresenceSerializer,
    EnrollSerializer,
    IntegrationSerializer,
    IntegrationUpdateSerializer,
    RecomputeSerializer,
    SyncEventsSerializer,
    TerminalEventSerializer,
    TerminalPersonSerializer,
    TerminalSerializer,
    TerminalTestSerializer,
    TerminalWriteSerializer,
)
from .services.hikvision import HikvisionClient, HikvisionError
from .services.registry import DEFAULT_CONFIG, integration_config

logger = logging.getLogger(__name__)


class IntegrationTestError(AppError):
    default_code = "INTEGRATION_TEST_FAILED"
    default_detail = "Ulanishni tekshirib bo'lmadi."


# --------------------------------------------------------------------------- #
# Settings overview
# --------------------------------------------------------------------------- #
@extend_schema(
    tags=["settings"],
    responses={200: OpenApiResponse(description="Sozlamalar bo'limlari")},
    summary="Sozlamalar bo'limlari",
)
class SettingsOverviewView(APIView):
    """Which settings sections the signed-in user may open."""

    permission_classes = [CanOpenSettings]

    def get(self, request):
        """The menu, section by section, with a flag per section.

        An ADMIN reaches this page for the two appearance switches and sees the
        integrations section marked unavailable — the credentials in it are the
        platform's, not the school's. The flags are what the sidebar draws; the
        endpoints behind each section refuse the same thing again on their own
        authority.
        """
        from apps.accounts.catalog import Perm

        user = request.user
        return Response(
            {
                "role": user.role,
                "roles": user.role_codes,
                "permissions": user.permission_codes,
                "can_manage_integrations": user.can_manage_integrations,
                "sections": [
                    {
                        "key": "profile",
                        "label": "Profil",
                        "description": "Shaxsiy ma'lumotlar va parol",
                        "available": True,
                    },
                    {
                        "key": "appearance",
                        "label": "Ko'rinish",
                        "description": "Mavzular va zarrachalar",
                        "available": user.has_permission(Perm.SETTINGS_APPEARANCE),
                    },
                    {
                        "key": "integrations",
                        "label": "Integratsiyalar",
                        "description": "Telegram bot, SMS, Face ID va terminallar",
                        "available": user.has_permission(Perm.INTEGRATIONS_VIEW),
                        "children": [
                            {"key": "TELEGRAM_BOT", "label": "Telegram bot"},
                            {"key": "SMS_ESKIZ", "label": "SMS (Eskiz)"},
                            {"key": "FACE_ID", "label": "Face ID"},
                            {"key": "TERMINALS", "label": "Terminallar"},
                        ],
                    },
                ],
            }
        )


# --------------------------------------------------------------------------- #
# Integrations
# --------------------------------------------------------------------------- #
def _ensure_integration(kind: str) -> Integration:
    integration, _created = Integration.objects.get_or_create(
        kind=kind, school=None, defaults={"config": dict(DEFAULT_CONFIG.get(kind, {}))}
    )
    return integration


@extend_schema(tags=["settings"])
class IntegrationListView(APIView):
    permission_classes = [CanReadIntegrations]

    @extend_schema(
        responses={200: IntegrationSerializer(many=True)}, summary="Integratsiyalar ro'yxati"
    )
    def get(self, request):
        # Materialise a row per kind so the UI always has all four cards.
        integrations = [_ensure_integration(kind.value) for kind in IntegrationKind]
        return Response(
            {
                "kinds": AVAILABLE_KINDS,
                "results": IntegrationSerializer(integrations, many=True).data,
            }
        )


@extend_schema(tags=["settings"])
class IntegrationDetailView(APIView):
    permission_classes = [CanReadIntegrations]

    def get_permissions(self):
        if self.request.method in ("PUT", "PATCH"):
            return [IsDeveloper()]
        return super().get_permissions()

    def _get(self, kind: str) -> Integration:
        if kind not in IntegrationKind.values:
            raise NotFoundError("Bunday integratsiya yo'q.", code="UNKNOWN_INTEGRATION")
        return _ensure_integration(kind)

    @extend_schema(responses={200: IntegrationSerializer}, summary="Integratsiya")
    def get(self, request, kind):
        integration = self._get(kind)
        data = IntegrationSerializer(integration).data
        data["effective_config"] = integration_config(kind)
        data["defaults"] = DEFAULT_CONFIG.get(kind, {})
        return Response(data)

    @extend_schema(
        request=IntegrationUpdateSerializer,
        responses={200: IntegrationSerializer},
        summary="Integratsiyani saqlash",
    )
    def put(self, request, kind):
        integration = self._get(kind)
        serializer = IntegrationUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        before = {"is_enabled": integration.is_enabled, "config": dict(integration.config or {})}

        if "is_enabled" in data:
            integration.is_enabled = data["is_enabled"]
        if "config" in data:
            integration.config = {**(integration.config or {}), **data["config"]}
        if "secrets" in data:
            # Blank keeps the stored value; null clears it.
            integration.update_secrets(
                {key: value for key, value in data["secrets"].items() if value != ""}
            )
        integration.updated_by = request.user
        integration.save()

        log_action(
            AuditAction.SENSITIVE_DATA_ACCESS,
            user=request.user,
            entity=integration,
            request=request,
            old_data=before,
            new_data={"is_enabled": integration.is_enabled, "config": integration.config},
            metadata={"operation": "integration_update", "kind": kind},
        )
        return Response(IntegrationSerializer(integration).data)


@extend_schema(tags=["settings"])
class IntegrationTestView(APIView):
    """"Tekshirish" button: proves the stored credentials actually work."""

    permission_classes = [IsDeveloper]

    @extend_schema(request=None, responses={200: OpenApiResponse(description="Tekshiruv natijasi")},
                   summary="Integratsiyani tekshirish")
    def post(self, request, kind):
        if kind not in IntegrationKind.values:
            raise NotFoundError("Bunday integratsiya yo'q.", code="UNKNOWN_INTEGRATION")
        integration = _ensure_integration(kind)

        try:
            details = self._run_check(kind)
        except Exception as exc:  # normalised below — the button must never 500
            message = str(exc) or exc.__class__.__name__
            integration.mark_checked(ok=False, error=message)
            return Response(
                {"ok": False, "status": IntegrationStatus.ERROR, "message": message},
                status=status.HTTP_200_OK,
            )

        integration.mark_checked(ok=True)
        return Response({"ok": True, "status": IntegrationStatus.OK, "details": details})

    def _run_check(self, kind: str) -> dict:
        if kind == IntegrationKind.TELEGRAM_BOT:
            from apps.telegram.services import TelegramClient

            from .services.registry import integration_secret

            token = integration_secret(kind, "bot_token")
            client = TelegramClient(token=token)
            if not client.enabled:
                raise IntegrationTestError("Bot tokeni kiritilmagan.")
            result = client._call("getMe", {})
            return {
                "username": result.get("username"),
                "first_name": result.get("first_name"),
                "id": result.get("id"),
            }

        if kind == IntegrationKind.SMS_ESKIZ:
            from apps.common.sms.eskiz import EskizSMSProvider

            return EskizSMSProvider().check()

        if kind == IntegrationKind.FACE_ID:
            enrolled = TerminalPerson.objects.filter(has_face=True).count()
            total = TerminalPerson.objects.count()
            return {"enrolled_faces": enrolled, "people": total}

        # TERMINALS: report how many devices answer.
        online, offline = 0, []
        for terminal in Terminal.objects.filter(is_active=True):
            try:
                with HikvisionClient.for_terminal(terminal) as client:
                    info = client.device_info()
                terminal.mark_online(firmware=info.firmware, serial=info.serial_number)
                online += 1
            except HikvisionError as error:
                terminal.mark_offline(str(error))
                offline.append({"terminal": terminal.name, "error": str(error)})
        if offline and not online:
            raise IntegrationTestError(offline[0]["error"])
        return {"online": online, "offline": offline}


# --------------------------------------------------------------------------- #
# Terminals
# --------------------------------------------------------------------------- #
@extend_schema(tags=["terminals"])
class TerminalListView(APIView):
    permission_classes = [CanReadIntegrations]

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsDeveloper()]
        return super().get_permissions()

    @extend_schema(responses={200: TerminalSerializer(many=True)}, summary="Terminallar")
    def get(self, request):
        terminals = Terminal.objects.select_related("school").order_by("school", "name")
        school = request.query_params.get("school")
        if school:
            terminals = terminals.filter(school_id=school)
        return Response(
            {
                "directions": TERMINAL_DIRECTIONS,
                "vendors": TERMINAL_VENDORS,
                "results": TerminalSerializer(terminals, many=True).data,
            }
        )

    @extend_schema(
        request=TerminalWriteSerializer,
        responses={201: TerminalSerializer},
        summary="Terminal qo'shish",
    )
    def post(self, request):
        serializer = TerminalWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        terminal = serializer.save()

        log_action(
            AuditAction.SENSITIVE_DATA_ACCESS,
            user=request.user,
            entity=terminal,
            request=request,
            new_data={"name": terminal.name, "host": terminal.host, "port": terminal.port},
            metadata={"operation": "terminal_create"},
        )
        return Response(TerminalSerializer(terminal).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["terminals"])
class TerminalDetailView(APIView):
    permission_classes = [CanReadIntegrations]

    def get_permissions(self):
        if self.request.method in ("PUT", "PATCH", "DELETE"):
            return [IsDeveloper()]
        return super().get_permissions()

    def _get(self, pk) -> Terminal:
        terminal = Terminal.objects.select_related("school").filter(pk=pk).first()
        if terminal is None:
            raise NotFoundError("Terminal topilmadi.", code="TERMINAL_NOT_FOUND")
        return terminal

    @extend_schema(responses={200: TerminalSerializer}, summary="Terminal")
    def get(self, request, pk):
        return Response(TerminalSerializer(self._get(pk)).data)

    @extend_schema(
        request=TerminalWriteSerializer, responses={200: TerminalSerializer},
        summary="Terminalni tahrirlash",
    )
    def patch(self, request, pk):
        terminal = self._get(pk)
        serializer = TerminalWriteSerializer(terminal, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        terminal = serializer.save()

        log_action(
            AuditAction.SENSITIVE_DATA_ACCESS,
            user=request.user,
            entity=terminal,
            request=request,
            metadata={"operation": "terminal_update"},
        )
        return Response(TerminalSerializer(terminal).data)

    @extend_schema(responses={204: None}, summary="Terminalni o'chirish")
    def delete(self, request, pk):
        terminal = self._get(pk)
        terminal.delete()  # soft delete — the event history stays intact
        log_action(
            AuditAction.SENSITIVE_DATA_ACCESS,
            user=request.user,
            entity=terminal,
            request=request,
            metadata={"operation": "terminal_delete"},
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["terminals"])
class TerminalTestView(APIView):
    """Reach out to a device and report what it says."""

    permission_classes = [IsDeveloper]

    @extend_schema(request=None, responses={200: OpenApiResponse(description="Qurilma ma'lumoti")},
                   summary="Terminalni tekshirish")
    def post(self, request, pk):
        terminal = Terminal.objects.filter(pk=pk).first()
        if terminal is None:
            raise NotFoundError("Terminal topilmadi.", code="TERMINAL_NOT_FOUND")
        try:
            with HikvisionClient.for_terminal(terminal) as client:
                info = client.device_info()
                people = client.person_count()
        except HikvisionError as error:
            terminal.mark_offline(str(error))
            return Response({"ok": False, "message": str(error)})

        terminal.mark_online(firmware=info.firmware, serial=info.serial_number)
        return Response(
            {
                "ok": True,
                "device": {
                    "name": info.name,
                    "model": info.model,
                    "serial_number": info.serial_number,
                    "firmware": info.firmware,
                    "mac": info.mac,
                },
                "people_on_device": people,
            }
        )


@extend_schema(tags=["terminals"])
class TerminalAdHocTestView(APIView):
    """Try credentials before creating the terminal record."""

    permission_classes = [IsDeveloper]

    @extend_schema(
        request=TerminalTestSerializer,
        responses={200: OpenApiResponse(description="Qurilma ma'lumoti")},
        summary="Ulanishni tekshirish (saqlamasdan)",
    )
    def post(self, request):
        serializer = TerminalTestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        scheme = "https" if data["use_https"] else "http"
        base_url = f"{scheme}://{data['host']}:{data['port']}"

        try:
            with HikvisionClient(base_url, data["username"], data["password"]) as client:
                info = client.device_info()
        except HikvisionError as error:
            return Response({"ok": False, "message": str(error)})

        return Response(
            {
                "ok": True,
                "device": {
                    "name": info.name,
                    "model": info.model,
                    "serial_number": info.serial_number,
                    "firmware": info.firmware,
                },
            }
        )


@extend_schema(tags=["terminals"])
class TerminalSyncView(APIView):
    """Pull events from a device on demand (also used to backfill a range)."""

    permission_classes = [IsDeveloper]

    @extend_schema(
        request=SyncEventsSerializer,
        responses={200: OpenApiResponse(description="Sinxronizatsiya natijasi")},
        summary="Hodisalarni tortib olish",
    )
    def post(self, request, pk):
        terminal = Terminal.objects.select_related("school").filter(pk=pk).first()
        if terminal is None:
            raise NotFoundError("Terminal topilmadi.", code="TERMINAL_NOT_FOUND")

        serializer = SyncEventsSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        start = serializer.validated_data.get("start")
        end = serializer.validated_data.get("end") or timezone.now()

        from .services.ingest import poll_terminal as run_poll

        result = run_poll(terminal, since=start, until=end)
        return Response(result)


@extend_schema(tags=["terminals"])
class TerminalRotateTokenView(APIView):
    permission_classes = [IsDeveloper]

    @extend_schema(request=None, responses={200: OpenApiResponse(description="Yangi ingest URL")},
                   summary="Ingest tokenni yangilash")
    def post(self, request, pk):
        terminal = Terminal.objects.filter(pk=pk).first()
        if terminal is None:
            raise NotFoundError("Terminal topilmadi.", code="TERMINAL_NOT_FOUND")
        terminal.rotate_ingest_token()
        log_action(
            AuditAction.SENSITIVE_DATA_ACCESS,
            user=request.user,
            entity=terminal,
            request=request,
            metadata={"operation": "terminal_rotate_ingest_token"},
        )
        return Response(TerminalSerializer(terminal).data)


@extend_schema(
    tags=["terminals"],
    parameters=[
        OpenApiParameter("terminal", str, description="Terminal ID"),
        OpenApiParameter("date", str, description="YYYY-MM-DD"),
        OpenApiParameter("student", str, description="O'quvchi ID"),
    ],
    summary="Terminal hodisalari",
)
class TerminalEventListView(ListAPIView):
    serializer_class = TerminalEventSerializer
    permission_classes = [CanReadIntegrations]

    def get_queryset(self):
        queryset = TerminalEvent.objects.select_related(
            "terminal", "student", "student__class_group"
        ).order_by("-occurred_at")
        params = self.request.query_params
        if params.get("terminal"):
            queryset = queryset.filter(terminal_id=params["terminal"])
        if params.get("student"):
            queryset = queryset.filter(student_id=params["student"])
        if params.get("date"):
            queryset = queryset.filter(date=params["date"])
        return queryset


# --------------------------------------------------------------------------- #
# Face ID enrolment
# --------------------------------------------------------------------------- #
@extend_schema(tags=["face-id"], summary="Terminalga yuklangan o'quvchilar")
class TerminalPersonListView(ListAPIView):
    serializer_class = TerminalPersonSerializer
    permission_classes = [CanReadIntegrations]

    def get_queryset(self):
        queryset = TerminalPerson.objects.select_related(
            "student", "student__class_group"
        ).order_by("student__last_name")
        params = self.request.query_params
        if params.get("class_group"):
            queryset = queryset.filter(student__class_group_id=params["class_group"])
        if params.get("school"):
            queryset = queryset.filter(school_id=params["school"])
        return queryset


@extend_schema(tags=["face-id"])
class EnrollView(APIView):
    """Push pupils (and their photos) onto every active terminal."""

    permission_classes = [IsDeveloper]

    @extend_schema(
        request=EnrollSerializer,
        responses={200: OpenApiResponse(description="Yuklash natijasi")},
        summary="O'quvchilarni terminalga yuklash",
    )
    def post(self, request):

        from .services.enrollment import enroll_student

        serializer = EnrollSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        from apps.guardians.selectors import accessible_students

        # Scoped through the same selector as everywhere else, so "all" can
        # never reach past what the caller is allowed to see.
        students = accessible_students(request.user).select_related("school", "class_group")
        if data["class_group"]:
            students = students.filter(class_group_id=data["class_group"])
        elif not data["all"]:
            students = students.filter(id__in=data["students"])

        results, errors = [], []
        for student in students:
            outcome = enroll_student(student)
            results.append(
                {
                    "student": str(student.id),
                    "name": student.display_name,
                    "person_code": outcome["person_code"],
                    "terminals": outcome["terminals"],
                    "faces": outcome["faces"],
                }
            )
            errors.extend(outcome["errors"])

        log_action(
            AuditAction.SENSITIVE_DATA_ACCESS,
            user=request.user,
            request=request,
            metadata={
                "operation": "face_enroll",
                "enrolled": len(results),
                "faces": sum(row["faces"] for row in results),
                "errors": len(errors),
            },
        )
        return Response(
            {
                "enrolled": len(results),
                "faces": sum(row["faces"] for row in results),
                "results": results,
                "errors": errors,
            }
        )


@extend_schema(tags=["face-id"])
class StudentPhotoView(APIView):
    """Upload the photo that gets enrolled into the terminals' face library."""

    permission_classes = [IsDeveloper]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        request={"multipart/form-data": {"type": "object", "properties": {
            "photo": {"type": "string", "format": "binary"}}}},
        responses={200: OpenApiResponse(description="Rasm saqlandi")},
        summary="O'quvchi rasmini yuklash",
    )
    def post(self, request, student_id):
        from apps.students.models import Student

        from .services.enrollment import EnrollmentError, prepare_face_image

        student = Student.objects.filter(pk=student_id).select_related("school").first()
        if student is None:
            raise NotFoundError("O'quvchi topilmadi.", code="STUDENT_NOT_FOUND")

        upload = request.FILES.get("photo")
        if upload is None:
            raise ConflictError("Rasm fayli yuborilmadi.", code="PHOTO_REQUIRED")

        config = integration_config(IntegrationKind.FACE_ID, student.school)
        if upload.size > int(config.get("max_photo_bytes", 2 * 1024 * 1024)):
            raise ConflictError("Rasm hajmi juda katta.", code="PHOTO_TOO_LARGE")

        raw = upload.read()
        try:
            prepare_face_image(raw)  # validates before we store anything
        except EnrollmentError as error:
            raise ConflictError(str(error), code="INVALID_PHOTO") from error

        upload.seek(0)
        student.photo.save(f"{student.id}.jpg", upload, save=True)

        result = None
        if config.get("auto_enroll", True):
            from .services.enrollment import enroll_student

            result = enroll_student(student)

        return Response(
            {"ok": True, "photo": absolute_media_url(student.photo), "enrollment": result}
        )


# --------------------------------------------------------------------------- #
# Presence (prihod / uhod)
# --------------------------------------------------------------------------- #
@extend_schema(
    tags=["terminals"],
    parameters=[
        OpenApiParameter("date", str, description="YYYY-MM-DD"),
        OpenApiParameter("class_group", str, description="Sinf guruhi ID"),
    ],
    summary="Kunlik kirish-chiqish",
)
class DailyPresenceListView(ListAPIView):
    """Every pupil's day at the gate — an integrations tool, not a settings page.

    ``settings.view`` alone used to open it, and an ADMIN holds that for the
    appearance switches; the list is attendance, so it sits with the terminals.
    """

    serializer_class = DailyPresenceSerializer
    permission_classes = [CanReadIntegrations]

    def get_queryset(self):
        from apps.attendance.services.periods import today

        queryset = DailyPresence.objects.select_related(
            "student", "student__class_group"
        ).order_by("student__last_name")
        params = self.request.query_params
        queryset = queryset.filter(date=params.get("date") or today())
        if params.get("class_group"):
            queryset = queryset.filter(student__class_group_id=params["class_group"])
        return queryset


@extend_schema(tags=["terminals"])
class RecomputePresenceView(APIView):
    """Rebuild the day's entry/exit records from the stored events."""

    permission_classes = [IsDeveloper]

    @extend_schema(
        request=RecomputeSerializer,
        responses={200: OpenApiResponse(description="Qayta hisoblash natijasi")},
        summary="Davomatni qayta hisoblash",
    )
    def post(self, request):
        from apps.students.models import Student

        from .services.presence import rebuild_daily_presence

        serializer = RecomputeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        students = Student.objects.active().select_related("school", "class_group")
        if data["class_group"]:
            students = students.filter(class_group_id=data["class_group"])
        elif data["school"]:
            students = students.filter(school_id=data["school"])

        totals = {"students": 0, "rebuilt": 0}
        for student in students.iterator(chunk_size=200):
            presence = rebuild_daily_presence(student, data["date"])
            totals["students"] += 1
            totals["rebuilt"] += 1 if presence is not None else 0

        log_action(
            AuditAction.ATTENDANCE_UPDATE,
            user=request.user,
            request=request,
            metadata={"operation": "recompute_from_terminal", "date": data["date"].isoformat(),
                      **totals},
        )
        return Response({"date": data["date"].isoformat(), **totals})


# --------------------------------------------------------------------------- #
# Device push endpoint (no user auth — the ingest token is the credential)
# --------------------------------------------------------------------------- #
@extend_schema(
    tags=["terminals"],
    request=None,
    responses={200: OpenApiResponse(description="Qabul qilindi")},
    summary="Terminal hodisasini qabul qilish (webhook)",
    auth=[],
)
class TerminalIngestView(APIView):
    """Endpoint the device's HTTP Listening notification posts to.

    Authenticated purely by the long, rotatable token in the URL — Hikvision
    firmware cannot send custom headers reliably. Nothing here trusts the body:
    the token decides which terminal (and therefore which school) the event
    belongs to.
    """

    permission_classes = []
    authentication_classes: list = []
    # Firmware differs: some models post multipart with a JSON part, others a
    # bare JSON body, others urlencoded. Accept all three.
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def post(self, request, ingest_token):
        terminal = (
            Terminal.objects.select_related("school")
            .filter(ingest_token=ingest_token, is_active=True, deleted_at__isnull=True)
            .first()
        )
        if terminal is None:
            # Same answer as a wrong token on any other endpoint: no oracle.
            raise NotFoundError("Terminal topilmadi.", code="TERMINAL_NOT_FOUND")

        payload = self._extract_payload(request)
        if payload is None:
            return Response({"ok": True, "stored": 0, "note": "no parsable payload"})

        from .services.ingest import ingest_events, parse_push_payload

        events = parse_push_payload(payload)
        stored = ingest_events(terminal, events)

        terminal.last_seen_at = timezone.now()
        terminal.status = IntegrationStatus.OK
        terminal.save(update_fields=["last_seen_at", "status", "updated_at"])

        if stored:
            from .tasks import process_terminal_events

            process_terminal_events.delay([str(event.pk) for event in stored])

        return Response({"ok": True, "received": len(events), "stored": len(stored)})

    def _extract_payload(self, request) -> dict | None:
        """Devices post multipart with a JSON part, or a bare JSON body."""
        import json

        for key in ("event_log", "EventNotificationAlert", "data", "json"):
            value = request.data.get(key) if hasattr(request.data, "get") else None
            if isinstance(value, dict):
                return value
            if isinstance(value, str):
                try:
                    return json.loads(value)
                except ValueError:
                    continue

        for uploaded in request.FILES.values():
            try:
                return json.loads(uploaded.read().decode("utf-8", "ignore"))
            except ValueError:
                continue

        if isinstance(request.data, dict) and request.data:
            return dict(request.data)

        body = (request.body or b"").decode("utf-8", "ignore").strip()
        if body:
            try:
                return json.loads(body)
            except ValueError:
                return None
        return None
