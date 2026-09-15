"""Parent-facing presence API.

Attendance is entry and exit at the school gate: how many times a pupil walked
in, how many times out, when the first entry and last exit were, and how long
they spent inside and outside. Every report is produced by
:mod:`apps.attendance.services.presence_reports` — the views only parse query
parameters and enforce access.
"""
from __future__ import annotations

from datetime import date, datetime

from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.catalog import Perm
from apps.common.exceptions import ConflictError, NotFoundError, PermissionError_, error_response
from apps.common.permissions import IsAuthenticatedActive, IsTeacher

from .constants import AbsenceRequestStatus
from .models import AbsenceRequest, AttendanceReason
from .permissions import StudentScopedMixin
from .selectors import absence_requests_for
from .serializers import (
    AbsenceRequestCreateSerializer,
    AbsenceRequestReviewSerializer,
    AbsenceRequestSerializer,
    AttendanceReasonSerializer,
    LessonMarksWriteSerializer,
    TeachingSubjectSerializer,
)
from .services.absence import (
    approve_absence_request,
    reject_absence_request,
    submit_absence_request,
)
from .services.lesson_reports import build_lesson_attendance
from .services.lessons import (
    class_cards,
    class_day,
    get_class_group_for,
    get_subject_for,
    roster,
    save_marks,
    subject_cards,
)
from .services.periods import today
from .services.presence_reports import (
    build_daily_presence,
    build_monthly_presence,
    build_presence_calendar,
    build_weekly_presence,
    build_yearly_presence,
)
from .services.timetable import assert_marking_open

DATE_PARAM = OpenApiParameter("date", str, description="YYYY-MM-DD (default: bugun)")


def _parse_date(raw: str | None, default: date | None = None) -> date:
    if not raw:
        return default or today()
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        raise NotFoundError("Sana formati noto'g'ri (YYYY-MM-DD).", code="INVALID_DATE") from None


def _parse_int(raw: str | None, default: int, *, low: int, high: int) -> int:
    if raw in (None, ""):
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise NotFoundError("Noto'g'ri parametr.", code="INVALID_PARAM") from None
    if not low <= value <= high:
        raise NotFoundError("Parametr chegaradan tashqarida.", code="INVALID_PARAM")
    return value


# --------------------------------------------------------------------------- #
# Presence reports
# --------------------------------------------------------------------------- #
@extend_schema(
    tags=["presence"],
    parameters=[DATE_PARAM],
    responses={200: OpenApiResponse(description="Kunlik kirish-chiqish va yakuniy statistika")},
    summary="Kunlik davomat (kirish-chiqish)",
)
class DailyPresenceView(StudentScopedMixin, APIView):
    def get(self, request, student_id):
        student = self.get_student()
        day = _parse_date(request.query_params.get("date"))
        return Response(build_daily_presence(student, day))


@extend_schema(
    tags=["presence"],
    parameters=[DATE_PARAM],
    responses={200: OpenApiResponse(description="Hafta kunlari kesimida kirish-chiqish")},
    summary="Haftalik davomat",
)
class WeeklyPresenceView(StudentScopedMixin, APIView):
    def get(self, request, student_id):
        student = self.get_student()
        anchor = _parse_date(request.query_params.get("date"))
        return Response(build_weekly_presence(student, anchor))


@extend_schema(
    tags=["presence"],
    parameters=[
        OpenApiParameter("year", int, description="Masalan 2026"),
        OpenApiParameter("month", int, description="1-12"),
    ],
    responses={200: OpenApiResponse(description="Kalendar to'ri va oylik statistika")},
    summary="Oylik davomat (kalendar)",
)
class MonthlyPresenceView(StudentScopedMixin, APIView):
    def get(self, request, student_id):
        student = self.get_student()
        reference = today()
        year = _parse_int(request.query_params.get("year"), reference.year, low=2000, high=2100)
        month = _parse_int(request.query_params.get("month"), reference.month, low=1, high=12)
        return Response(build_monthly_presence(student, year, month))


@extend_schema(
    tags=["presence"],
    parameters=[OpenApiParameter("year", int, description="Kalendar yili (ixtiyoriy)")],
    responses={200: OpenApiResponse(description="Oylar kesimida yillik statistika")},
    summary="Yillik davomat",
)
class YearlyPresenceView(StudentScopedMixin, APIView):
    def get(self, request, student_id):
        student = self.get_student()
        year = request.query_params.get("year")
        year = _parse_int(year, today().year, low=2000, high=2100) if year else None
        return Response(build_yearly_presence(student, year=year))


