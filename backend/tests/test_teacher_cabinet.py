"""The teacher's own cabinet: presence at the gate, profile, today's lessons.

Staff walk through the same turnstile as the pupils. Their passes are found by
the code recorded on their row, paired into visits by the same engine, and read
back as a day timeline and a week of totals.
"""
from __future__ import annotations

from datetime import timedelta

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.services.auth import issue_tokens
from apps.integrations.constants import EventDirection
from apps.integrations.models import TerminalEvent
from tests.conftest import PASSWORD, TODAY, at

pytestmark = pytest.mark.django_db

DEVICE_CODE = "T-1001"


def as_user(user):
    client = APIClient()
    access, _refresh, _ttl = issue_tokens(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return client


@pytest.fixture
def gate_teacher(teaching_teacher, teaching_user):
    """A teacher the turnstile knows, with a name that has all three parts."""
    from apps.integrations.models import TerminalPerson

    teaching_teacher.first_name = "Samir"
    teaching_teacher.last_name = "Hasanov"
    teaching_teacher.middle_name = "Xayrilloyevich"
    teaching_teacher.email = "samir@maktab.uz"
    teaching_teacher.save()
    TerminalPerson.objects.create(
        school=teaching_teacher.school, teacher=teaching_teacher, person_code=DEVICE_CODE
    )
    return teaching_teacher


@pytest.fixture
def client(teaching_user):
    return as_user(teaching_user)


def walk(terminal, teacher, hour, minute, *, direction, serial, day=None):
    """One pass, attributed to the teacher the way the ingest path would."""
    event = TerminalEvent.objects.create(
        terminal=terminal,
        external_id=f"t:{serial}",
        occurred_at=at(hour, minute, day),
        direction=EventDirection.IN if direction == "IN" else EventDirection.OUT,
        person_code=DEVICE_CODE,
        teacher=teacher,
    )
    return event


# --------------------------------------------------------------------------- #
# The turnstile knows staff too
# --------------------------------------------------------------------------- #
def test_a_pass_is_attributed_to_the_person_who_owns_the_code(terminal, gate_teacher):
    from apps.integrations.services.ingest import _resolve_person

    # (student, teacher, staff) — three registers walk through the same gate.
    assert _resolve_person(terminal, DEVICE_CODE) == (None, gate_teacher, None)
    assert _resolve_person(terminal, "nobody") == (None, None, None)


def test_a_pupil_and_a_teacher_cannot_share_a_code(terminal, gate_teacher, student):
    """One enrolment row per code, so a pass has exactly one owner."""
    from apps.integrations.services.enrollment import ensure_person_code
    from apps.integrations.services.ingest import _resolve_person

    person = ensure_person_code(student)
    resolved_student, resolved_teacher, _resolved_staff = _resolve_person(
        terminal, person.person_code
    )
    assert (resolved_student, resolved_teacher) == (student, None)


# --------------------------------------------------------------------------- #
# The day timeline
# --------------------------------------------------------------------------- #
def test_the_timeline_paints_every_visit_not_just_the_first_and_last(
    client, terminal, gate_teacher
):
    """In, out, in, out — two green blocks with a gap, not one long one."""
    walk(terminal, gate_teacher, 8, 0, direction="IN", serial=1)
    walk(terminal, gate_teacher, 12, 0, direction="OUT", serial=2)
    walk(terminal, gate_teacher, 13, 0, direction="IN", serial=3)
    walk(terminal, gate_teacher, 17, 0, direction="OUT", serial=4)

    response = client.get(reverse("teaching:teacher-dashboard"))
    assert response.status_code == 200
    segments = response.data["timeline"]["segments"]

    assert [(row["state"], row["start"], row["end"]) for row in segments] == [
        ("OUT", "06:00", "08:00"),
        ("IN", "08:00", "12:00"),
        ("OUT", "12:00", "13:00"),
        ("IN", "13:00", "17:00"),
        ("OUT", "17:00", "00:00"),
    ]
    # The band is 06:00–24:00, so the widths add up to the whole of it.
    assert round(sum(row["width"] for row in segments)) == 100


def test_the_timeline_reports_the_first_entry_and_last_exit(
    client, terminal, gate_teacher
):
    walk(terminal, gate_teacher, 8, 12, direction="IN", serial=1)
    walk(terminal, gate_teacher, 13, 40, direction="OUT", serial=2)
    walk(terminal, gate_teacher, 14, 20, direction="IN", serial=3)
    walk(terminal, gate_teacher, 17, 55, direction="OUT", serial=4)

    data = client.get(reverse("teaching:teacher-dashboard")).data["timeline"]
    assert data["first_in"] == "08:12"
    assert data["last_out"] == "17:55"
    assert data["is_inside"] is False


def test_a_teacher_still_inside_has_no_last_exit_yet(
    client, terminal, gate_teacher, clock_at
):
    clock_at(11, 30)
    walk(terminal, gate_teacher, 8, 0, direction="IN", serial=1)

    data = client.get(reverse("teaching:teacher-dashboard")).data["timeline"]
    assert data["is_inside"] is True
    assert data["first_in"] == "08:00"
    assert data["last_out"] is None
    # The green block runs to now, not to the end of the band.
    green = [row for row in data["segments"] if row["state"] == "IN"]
    assert len(green) == 1
    assert green[0]["start"] == "08:00"


def test_a_day_with_no_passes_is_all_red(client, gate_teacher):
    data = client.get(reverse("teaching:teacher-dashboard")).data["timeline"]
    assert [(row["state"], row["start"], row["end"]) for row in data["segments"]] == [
        ("OUT", "06:00", "00:00")
    ]
    assert data["first_in"] is None
    assert data["last_out"] is None


# --------------------------------------------------------------------------- #
# The week
# --------------------------------------------------------------------------- #
def test_the_week_counts_time_in_time_out_and_late_starts(
    client, terminal, gate_teacher, school
):
    """Two hours inside on a day whose working span is 08:10–14:00."""
    walk(terminal, gate_teacher, 9, 0, direction="IN", serial=1)
    walk(terminal, gate_teacher, 11, 0, direction="OUT", serial=2)

    week = client.get(reverse("teaching:teacher-dashboard")).data["week"]
    assert week["active_minutes"] == 120
    # 08:10 → 14:00 is 350 working minutes a day. Every elapsed school day of
    # the week counts, and a day nobody turned up is inactive end to end.
    assert week["inactive_minutes"] == week["school_days"] * 350 - 120
    # First entry at 09:00, well past the 08:10 start.
    assert week["late_days"] == 1


def test_arriving_before_the_start_is_not_a_late_day(client, terminal, gate_teacher):
    walk(terminal, gate_teacher, 8, 0, direction="IN", serial=1)
    walk(terminal, gate_teacher, 14, 0, direction="OUT", serial=2)

    week = client.get(reverse("teaching:teacher-dashboard")).data["week"]
    assert week["late_days"] == 0
    assert week["active_minutes"] == 360


def test_the_week_ignores_days_that_have_not_happened(client, gate_teacher):
    week = client.get(reverse("teaching:teacher-dashboard")).data["week"]
    # Only the days up to and including today can count.
    assert week["school_days"] >= 1
    assert week["active_minutes"] == 0


# --------------------------------------------------------------------------- #
# The pass log
# --------------------------------------------------------------------------- #
def test_the_pass_log_shows_the_last_six_newest_first(client, terminal, gate_teacher):
    for index in range(8):
        walk(
            terminal,
            gate_teacher,
            8 + index,
            0,
            direction="IN" if index % 2 == 0 else "OUT",
            serial=index,
        )

    passes = client.get(reverse("teaching:teacher-dashboard")).data["recent_passes"]
    assert len(passes) == 6
    assert passes[0]["time"] == "15:00"
    assert passes[0]["label"] == "Chiqdi"
    assert passes[1]["label"] == "Kirdi"


def test_the_pass_log_is_empty_when_the_gate_has_nothing(client, gate_teacher):
    assert client.get(reverse("teaching:teacher-dashboard")).data["recent_passes"] == []


# --------------------------------------------------------------------------- #
# Identity
# --------------------------------------------------------------------------- #
def test_the_cabinet_names_the_teacher_in_full(client, gate_teacher):
    """One name everywhere: the navbar shows what the profile shows."""
    card = client.get(reverse("teaching:teacher-dashboard")).data["teacher"]
    assert card["full_name"] == "Hasanov Samir Xayrilloyevich"
    assert card["school"]["name"] == "Test maktabi"
    assert "short_name" not in card


def test_a_teacher_with_no_patronymic_is_named_without_a_trailing_space(
    client, gate_teacher
):
    gate_teacher.middle_name = ""
    gate_teacher.save(update_fields=["middle_name"])
    card = client.get(reverse("teaching:teacher-dashboard")).data["teacher"]
    assert card["full_name"] == "Hasanov Samir"


# --------------------------------------------------------------------------- #
# The profile
# --------------------------------------------------------------------------- #
def test_the_profile_returns_the_teachers_own_record(client, gate_teacher, class_subject):
    response = client.get(reverse("teaching:teacher-profile"))
    assert response.status_code == 200
    assert response.data["first_name"] == "Samir"
    assert response.data["username"] == "s.rasulov"
    assert response.data["email"] == "samir@maktab.uz"
    # One card per subject, carrying its class group.
    assert [(row["name"], row["class_group_name"]) for row in response.data["subjects"]] == [
        ("Matematika", "7-A")
    ]


def test_a_teacher_can_edit_their_own_details(client, gate_teacher):
    response = client.patch(
        reverse("teaching:teacher-profile"),
        {
            "first_name": "Samirbek",
            "birth_date": "1990-03-04",
            "passport_id": "aa1234567",
            "gender": "MALE",
            "phone": "+998(90)123-45-67",
            "email": "yangi@maktab.uz",
        },
        format="json",
    )
    assert response.status_code == 200
    assert response.data["first_name"] == "Samirbek"
    assert response.data["passport_id"] == "AA1234567"
    assert response.data["phone"] == "+998901234567"
    assert response.data["gender_label"] == "Erkak"

    gate_teacher.refresh_from_db()
    assert gate_teacher.birth_date.isoformat() == "1990-03-04"


def test_the_profile_shows_the_teachers_own_jshshir_in_full(client, gate_teacher):
    """Shown to its owner and to the register's administrators, as asked."""
    gate_teacher.set_jshshir("31234567890123")
    gate_teacher.save()

    response = client.get(reverse("teaching:teacher-profile"))
    assert response.data["jshshir"] == "31234567890123"
    assert response.data["masked_jshshir"] == "**********0123"
    assert response.data["has_jshshir"] is True
    # A password is still never readable — it is a one-way hash.
    assert "password" not in response.data


def test_changing_the_password_needs_both_fields_to_match(client, gate_teacher):
    response = client.patch(
        reverse("teaching:teacher-profile"),
        {"password": "Maktab2026!", "password_confirm": "boshqa"},
        format="json",
    )
    assert response.status_code == 400
    assert "password_confirm" in response.data["error"]["fields"]


def test_a_weak_new_password_is_refused(client, gate_teacher):
    response = client.patch(
        reverse("teaching:teacher-profile"),
        {"password": "12345678", "password_confirm": "12345678"},
        format="json",
    )
    assert response.status_code == 409
    assert response.data["error"]["code"] == "WEAK_PASSWORD"


def test_a_new_password_actually_takes_effect(client, gate_teacher, teaching_user):
    response = client.patch(
        reverse("teaching:teacher-profile"),
        {"password": "Yangi!Parol2026", "password_confirm": "Yangi!Parol2026"},
        format="json",
    )
    assert response.status_code == 200

    teaching_user.refresh_from_db()
    assert teaching_user.check_password("Yangi!Parol2026")
    assert not teaching_user.check_password(PASSWORD)


def test_the_profile_leaves_the_password_alone_when_it_is_not_sent(
    client, gate_teacher, teaching_user
):
    client.patch(
        reverse("teaching:teacher-profile"), {"first_name": "Samir"}, format="json"
    )
    teaching_user.refresh_from_db()
    assert teaching_user.check_password(PASSWORD)


# --------------------------------------------------------------------------- #
# Today's lessons
# --------------------------------------------------------------------------- #
def test_todays_lessons_carry_the_class_the_times_and_the_lock(
    client, gate_teacher, class_subject, class_groups, clock_at
):
    from apps.attendance.models import Schedule
    from apps.schools.services.management import current_academic_year

    clock_at(10, 0)
    Schedule.objects.create(
        academic_year=current_academic_year(class_subject.school),
        class_group=class_groups["7-A"],
        subject=class_subject,
        teacher=gate_teacher,
        weekday=TODAY.isoweekday(),
        lesson_number=1,
        # The clock is pinned to 10:00, so this lesson is still ahead whatever
        # time of day the suite happens to run at.
        start_time="12:00",
        end_time="12:40",
    )

    response = client.get(reverse("teaching:teacher-lessons"))
    assert response.status_code == 200
    row = response.data["results"][0]
    assert row["subject_name"] == "Matematika"
    assert row["class_group_name"] == "7-A"
    assert row["start_time"] == "12:00"
    assert row["end_time"] == "12:40"
    # Two hours ahead of the pinned clock, so it has not started yet.
    assert row["can_mark"] is False
    assert row["opens_at"] == "12:00"


def test_every_lesson_keeps_its_own_subject(client, gate_teacher, class_subject, class_groups, school):
    """A class with several of my subjects must not report them all as one."""
    from apps.attendance.models import Schedule
    from apps.schools.models import Subject
    from apps.schools.services.management import current_academic_year

    group = class_groups["7-A"]
    year = current_academic_year(school)
    physics = Subject.objects.create(school=school, class_group=group, name="Fizika")
    physics.teachers.add(gate_teacher)

    for number, (subject, start, end) in enumerate(
        [(class_subject, "08:00", "08:40"), (physics, "09:00", "09:40")], start=1
    ):
        Schedule.objects.create(
            academic_year=year,
            class_group=group,
            subject=subject,
            teacher=gate_teacher,
            weekday=TODAY.isoweekday(),
            lesson_number=number,
            start_time=start,
            end_time=end,
        )

    rows = client.get(reverse("teaching:teacher-lessons")).data["results"]
    assert [(row["start_time"], row["subject_name"]) for row in rows] == [
        ("08:00", "Matematika"),
        ("09:00", "Fizika"),
    ]


def test_somebody_elses_lesson_with_my_class_is_left_out(
    client, gate_teacher, class_subject, class_groups, school, teacher
):
    from apps.attendance.models import Schedule
    from apps.schools.models import Subject
    from apps.schools.services.management import current_academic_year

    group = class_groups["7-A"]
    theirs = Subject.objects.create(school=school, class_group=group, name="Tarix")
    theirs.teachers.add(teacher)
    Schedule.objects.create(
        academic_year=current_academic_year(school),
        class_group=group,
        subject=theirs,
        teacher=teacher,
        weekday=TODAY.isoweekday(),
        lesson_number=1,
        start_time="08:00",
        end_time="08:40",
    )

    rows = client.get(reverse("teaching:teacher-lessons")).data["results"]
    assert [row["subject_name"] for row in rows] == ["Matematika"]
    assert rows[0]["start_time"] is None  # no timetable of my own → fallback


def test_without_a_timetable_the_lesson_list_still_offers_the_subjects(
    client, gate_teacher, class_subject
):
    response = client.get(reverse("teaching:teacher-lessons"))
    row = response.data["results"][0]
    assert row["subject_name"] == "Matematika"
    assert row["start_time"] is None
    assert row["can_mark"] is True


# --------------------------------------------------------------------------- #
# Access
# --------------------------------------------------------------------------- #
def test_a_parent_cannot_open_the_teacher_cabinet(parent_user):
    for name in ("teacher-dashboard", "teacher-profile", "teacher-lessons"):
        response = as_user(parent_user).get(reverse(f"teaching:{name}"))
        assert response.status_code == 403


def test_an_admin_without_a_teacher_row_is_told_so(db):
    from apps.accounts.constants import Role
    from apps.accounts.models import User

    admin = User.objects.create_user(
        username="adminsiz", password=PASSWORD, role=Role.ADMIN,
        first_name="A", last_name="B",
    )
    response = as_user(admin).get(reverse("teaching:teacher-dashboard"))
    assert response.status_code == 404
    assert response.data["error"]["code"] == "TEACHER_PROFILE_MISSING"


# --------------------------------------------------------------------------- #
# The calendar
# --------------------------------------------------------------------------- #
def timetable(subject, group, weekday, start="08:00", end="08:40", number=1):
    from apps.attendance.models import Schedule
    from apps.schools.services.management import current_academic_year

    return Schedule.objects.create(
        academic_year=current_academic_year(subject.school),
        class_group=group,
        subject=subject,
        weekday=weekday,
        lesson_number=number,
        start_time=start,
        end_time=end,
    )


def calendar_of(client, day=None):
    day = day or TODAY
    return client.get(
        reverse("teaching:teacher-calendar"), {"year": day.year, "month": day.month}
    ).data


def day_of(response, day):
    return next(row for row in response["days"] if row["date"] == day.isoformat())


def test_a_day_with_a_lesson_is_a_teaching_day(
    client, gate_teacher, class_subject, class_groups
):
    timetable(class_subject, class_groups["7-A"], TODAY.isoweekday())

    data = calendar_of(client)
    assert day_of(data, TODAY)["teaches"] is True
    assert day_of(data, TODAY)["groups_count"] == 1


def test_a_day_with_no_lesson_is_not(client, gate_teacher, class_subject, class_groups):
    """The timetable is on one weekday; the next one is empty."""
    timetable(class_subject, class_groups["7-A"], TODAY.isoweekday())

    tomorrow = TODAY + timedelta(days=1)
    data = calendar_of(client, tomorrow)
    if tomorrow.isoweekday() != TODAY.isoweekday():
        assert day_of(data, tomorrow)["teaches"] is False


def test_a_holiday_is_never_a_teaching_day(
    client, gate_teacher, class_subject, class_groups, school, academic_year
):
    from apps.schools.models import Holiday

    timetable(class_subject, class_groups["7-A"], TODAY.isoweekday())
    Holiday.objects.create(
        school=school, academic_year=academic_year, date=TODAY, name="Mustaqillik kuni"
    )

    row = day_of(calendar_of(client), TODAY)
    assert row["teaches"] is False
    assert row["is_school_day"] is False
    assert row["holiday"] == "Mustaqillik kuni"


def test_the_grid_marks_which_days_belong_to_the_month(client, gate_teacher):
    data = calendar_of(client)
    # A Monday-aligned grid always carries a few days of the neighbouring months.
    assert any(row["in_month"] for row in data["days"])
    assert data["year"] == TODAY.year and data["month"] == TODAY.month


def test_a_teacher_with_no_timetable_has_no_green_days(client, gate_teacher, class_subject):
    data = calendar_of(client)
    assert all(row["teaches"] is False for row in data["days"])


def test_the_day_lists_the_classes_and_their_lessons(
    client, gate_teacher, class_subject, class_groups, school, student
):
    from apps.schools.models import Subject

    group = class_groups["7-A"]
    physics = Subject.objects.create(school=school, class_group=group, name="Fizika")
    physics.teachers.add(gate_teacher)
    timetable(class_subject, group, TODAY.isoweekday(), "08:00", "08:40", 1)
    timetable(physics, group, TODAY.isoweekday(), "09:00", "09:40", 2)

    response = client.get(
        reverse("teaching:teacher-calendar-day", args=[TODAY.isoformat()])
    )
    assert response.status_code == 200
    groups = response.data["groups"]
    assert [row["display_name"] for row in groups] == ["7-A"]
    assert [
        (row["start_time"], row["subject_name"]) for row in groups[0]["lessons"]
    ] == [("08:00", "Matematika"), ("09:00", "Fizika")]
    assert groups[0]["students_count"] == 1


def test_a_day_the_teacher_does_not_work_lists_nothing(client, gate_teacher, class_subject):
    response = client.get(
        reverse("teaching:teacher-calendar-day", args=[TODAY.isoformat()])
    )
    assert response.data["groups"] == []


def test_somebody_elses_lesson_is_not_in_my_day(
    client, gate_teacher, class_subject, class_groups, school, teacher
):
    from apps.schools.models import Subject

    theirs = Subject.objects.create(
        school=school, class_group=class_groups["7-A"], name="Tarix"
    )
    theirs.teachers.add(teacher)
    timetable(theirs, class_groups["7-A"], TODAY.isoweekday())

    response = client.get(
        reverse("teaching:teacher-calendar-day", args=[TODAY.isoformat()])
    )
    assert response.data["groups"] == []


def test_a_parent_cannot_read_the_teaching_calendar(parent_user):
    response = as_user(parent_user).get(reverse("teaching:teacher-calendar"))
    assert response.status_code == 403


# --------------------------------------------------------------------------- #
# Search
# --------------------------------------------------------------------------- #
def search(client, term):
    return client.get(reverse("teaching:search"), {"q": term})


def test_search_needs_something_to_go_on(client, gate_teacher):
    assert search(client, "a").data["results"] == []
    assert search(client, "").data["results"] == []


def test_search_finds_a_class_a_subject_and_a_pupil(
    client, gate_teacher, class_subject, class_groups, student
):
    """One query, every kind of record the caller may already open."""
    kinds = {row["kind"] for row in search(client, "7-A").data["results"]}
    assert "class" in kinds

    subjects = [row for row in search(client, "matem").data["results"] if row["kind"] == "subject"]
    assert subjects[0]["title"] == "Matematika"
    assert subjects[0]["subtitle"] == "7-A"
    assert subjects[0]["is_mine"] is True

    pupils = [row for row in search(client, "Valiyev").data["results"] if row["kind"] == "student"]
    assert pupils[0]["title"] == student.full_name
    assert pupils[0]["subtitle"] == "7-A"


def test_search_finds_a_colleague(client, gate_teacher, class_subject):
    rows = [row for row in search(client, "Hasanov").data["results"] if row["kind"] == "teacher"]
    assert rows[0]["title"] == "Hasanov Samir"
    assert "Matematika" in rows[0]["subtitle"]


def test_a_teacher_only_searches_pupils_of_the_classes_they_teach(
    client, gate_teacher, class_subject, student, other_student
):
    """`student` sits in 7-A, which is theirs; `other_student` sits in 7-B."""
    mine = [row["title"] for row in search(client, "Valiyev").data["results"] if row["kind"] == "student"]
    theirs = [row["title"] for row in search(client, "Karimov").data["results"] if row["kind"] == "student"]
    assert mine == [student.full_name]
    assert theirs == []


def test_an_administrator_searches_the_whole_school(db, school, class_groups, student, other_student):
    from apps.accounts.constants import Role
    from apps.accounts.models import User

    admin = User.objects.create_user(
        username="qidiruvadmin", password=PASSWORD, role=Role.ADMIN,
        first_name="Nodir", last_name="Adminov",
    )
    def pupils(term):
        response = as_user(admin).get(reverse("teaching:search"), {"q": term})
        return [row["title"] for row in response.data["results"] if row["kind"] == "student"]

    assert pupils("Valiyev") == [student.full_name]
    assert pupils("Karimov") == [other_student.full_name]


def test_search_never_leaves_the_school(client, gate_teacher, class_groups):
    from apps.schools.models import AcademicYear, ClassGroup, Grade, School

    other = School.objects.create(name="Boshqa maktab")
    ClassGroup.objects.create(
        school=other,
        academic_year=AcademicYear.objects.create(
            school=other, name="2026-2027", start_date=TODAY,
            end_date=TODAY + timedelta(days=200),
        ),
        grade=Grade.objects.create(school=other, level=5),
        name="A",
    )
    titles = [row["title"] for row in search(client, "5-A").data["results"]]
    assert "5-A" not in titles


def test_a_parent_cannot_search(parent_user):
    assert as_user(parent_user).get(reverse("teaching:search"), {"q": "ab"}).status_code == 403


# --------------------------------------------------------------------------- #
# The calendar belongs to the administrators too
# --------------------------------------------------------------------------- #
def test_an_administrator_sees_the_whole_school_on_the_calendar(
    db, school, class_groups, class_subject, teaching_teacher, academic_year
):
    """A teacher's calendar is their own classes; an administrator's is all of them."""
    from apps.accounts.constants import Role
    from apps.accounts.models import User
    from apps.attendance.models import Schedule
    from apps.schools.models import Subject

    # A subject this administrator does not teach — nobody does.
    orphan = Subject.objects.create(
        school=school, class_group=class_groups["3-B"], name="Tarix"
    )
    for subject, group in ((class_subject, class_groups["7-A"]), (orphan, class_groups["3-B"])):
        Schedule.objects.create(
            academic_year=academic_year,
            class_group=group,
            subject=subject,
            weekday=TODAY.isoweekday(),
            lesson_number=1,
            start_time="08:00",
            end_time="08:40",
        )

    admin = User.objects.create_user(
        # An observing role: an ADMIN reads nobody's attendance, so no calendar.
        username="kalendaradmin", password=PASSWORD, role=Role.SUPER_ADMIN,
        first_name="Nodir", last_name="Adminov",
    )
    client = as_user(admin)

    month = client.get(
        reverse("teaching:teacher-calendar"), {"year": TODAY.year, "month": TODAY.month}
    )
    assert month.status_code == 200
    row = next(day for day in month.data["days"] if day["date"] == TODAY.isoformat())
    assert row["teaches"] is True
    assert row["groups_count"] == 2

    day = client.get(reverse("teaching:teacher-calendar-day", args=[TODAY.isoformat()]))
    assert sorted(group["display_name"] for group in day.data["groups"]) == ["3-B", "7-A"]


def test_a_teacher_still_only_sees_their_own_classes(
    client, gate_teacher, class_subject, class_groups, school, academic_year
):
    from apps.attendance.models import Schedule
    from apps.schools.models import Subject

    orphan = Subject.objects.create(
        school=school, class_group=class_groups["3-B"], name="Tarix"
    )
    for subject, group in ((class_subject, class_groups["7-A"]), (orphan, class_groups["3-B"])):
        Schedule.objects.create(
            academic_year=academic_year,
            class_group=group,
            subject=subject,
            weekday=TODAY.isoweekday(),
            lesson_number=1,
            start_time="08:00",
            end_time="08:40",
        )

    day = client.get(reverse("teaching:teacher-calendar-day", args=[TODAY.isoformat()]))
    assert [group["display_name"] for group in day.data["groups"]] == ["7-A"]
