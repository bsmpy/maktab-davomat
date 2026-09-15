"""The teacher's own cabinet: their presence, their profile, their lessons.

Three endpoints, deliberately: the dashboard is one request rather than six,
the profile is one read and one write, and the lesson list is the flat "what am
I teaching today" view the Davomat page opens on.
"""
from __future__ import annotations

from datetime import datetime

from django.db import transaction
from django.db.models import Q
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.accounts.catalog import Perm
from apps.accounts.services.provisioning import validate_chosen_password
from apps.common.exceptions import NotFoundError
from apps.common.media import absolute_media_url
from apps.common.permissions import HasPermission
from apps.schools.models import StaffGender

from .services.lessons import teacher_of, visible_subjects
from .services.periods import today
from .services.teacher_presence import (
    range_summary,
    recent_passes,
    teacher_card,
    teaching_calendar,
    teaching_day,
    timeline,
    week_summary,
)
from .services.timetable import entries_for, marking_opens_at
from .teacher_serializers import TeacherProfileWriteSerializer

DATE_PARAM = OpenApiParameter("date", str, description="YYYY-MM-DD (default: bugun)")


class _SchoolScope:
    """Stands in for a teacher row on the pages an administrator also opens."""

    def __init__(self, school):
        self.school = school
        self.school_id = school.id


class TeacherSelfView(APIView):
    """Base for every endpoint that is about *this person's own day*.

    Not only teachers: a cook, a guard and an accountant walk through the same
    turnstile, and their cabinet asks the same three questions — when did I
    arrive, when did I leave, what did my week look like. So the scope is the
    person's register row, whichever register it lives in, and the permission
    is the one everybody has: ``self.view``.
    """

    permission_classes = [HasPermission]
    read_permission = Perm.STAFF_CABINET

    def get_person(self):
        """The register row behind this account — a teacher or a staff member."""
        person = rbac.person_record(self.request.user)
        if person is None:
            raise NotFoundError(
                "Sizning xodim profilingiz topilmadi.", code="TEACHER_PROFILE_MISSING"
            )
        return person

    #: The old name, kept because every endpoint below reads better with it.
    get_teacher = get_person

    def get_scope(self):
        """Something with a ``school_id``, for the pages an administrator shares.

        A teacher or a staff member is scoped by their own row. An
        administrator who has not been given one is still scoped to a school —
        the calendar needs the school's holidays and working days, not the
        person.
        """
        person = rbac.person_record(self.request.user)
        if person is not None:
            return person

        from apps.schools.services.management import resolve_school

        return _SchoolScope(resolve_school(self.request.user))


def _parse_int(raw: str | None, default: int, *, low: int, high: int) -> int:
    try:
        value = int(raw) if raw not in (None, "") else default
    except (TypeError, ValueError):
        return default
    return min(max(value, low), high)


def _parse_date(raw: str | None):
    if not raw:
        return today()
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        raise NotFoundError("Sana formati noto'g'ri (YYYY-MM-DD).", code="INVALID_DATE") from None


def subject_cards(teacher) -> list[dict]:
    """Every subject the teacher carries, one card per class group.

    A staff member carries none — they have a position instead — so the page
    gets an empty list rather than an error.
    """
    if not hasattr(teacher, "subjects"):
        return []
    subjects = (
        teacher.subjects.filter(deleted_at__isnull=True)
        .select_related("class_group", "class_group__grade")
        .order_by("class_group__grade__level", "class_group__name", "name")
    )
    return [
        {
            "id": str(subject.id),
            "name": subject.name,
            "display_name": subject.display_name,
            "class_group_name": (
                subject.class_group.display_name if subject.class_group_id else ""
            ),
        }
        for subject in subjects
    ]


@extend_schema(tags=["teaching"])
class TeacherDashboardView(TeacherSelfView):
    """Everything the teacher's home screen shows, in one request."""

    @extend_schema(parameters=[DATE_PARAM], summary="O'qituvchi bosh sahifasi")
    def get(self, request):
        from apps.accounts.constants import Role

        from .services.cabinet_home import curator_groups_today, lessons_today

        teacher = self.get_teacher()
        day = _parse_date(request.query_params.get("date"))
        role = request.user.role
        return Response(
            {
                "teacher": teacher_card(teacher),
                "week": week_summary(teacher, day),
                "timeline": timeline(teacher, day),
                "recent_passes": recent_passes(teacher),
                # Only for the hat being worn: a teacher gets the lessons they
                # give today, a curator their groups' day. ``None`` means "not
                # this role's section", an empty list means "nothing today".
                "lessons_today": (
                    lessons_today(teacher, day)
                    if role == Role.TEACHER and hasattr(teacher, "schedules")
                    else None
                ),
                "groups_today": (
                    curator_groups_today(request.user, day) if role == Role.CURATOR else None
                ),
            }
        )