@extend_schema(
    tags=["presence"],
    responses={200: OpenApiResponse(description="Oylik kalendar")},
    summary="Kalendar",
)
class CalendarView(StudentScopedMixin, APIView):
    def get(self, request, student_id):
        student = self.get_student()
        reference = today()
        year = _parse_int(request.query_params.get("year"), reference.year, low=2000, high=2100)
        month = _parse_int(request.query_params.get("month"), reference.month, low=1, high=12)
        return Response(build_presence_calendar(student, year, month))


# --------------------------------------------------------------------------- #
# Absence reasons
# --------------------------------------------------------------------------- #
@extend_schema(tags=["attendance"], summary="Sabab turlari")
class AttendanceReasonListView(ListAPIView):
    serializer_class = AttendanceReasonSerializer
    permission_classes = [IsAuthenticatedActive]
    pagination_class = None

    def get_queryset(self):
        return AttendanceReason.objects.filter(is_active=True).order_by("order", "name")


@extend_schema(tags=["attendance"])
class StudentAbsenceRequestView(StudentScopedMixin, APIView):
    """List a pupil's reason submissions and create a new one."""

    @extend_schema(responses={200: AbsenceRequestSerializer(many=True)}, summary="Sabab arizalari ro'yxati")
    def get(self, request, student_id):
        student = self.get_student()
        reference = today()
        start = date(reference.year - 1, reference.month, 1)
        requests = absence_requests_for(student, start, date(reference.year + 1, 12, 31))
        return Response({"results": AbsenceRequestSerializer(requests, many=True).data})

    @extend_schema(
        request=AbsenceRequestCreateSerializer,
        responses={201: AbsenceRequestSerializer},
        summary="Sabab bildirish",
    )
    def post(self, request, student_id):
        student = self.get_student()
        serializer = AbsenceRequestCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        reason = AttendanceReason.objects.filter(pk=data["reason"], is_active=True).first()
        if reason is None:
            raise NotFoundError("Sabab turi topilmadi.", code="REASON_NOT_FOUND")

        absence_request = submit_absence_request(
            student=student,
            day=data["date"],
            reason=reason,
            comment=data["comment"],
            submitted_by=request.user,
        )
        return Response(
            AbsenceRequestSerializer(absence_request).data, status=status.HTTP_201_CREATED
        )


@extend_schema(tags=["attendance"])
class AbsenceRequestReviewView(APIView):
    """Teacher/admin approval workflow for a parent's explanation of a day.

    Deciding a request is a write, so it asks for ``absence.review`` — which a
    MODERATOR does not hold and a CURATOR does not either: watching a class is
    not the same as ruling on why a pupil missed a day.
    """

    permission_classes = [IsTeacher]
    read_permission = Perm.ABSENCE_REVIEW
    write_permission = Perm.ABSENCE_REVIEW

    def _get_request(self, request, pk) -> AbsenceRequest:
        from apps.guardians.selectors import accessible_students

        absence_request = (
            AbsenceRequest.objects.select_related("student", "reason").filter(pk=pk).first()
        )
        if absence_request is None:
            raise NotFoundError("Ariza topilmadi.", code="ABSENCE_REQUEST_NOT_FOUND")
        if not accessible_students(request.user).filter(pk=absence_request.student_id).exists():
            raise PermissionError_()
        return absence_request

    @extend_schema(
        request=AbsenceRequestReviewSerializer,
        responses={200: AbsenceRequestSerializer},
        summary="Sababni tasdiqlash / rad etish",
    )
    def post(self, request, pk, action):
        serializer = AbsenceRequestReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        absence_request = self._get_request(request, pk)

        if action == "approve":
            approve_absence_request(
                absence_request, reviewer=request.user, comment=serializer.validated_data["comment"]
            )
        elif action == "reject":
            reject_absence_request(
                absence_request, reviewer=request.user, comment=serializer.validated_data["comment"]
            )
        else:
            return error_response("INVALID_ACTION", "Noma'lum amal.", status_code=400)
        return Response(AbsenceRequestSerializer(absence_request).data)


