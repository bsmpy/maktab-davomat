"""Shared fixtures: a small but complete school, ready to assert against."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta

import pytest
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.constants import Role
from apps.accounts.models import User
from apps.attendance.models import AttendanceReason, Lesson, Schedule
from apps.common import clock as _clock
from apps.guardians.constants import Relation
from apps.guardians.models import Guardian, GuardianStudent
from apps.schools.models import AcademicYear, ClassGroup, Grade, School, Subject, Teacher
from apps.students.models import Student

# The suite runs on the wall clock. A deployment may be on a demo clock
# (CLOCK_OFFSET_SECONDS) and the suite reads that same .env, so the shift is
# undone here — before TODAY below is computed from it.
_clock.uninstall()


def _fixture_day() -> date:
    """A school day, anchored to the real calendar.

    Pinning a literal date makes every report that defaults to "today" start
    failing the moment the wall clock passes it, so the fixture day tracks the
    clock and only steps back off Sunday — the one weekday the school is shut.
    """
    day = timezone.localdate()
    return day - timedelta(days=1) if day.isoweekday() == 7 else day


TODAY = _fixture_day()
PASSWORD = "Test!Parol2026"


@pytest.fixture(autouse=True)
def _real_clock(settings):
    """Always test against the wall clock.

    A deployment may be running on a demo clock (``CLOCK_OFFSET_SECONDS``), and
    the suite reads that same ``.env``. Anything that needs a shifted clock
    installs one itself and puts it back afterwards.
    """
    from apps.common import clock

    settings.CLOCK_OFFSET_SECONDS = 0
    clock.uninstall()
    yield
    clock.uninstall()


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture(autouse=True)
def _dummy_sms(settings):
    from apps.common.sms.providers import DummySMSProvider
    from apps.common.sms.registry import _build

    settings.SMS_PROVIDER = "dummy"
    settings.OTP = {**settings.OTP, "EXPOSE_IN_RESPONSE": True}
    _build.cache_clear()
    DummySMSProvider.clear()
    yield
    DummySMSProvider.clear()
    _build.cache_clear()


@pytest.fixture
def api() -> APIClient:
    return APIClient()


@pytest.fixture
def clock_at(settings):
    """Pin the application clock to a time of day on the fixture day.

    Anything that asserts on "before" or "after" a moment has to control the
    clock. Reading the wall clock instead makes a test pass at noon and fail at
    one in the morning, which is how three of these were written and how all
    three eventually broke.
    """
    from apps.common import clock as _app_clock

    def _at(hour: int, minute: int = 0):
        target = timezone.make_aware(datetime.combine(TODAY, time(hour, minute)))
        settings.CLOCK_OFFSET_SECONDS = _app_clock.offset_for(target)
        _app_clock.uninstall()
        _app_clock.install()
        return target

    yield _at
    _app_clock.uninstall()


@pytest.fixture
def school(db) -> School:
    return School.objects.create(
        name="Test maktabi", short_name="Test", working_weekdays=[1, 2, 3, 4, 5, 6]
    )


@pytest.fixture
def academic_year(school) -> AcademicYear:
    return AcademicYear.objects.create(
        school=school,
        name="2026-2027",
        start_date=TODAY - timedelta(days=200),
        end_date=TODAY + timedelta(days=200),
        is_current=True,
    )


@pytest.fixture
def class_groups(school, academic_year) -> dict[str, ClassGroup]:
    groups = {}
    for level in (1, 3, 7):
        grade = Grade.objects.create(school=school, level=level)
        for name in ("A", "B"):
            group = ClassGroup.objects.create(
                school=school, academic_year=academic_year, grade=grade, name=name
            )
            groups[group.display_name] = group
    return groups


@pytest.fixture
def subject(school) -> Subject:
    return Subject.objects.create(school=school, name="Matematika", short_name="Mat")


@pytest.fixture
def class_subject(school, class_groups) -> Subject:
    """A subject as the console now creates them: bound to one class group."""
    return Subject.objects.create(
        school=school, class_group=class_groups["7-A"], name="Matematika"
    )


@pytest.fixture
def teaching_teacher(school, class_subject) -> Teacher:
    """A teacher who carries exactly one class subject — Matematika 7-A."""
    teacher = Teacher.objects.create(school=school, first_name="Saodaddin", last_name="Rasulov")
    teacher.subjects.add(class_subject)
    return teacher


@pytest.fixture
def teaching_user(teaching_teacher) -> User:
    user = User.objects.create_user(
        username="s.rasulov",
        password=PASSWORD,
        first_name=teaching_teacher.first_name,
        last_name=teaching_teacher.last_name,
        role=Role.TEACHER,
    )
    teaching_teacher.user = user
    teaching_teacher.save(update_fields=["user"])
    return user


@pytest.fixture
def teacher(school, subject) -> Teacher:
    teacher = Teacher.objects.create(school=school, first_name="Nodir", last_name="Ergashev")
    teacher.subjects.add(subject)
    return teacher


@pytest.fixture
def student(school, class_groups) -> Student:
    return Student.objects.create(
        school=school,
        class_group=class_groups["7-A"],
        first_name="Azizbek",
        last_name="Valiyev",
        middle_name="Alisherovich",
        student_code="S1001",
    )


@pytest.fixture
def sibling(school, class_groups) -> Student:
    return Student.objects.create(
        school=school,
        class_group=class_groups["3-B"],
        first_name="Madina",
        last_name="Valiyeva",
        student_code="S1002",
    )


@pytest.fixture
def other_student(school, class_groups) -> Student:
    return Student.objects.create(
        school=school,
        class_group=class_groups["7-B"],
        first_name="Sardor",
        last_name="Karimov",
        student_code="S2001",
    )


def make_guardian(school, *, first_name, last_name, phone, jshshir) -> Guardian:
    guardian = Guardian(
        school=school, first_name=first_name, last_name=last_name, phone=phone
    )
    guardian.set_jshshir(jshshir)
    guardian.save()
    return guardian


@pytest.fixture
def guardian(school) -> Guardian:
    """Registered in the school registry but WITHOUT an account yet."""
    return make_guardian(
        school,
        first_name="Alisher",
        last_name="Valiyev",
        phone="+998901234567",
        jshshir="31234567890123",
    )


@pytest.fixture
def guardian_links(guardian, student, sibling) -> list[GuardianStudent]:
    return [
        GuardianStudent.objects.create(
            guardian=guardian, student=student, relation=Relation.FATHER, is_primary=True
        ),
        GuardianStudent.objects.create(
            guardian=guardian, student=sibling, relation=Relation.FATHER
        ),
    ]


@pytest.fixture
def parent_user(guardian, guardian_links) -> User:
    from django.utils import timezone

    user = User.objects.create_user(
        username="a.valiyev",
        password=PASSWORD,
        first_name=guardian.first_name,
        last_name=guardian.last_name,
        phone=guardian.phone,
        phone_verified_at=timezone.now(),
        role=Role.PARENT,
    )
    guardian.user = user
    guardian.save(update_fields=["user"])
    GuardianStudent.objects.filter(guardian=guardian).update(
        verified=True, verified_at=timezone.now()
    )
    return user


@pytest.fixture
def other_parent(school, other_student) -> User:
    from django.utils import timezone

    guardian = make_guardian(
        school,
        first_name="Dilshod",
        last_name="Karimov",
        phone="+998935558899",
        jshshir="41111222233334",
    )
    GuardianStudent.objects.create(
        guardian=guardian,
        student=other_student,
        relation=Relation.FATHER,
        verified=True,
        verified_at=timezone.now(),
    )
    user = User.objects.create_user(
        username="d.karimov",
        password=PASSWORD,
        first_name=guardian.first_name,
        last_name=guardian.last_name,
        phone=guardian.phone,
        phone_verified_at=timezone.now(),
        role=Role.PARENT,
    )
    guardian.user = user
    guardian.save(update_fields=["user"])
    return user


@pytest.fixture
def teacher_user(teacher) -> User:
    user = User.objects.create_user(
        username="n.ergashev",
        password=PASSWORD,
        first_name=teacher.first_name,
        last_name=teacher.last_name,
        role=Role.TEACHER,
    )
    teacher.user = user
    teacher.save(update_fields=["user"])
    return user


@pytest.fixture
def reason(school) -> AttendanceReason:
    return AttendanceReason.objects.create(school=school, code="KASALLIK", name="Kasallik")


@pytest.fixture
def schedule(academic_year, class_groups, subject, teacher) -> Schedule:
    return Schedule.objects.create(
        academic_year=academic_year,
        class_group=class_groups["7-A"],
        subject=subject,
        teacher=teacher,
        weekday=2,  # Tuesday
        lesson_number=1,
        start_time=time(8, 30),
        end_time=time(9, 15),
    )


@pytest.fixture
def lessons(academic_year, class_groups, subject, teacher) -> list[Lesson]:
    """Six lessons on 2026-09-08 for class 7-A."""
    created = []
    for number in range(1, 7):
        created.append(
            Lesson.objects.create(
                academic_year=academic_year,
                class_group=class_groups["7-A"],
                subject=subject,
                teacher=teacher,
                date=TODAY,
                lesson_number=number,
                start_time=time(8 + number, 0),
                end_time=time(8 + number, 45),
            )
        )
    return created


@pytest.fixture
def terminal(school):
    """An access terminal, with its ISAPI password stored encrypted."""
    from apps.integrations.constants import TerminalDirection
    from apps.integrations.models import Terminal

    device = Terminal(
        school=school,
        name="Asosiy kirish",
        host="192.168.1.64",
        port=80,
        username="admin",
        direction=TerminalDirection.BOTH,
    )
    device.set_secrets({"password": "device-secret"})
    device.save()
    return device


@pytest.fixture
def person(school, student, terminal):
    from apps.integrations.models import TerminalPerson

    return TerminalPerson.objects.create(school=school, student=student, person_code="S1001")


def pass_through(terminal, person_code: str, moment, *, serial: int, direction="IN"):
    """Store one turnstile pass exactly as the ingest path would."""
    from apps.integrations.constants import EventDirection
    from apps.integrations.models import TerminalEvent

    return TerminalEvent.objects.create(
        terminal=terminal,
        external_id=f"sn:{serial}",
        occurred_at=moment,
        direction=EventDirection.IN if direction == "IN" else EventDirection.OUT,
        person_code=person_code,
        student_id=None,
    )


def at(hour: int, minute: int = 0, day: date | None = None):
    """A timezone-aware moment on the fixture day (Asia/Tashkent)."""
    return timezone.make_aware(
        datetime.combine(day or TODAY, time(hour, minute)), timezone.get_current_timezone()
    )


@pytest.fixture
def present_day(student, person, terminal):
    """The pupil arrived 08:24, stepped out 11:00-11:30, left 13:40."""
    from apps.integrations.models import TerminalEvent
    from apps.integrations.services.presence import rebuild_daily_presence

    for serial, (moment, direction) in enumerate(
        [
            (at(8, 24), "IN"),
            (at(11, 0), "OUT"),
            (at(11, 30), "IN"),
            (at(13, 40), "OUT"),
        ],
        start=900,
    ):
        event = pass_through(terminal, "S1001", moment, serial=serial, direction=direction)
        TerminalEvent.objects.filter(pk=event.pk).update(student=student)

    return rebuild_daily_presence(student, TODAY)


@pytest.fixture
def auth_client(api, parent_user) -> APIClient:
    from apps.accounts.services.auth import issue_tokens

    access, _refresh, _ttl = issue_tokens(parent_user)
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return api