@extend_schema(tags=["teaching"])
class TeacherLessonListView(TeacherSelfView):
    """Today's lessons across every class — what Davomat opens on."""

    @extend_schema(parameters=[DATE_PARAM], summary="Bugungi darslarim")
    def get(self, request):
        # Reaching the cabinet at all still requires a register row, so the
        # lookup stays even though the list below is built from the account.
        self.get_person()
        day = _parse_date(request.query_params.get("date"))
        # "Mine" means the subjects attached to *this teacher*. An employee who
        # does not teach has none, and the page says so rather than failing.
        subjects = visible_subjects(request.user)
        own = teacher_of(request.user)
        mine = (
            {subject.id: subject for subject in subjects.filter(teachers=own)}
            if own is not None
            else {}
        )
        # One pass per class group, not per subject: the timetable of 1-A is the
        # same list however many of its subjects this teacher carries.
        groups = {subject.class_group_id: subject.class_group for subject in mine.values()}

        lessons = []
        for group in groups.values():
            for entry in entries_for(group, day.isoweekday()):
                subject = mine.get(entry.subject_id)
                if subject is None:
                    continue  # somebody else's lesson with this class
                opens = marking_opens_at(subject, day)
                lessons.append(
                    {
                        "subject": str(subject.id),
                        "subject_name": subject.name,
                        "class_group_name": group.display_name,
                        "grade_level": group.grade.level,
                        "lesson_number": entry.lesson_number,
                        "start_time": entry.start_time.strftime("%H:%M"),
                        "end_time": entry.end_time.strftime("%H:%M"),
                        "room": entry.room,
                        "can_mark": opens is None and day <= today(),
                        "opens_at": None if opens is None else entry.start_time.strftime("%H:%M"),
                    }
                )

        # A school with no timetable still has to be able to mark a register.
        if not lessons:
            lessons = [
                {
                    "subject": str(subject.id),
                    "subject_name": subject.name,
                    "class_group_name": subject.class_group.display_name,
                    "grade_level": subject.class_group.grade.level,
                    "lesson_number": index,
                    "start_time": None,
                    "end_time": None,
                    "room": "",
                    "can_mark": day <= today(),
                    "opens_at": None,
                }
                for index, subject in enumerate(mine.values(), start=1)
            ]

        lessons.sort(key=lambda row: (row["start_time"] or "", row["lesson_number"]))
        return Response({"date": day.isoformat(), "results": lessons})


@extend_schema(tags=["teaching"])
class TeacherPresenceStatsView(TeacherSelfView):
    """The employee's own presence, rolled up over three spans at once.

    A week, a month and a year in one request, because the page shows all
    three side by side and three round trips for six numbers each is three
    times the wait for no extra information. Each span is a single query over
    the passes, bucketed by day.

    It is *their own* figures, always: the scope is the register row behind the
    signed-in account, so there is no id to pass and nothing to widen.
    """

    @extend_schema(
        parameters=[DATE_PARAM],
        summary="Mening davomatim: hafta, oy, yil",
    )
    def get(self, request):
        from .services.periods import month_range, week_range

        person = self.get_person()
        day = _parse_date(request.query_params.get("date"))
        config = None

        week = week_range(day)
        month = month_range(day.year, day.month)
        # The school's own year when there is one, the calendar year otherwise:
        # "yillik" means the year the school is in, not the last 365 days.
        year = _academic_span(person, day)

        return Response(
            {
                "date": day.isoformat(),
                "week": range_summary(person, week.start, week.end, config=config),
                "month": range_summary(person, month.start, month.end, config=config),
                "year": range_summary(person, year[0], year[1], config=config),
            }
        )


def _academic_span(person, day):
    """The school year ``day`` falls in, or the calendar year as a fallback."""
    from datetime import date as date_type

    from apps.attendance.selectors import academic_year_for_date

    year = academic_year_for_date(person.school_id, day)
    if year is not None:
        return year.start_date, min(year.end_date, day)
    return date_type(day.year, 1, 1), day