@extend_schema(tags=["attendance"], summary="Ko'rib chiqilishi kutilayotgan arizalar")
class PendingAbsenceRequestListView(ListAPIView):
    serializer_class = AbsenceRequestSerializer
    permission_classes = [IsTeacher]
    read_permission = Perm.ABSENCE_REVIEW

    def get_queryset(self):
        from apps.guardians.selectors import accessible_students

        return (
            AbsenceRequest.objects.filter(
                status=AbsenceRequestStatus.PENDING,
                student__in=accessible_students(self.request.user).values("id"),
            )
            .select_related("student", "reason", "submitted_by")
            .order_by("-date")
        )


# --------------------------------------------------------------------------- #
# Dars davomati — the register a teacher fills in
# --------------------------------------------------------------------------- #
@extend_schema(tags=["teaching"])
class TeachingSubjectListView(APIView):
    """The subject cards this user may mark: Rasulov sees only Matematika 1-A."""

    permission_classes = [IsTeacher]

    @extend_schema(
        parameters=[DATE_PARAM],
        responses={200: TeachingSubjectSerializer(many=True)},
        summary="Fan kartochkalari",
    )
    def get(self, request):
        day = _parse_date(request.query_params.get("date"))
        return Response({"date": day.isoformat(), "results": subject_cards(request.user, day)})


@extend_schema(tags=["teaching"])
class TeachingRosterView(APIView):
    """One subject on one day: the pupils and their marks.

    Readable by anyone who may read attendance for that subject — a curator
    reads their groups' registers — and writable only with ``attendance.mark``,
    which is what makes the same URL a report for one role and a form for
    another.
    """

    permission_classes = [IsTeacher]
    read_permission = Perm.ATTENDANCE_VIEW
    write_permission = Perm.ATTENDANCE_MARK

    @extend_schema(parameters=[DATE_PARAM], summary="Sinf ro'yxati va davomat")
    def get(self, request, subject_id):
        subject = get_subject_for(request.user, subject_id)
        day = _parse_date(request.query_params.get("date"))
        # The roll call does not open before the lesson does — not even to
        # look at. Until the bell there is nothing to record, and a teacher
        # who could open the list early could fill it in from memory.
        if day > today():
            raise ConflictError(
                "Kelajak kun uchun davomat ochilmaydi.", code="FUTURE_DATE"
            )
        assert_marking_open(subject, day)
        return Response(roster(subject, day))

    @extend_schema(
        request=LessonMarksWriteSerializer,
        responses={200: OpenApiResponse(description="Saqlandi")},
        summary="Davomatni saqlash",
    )
    def post(self, request, subject_id):
        subject = get_subject_for(request.user, subject_id)
        serializer = LessonMarksWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        return Response(
            save_marks(subject, data["date"], data["marks"], user=request.user)
        )


@extend_schema(tags=["attendance"])
class ChildLessonAttendanceView(StudentScopedMixin, APIView):
    """The same register, read from the parent's side."""

    @extend_schema(
        parameters=[
            OpenApiParameter("start", str, description="YYYY-MM-DD (default: bugun)"),
            OpenApiParameter("end", str, description="YYYY-MM-DD (default: start)"),
            OpenApiParameter(
                "include_days",
                bool,
                description="Kunlar ro'yxatini qaytarish (yillik ko'rinish uchun false)",
            ),
        ],
        summary="Dars davomati",
    )
    def get(self, request, student_id):
        start = _parse_date(request.query_params.get("start"))
        end = _parse_date(request.query_params.get("end"), default=start)
        if end < start:
            start, end = end, start
        include_days = request.query_params.get("include_days", "true").lower() != "false"
        return Response(
            build_lesson_attendance(
                self.get_student(), start, end, include_days=include_days
            )
        )


@extend_schema(tags=["teaching"])
class TeachingClassListView(APIView):
    """The classes this user teaches, with the today / tomorrow marker."""

    permission_classes = [IsTeacher]

    @extend_schema(parameters=[DATE_PARAM], summary="Sinf kartochkalari")
    def get(self, request):
        day = _parse_date(request.query_params.get("date"))
        return Response({"date": day.isoformat(), "results": class_cards(request.user, day)})


@extend_schema(tags=["teaching"])
class TeachingClassDayView(APIView):
    """One class on one day: its timetable and how much is already marked."""

    permission_classes = [IsTeacher]

    @extend_schema(parameters=[DATE_PARAM], summary="Sinfning kunlik darslari")
    def get(self, request, class_group_id):
        group = get_class_group_for(request.user, class_group_id)
        day = _parse_date(request.query_params.get("date"))
        return Response(class_day(request.user, group, day))