@extend_schema(tags=["teaching"])
class TeacherProfileView(TeacherSelfView):
    """The teacher's own record, and the one place they can edit it."""

    parser_classes = [MultiPartParser, FormParser, *APIView.parser_classes]

    def payload(self, teacher) -> dict:
        user = teacher.user
        # A staff member has a position where a teacher has subjects; both
        # render in the same slot of the same page.
        position = getattr(teacher, "position", None)
        return {
            **teacher_card(teacher),
            "birth_date": teacher.birth_date.isoformat() if teacher.birth_date else None,
            "passport_id": teacher.passport_id,
            "masked_jshshir": teacher.masked_jshshir,
            "jshshir": teacher.jshshir,
            "has_jshshir": bool(teacher.jshshir_last4),
            "gender": teacher.gender,
            "gender_label": teacher.get_gender_display(),
            "phone": teacher.phone,
            "username": user.username if user else "",
            "role": user.role if user else "",
            "roles": user.role_codes if user else [],
            "role_label": user.get_role_display() if user else "",
            "subjects": subject_cards(teacher),
            "position": position.titles if position is not None else None,
            "genders": [
                {"value": value, "label": label} for value, label in StaffGender.choices
            ],
        }

    @extend_schema(summary="Mening profilim")
    def get(self, request):
        return Response(self.payload(self.get_teacher()))

    @extend_schema(request=TeacherProfileWriteSerializer, summary="Profilni saqlash")
    def patch(self, request):
        teacher = self.get_teacher()
        serializer = TeacherProfileWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        photo = data.pop("photo", None)
        password = data.pop("password", "")
        data.pop("password_confirm", None)
        jshshir = data.pop("jshshir", None)

        with transaction.atomic():
            if jshshir is not None and jshshir != "":
                teacher.set_jshshir(jshshir)
            for field, value in data.items():
                setattr(teacher, field, value)
            if photo is not None:
                teacher.photo = photo
            teacher.save()

            if password:
                user = teacher.user
                if user is None:
                    raise NotFoundError(
                        "Sizda kabinet akkaunti yo'q.", code="ACCOUNT_MISSING"
                    )
                validate_chosen_password(password, user=user)
                user.set_password(password)
                user.must_change_password = False
                user.save(update_fields=["password", "must_change_password"])

        return Response(self.payload(teacher))


@extend_schema(tags=["teaching"])
class TeacherPhotoView(TeacherSelfView):
    """The photo shown in the navbar and at the top of the profile."""

    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(summary="Rasmni yuklash")
    def post(self, request):
        teacher = self.get_teacher()
        photo = request.FILES.get("photo")
        if photo is None:
            raise NotFoundError("Rasm yuborilmadi.", code="PHOTO_MISSING")
        teacher.photo = photo
        teacher.save(update_fields=["photo"])
        return Response({"photo": absolute_media_url(teacher.photo)})


@extend_schema(tags=["teaching"])
class TeacherCalendarView(TeacherSelfView):
    """A month at a glance: which days this teacher stands in front of a class.

    For an observing role it is the whole school's lessons and how many were
    marked, which is attendance — so it asks for ``attendance.view``.
    """

    read_permission = Perm.ATTENDANCE_VIEW

    @extend_schema(
        parameters=[
            OpenApiParameter("year", int, description="Masalan 2026"),
            OpenApiParameter("month", int, description="1-12"),
        ],
        summary="O'qituvchi kalendari",
    )
    def get(self, request):
        teacher = self.get_scope()
        now = today()
        year = _parse_int(request.query_params.get("year"), now.year, low=2000, high=2100)
        month = _parse_int(request.query_params.get("month"), now.month, low=1, high=12)
        return Response(teaching_calendar(request.user, teacher, year, month))


@extend_schema(tags=["teaching"])
class TeacherCalendarDayView(TeacherSelfView):
    """One day of the calendar: the classes taught, and their lessons."""

    read_permission = Perm.ATTENDANCE_VIEW

    @extend_schema(summary="Kalendar kuni")
    def get(self, request, day):
        teacher = self.get_scope()
        return Response(teaching_day(request.user, teacher, _parse_date(day)))


# --------------------------------------------------------------------------- #
# Search
# --------------------------------------------------------------------------- #
def _teacher_school_ids(user) -> list:
    """The schools this user may read, never "all of them" by accident.

    ``accessible_schools`` falls back to the whole queryset for an account with
    no register row — sensible while an administrator is being set up, wrong
    for a teacher or a curator, who would then see other schools' registers.
    """
    from apps.accounts.constants import Role
    from apps.schools.services.management import accessible_schools

    if user.role in Role.unrestricted_roles():
        return list(accessible_schools(user).values_list("id", flat=True))

    person = rbac.person_record(user)
    if person is not None:
        return [person.school_id]

    # An administrator is normally scoped by their register row too, but one
    # that has not been created yet must not lock them out.
    if user.role in Role.admin_roles():
        return list(accessible_schools(user).values_list("id", flat=True))

    raise NotFoundError(
        "Sizning xodim profilingiz topilmadi.", code="TEACHER_PROFILE_MISSING"
    )


#: Two letters is the shortest term worth a query; one matches half the register.
MIN_SEARCH = 2
#: Per section, so one crowded kind cannot bury the others.
SEARCH_LIMIT = 6


@extend_schema(tags=["teaching"])
class TeachingSearchView(TeacherSelfView):
    """One search across everything this user is allowed to see.

    Pupils are the sensitive half: a teacher searches only the classes they
    actually teach, a curator only their groups, while an administrator
    searches the whole school. Nothing here returns a record the caller could
    not already open by navigating — which is also why an account with no
    register scope at all (an ordinary STAFF login) cannot reach it.
    """

    read_permission = Perm.STUDENTS_VIEW

    @extend_schema(
        parameters=[OpenApiParameter("q", str, description="Kamida 2 ta belgi")],
        summary="Qidiruv",
    )
    def get(self, request):
        from apps.accounts.constants import Role
        from apps.schools.models import ClassGroup, Subject, Teacher
        from apps.students.models import Student

        term = (request.query_params.get("q") or "").strip()
        if len(term) < MIN_SEARCH:
            return Response({"query": term, "results": []})

        school_ids = _teacher_school_ids(request.user)
        wide = request.user.role in Role.admin_roles()
        # A teacher's pupil search is limited to the classes they stand in front
        # of; an administrator's is the whole school.
        pupil_groups = (
            ClassGroup.objects.filter(school_id__in=school_ids)
            if wide
            else ClassGroup.objects.filter(
                id__in=visible_subjects(request.user).values_list("class_group_id", flat=True)
            )
        )

        results = []

        for group in (
            ClassGroup.objects.filter(school_id__in=school_ids, is_active=True)
            .select_related("grade")
            .order_by("grade__level", "name")
        ):
            # "1-A" is short enough that a substring match on the whole label is
            # what a person expects; searching the letter alone is not useful.
            if term.lower() in group.display_name.lower():
                results.append(
                    {
                        "kind": "class",
                        "id": str(group.id),
                        "title": group.display_name,
                        "subtitle": f"{group.grade.level}-sinf",
                    }
                )
            if len(results) >= SEARCH_LIMIT:
                break

        subjects = (
            Subject.objects.filter(school_id__in=school_ids, is_active=True, name__icontains=term)
            .select_related("class_group", "class_group__grade")
            .order_by("class_group__grade__level", "class_group__name", "name")[:SEARCH_LIMIT]
        )
        mine = set(visible_subjects(request.user).values_list("id", flat=True))
        results += [
            {
                "kind": "subject",
                "id": str(subject.id),
                "title": subject.name,
                "subtitle": (
                    subject.class_group.display_name if subject.class_group_id else ""
                ),
                "is_mine": subject.id in mine,
            }
            for subject in subjects
        ]

        students = (
            Student.objects.active()
            .filter(class_group__in=pupil_groups)
            .filter(
                Q(first_name__icontains=term)
                | Q(last_name__icontains=term)
                | Q(student_code__icontains=term)
            )
            .select_related("class_group", "class_group__grade")
            .order_by("last_name", "first_name")[:SEARCH_LIMIT]
        )
        results += [
            {
                "kind": "student",
                "id": str(student.id),
                "title": student.full_name,
                "subtitle": student.class_group.display_name,
            }
            for student in students
        ]

        teachers = (
            Teacher.objects.filter(school_id__in=school_ids, is_active=True)
            .filter(Q(first_name__icontains=term) | Q(last_name__icontains=term))
            .prefetch_related("subjects")
            .order_by("last_name", "first_name")[:SEARCH_LIMIT]
        )
        results += [
            {
                "kind": "teacher",
                "id": str(row.id),
                "title": row.full_name,
                "subtitle": ", ".join(
                    subject.name for subject in row.subjects.all()[:3]
                ),
            }
            for row in teachers
        ]

        return Response({"query": term, "results": results})
