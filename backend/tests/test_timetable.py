"""Dars jadvali: what an administrator uploads, and what a teacher sees of it.

An administrator picks sinf → guruh → kun and adds lessons in order. A teacher
then opens their cabinet on classes rather than subjects, each flagged green
for today, amber for tomorrow, grey for neither.
"""
from __future__ import annotations

from datetime import timedelta

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.constants import Role
from apps.accounts.models import User
from apps.accounts.services.auth import issue_tokens
from apps.attendance.models import Attendance
from apps.schools.models import Subject
from tests.conftest import PASSWORD, TODAY

pytestmark = pytest.mark.django_db


def as_user(api, user):
    access, _refresh, _ttl = issue_tokens(user)
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return api


@pytest.fixture
def developer(db) -> User:
    return User.objects.create_user(
        username="bsm", password=PASSWORD, role=Role.DEVELOPER,
        first_name="Behruz", last_name="Sattorov",
    )


# Each role gets its own client: sharing one would have the second set of
# credentials overwrite the first.
@pytest.fixture
def admin_client(developer):
    return as_user(APIClient(), developer)


@pytest.fixture
def teacher_client(teaching_user):
    return as_user(APIClient(), teaching_user)


def add(client, group, subject, weekday, start, end, **extra):
    return client.post(
        reverse("management:schedule"),
        {
            "class_group": str(group.id),
            "subject": str(subject.id),
            "weekday": weekday,
            "start_time": start,
            "end_time": end,
            **extra,
        },
        format="json",
    )


# --------------------------------------------------------------------------- #
# Uploading the timetable
# --------------------------------------------------------------------------- #
def test_lessons_are_numbered_by_the_clock_not_by_entry_order(
    admin_client, class_groups, class_subject, school
):
    group = class_groups["7-A"]
    physics = Subject.objects.create(school=school, class_group=group, name="Fizika")

    # Added second, but it runs first.
    later = add(admin_client, group, class_subject, 1, "09:00", "09:40")
    earlier = add(admin_client, group, physics, 1, "08:00", "08:40")
    assert (later.status_code, earlier.status_code) == (201, 201)

    listed = admin_client.get(
        reverse("management:schedule"), {"class_group": str(group.id), "weekday": 1}
    )
    assert [
        (row["lesson_number"], row["start_time"], row["subject_name"])
        for row in listed.data["results"]
    ] == [(1, "08:00", "Fizika"), (2, "09:00", "Matematika")]


def test_the_lesson_carries_its_class_group_in_the_name(
    admin_client, class_groups, class_subject, teaching_teacher
):
    response = add(admin_client, class_groups["7-A"], class_subject, 1, "08:00", "08:40")
    assert response.data["subject_display"] == "Matematika 7-A"
    assert response.data["weekday_label"] == "Dushanba"
    assert response.data["teacher_name"] == "Rasulov Saodaddin"


def test_two_lessons_cannot_overlap(admin_client, class_groups, class_subject, school):
    group = class_groups["7-A"]
    physics = Subject.objects.create(school=school, class_group=group, name="Fizika")

    assert add(admin_client, group, class_subject, 1, "08:00", "08:40").status_code == 201
    clash = add(admin_client, group, physics, 1, "08:30", "09:10")
    assert clash.status_code == 409
    assert clash.data["error"]["code"] == "LESSON_OVERLAP"

    # The same times on another weekday are fine.
    assert add(admin_client, group, physics, 2, "08:30", "09:10").status_code == 201


def test_the_end_must_come_after_the_start(admin_client, class_groups, class_subject):
    response = add(admin_client, class_groups["7-A"], class_subject, 1, "09:00", "08:00")
    assert response.status_code == 409
    assert response.data["error"]["code"] == "INVALID_TIME_RANGE"


def test_a_subject_from_another_class_is_refused(admin_client, class_groups, class_subject):
    response = add(admin_client, class_groups["7-B"], class_subject, 1, "08:00", "08:40")
    assert response.status_code == 404
    assert response.data["error"]["code"] == "SUBJECT_NOT_IN_GROUP"


def test_removing_a_lesson_closes_the_gap(admin_client, class_groups, class_subject, school):
    group = class_groups["7-A"]
    physics = Subject.objects.create(school=school, class_group=group, name="Fizika")
    first = add(admin_client, group, class_subject, 1, "08:00", "08:40")
    add(admin_client, group, physics, 1, "09:00", "09:40")

    admin_client.delete(reverse("management:schedule-detail", args=[first.data["id"]]))

    listed = admin_client.get(
        reverse("management:schedule"), {"class_group": str(group.id), "weekday": 1}
    )
    assert [(row["lesson_number"], row["subject_name"]) for row in listed.data["results"]] == [
        (1, "Fizika")
    ]


# --------------------------------------------------------------------------- #
# The teacher's classes
# --------------------------------------------------------------------------- #
def test_the_cabinet_lists_classes_not_subjects(teacher_client, class_subject, student):
    response = teacher_client.get(reverse("teaching:teaching-classes"))
    assert response.status_code == 200
    card = response.data["results"][0]
    assert card["display_name"] == "7-A"
    assert card["students_count"] == 1
    assert [row["name"] for row in card["subjects"]] == ["Matematika"]


@pytest.mark.parametrize(
    ("offset", "state"),
    [(0, "TODAY"), (1, "TOMORROW"), (2, "NONE"), (5, "NONE")],
)
def test_the_marker_says_today_tomorrow_or_neither(
    admin_client, teacher_client, class_groups, class_subject, offset, state
):
    """A lesson `offset` days from now colours the dot accordingly."""
    weekday = (TODAY + timedelta(days=offset)).isoweekday()
    add(admin_client, class_groups["7-A"], class_subject, weekday, "08:00", "08:40")

    response = teacher_client.get(reverse("teaching:teaching-classes"))
    assert response.data["results"][0]["schedule_state"] == state


def test_a_class_with_no_timetable_is_grey(teacher_client, class_subject):
    response = teacher_client.get(reverse("teaching:teaching-classes"))
    assert response.data["results"][0]["schedule_state"] == "NONE"


def test_somebody_elses_lesson_does_not_light_up_my_class(
    admin_client, teacher_client, class_groups, class_subject, school, teacher
):
    """The dot follows *my* subjects, not everything the class does."""
    other = Subject.objects.create(school=school, class_group=class_groups["7-A"], name="Fizika")
    other.teachers.add(teacher)
    add(admin_client, class_groups["7-A"], other, TODAY.isoweekday(), "08:00", "08:40")

    response = teacher_client.get(reverse("teaching:teaching-classes"))
    assert response.data["results"][0]["schedule_state"] == "NONE"


# --------------------------------------------------------------------------- #
# One class, one day
# --------------------------------------------------------------------------- #
def test_the_class_day_shows_the_timetable_and_whose_lesson_it_is(
    admin_client, teacher_client, class_groups, class_subject, school, teacher, student
):
    group = class_groups["7-A"]
    physics = Subject.objects.create(school=school, class_group=group, name="Fizika")
    physics.teachers.add(teacher)
    add(admin_client, group, class_subject, TODAY.isoweekday(), "08:00", "08:40", room="101")
    add(admin_client, group, physics, TODAY.isoweekday(), "09:00", "09:40")

    response = teacher_client.get(reverse("teaching:teaching-class-day", args=[group.id]))
    assert response.status_code == 200
    assert response.data["has_timetable"] is True

    lessons = response.data["lessons"]
    assert [(row["subject_name"], row["is_mine"]) for row in lessons] == [
        ("Matematika", True),
        ("Fizika", False),
    ]
    assert lessons[0]["start_time"] == "08:00"
    assert lessons[0]["room"] == "101"
    assert lessons[0]["students_count"] == 1


def test_without_a_timetable_the_class_day_still_offers_my_subjects(
    teacher_client, class_groups, class_subject, student
):
    response = teacher_client.get(
        reverse("teaching:teaching-class-day", args=[class_groups["7-A"].id])
    )
    assert response.data["has_timetable"] is False
    assert [row["subject_name"] for row in response.data["lessons"]] == ["Matematika"]
    assert response.data["lessons"][0]["start_time"] is None


def test_a_teacher_cannot_open_a_class_they_do_not_teach(teacher_client, class_groups):
    response = teacher_client.get(
        reverse("teaching:teaching-class-day", args=[class_groups["3-B"].id])
    )
    assert response.status_code == 404
    assert response.data["error"]["code"] == "CLASS_GROUP_NOT_FOUND"


def test_the_class_day_counts_what_is_already_marked(
    teacher_client, class_groups, class_subject, student
):
    teacher_client.post(
        reverse("teaching:teaching-roster", args=[class_subject.id]),
        {
            "date": TODAY.isoformat(),
            "marks": [{"student": str(student.id), "status": "PRESENT"}],
        },
        format="json",
    )
    response = teacher_client.get(
        reverse("teaching:teaching-class-day", args=[class_groups["7-A"].id])
    )
    assert response.data["lessons"][0]["marked_count"] == 1


def test_the_schedule_is_scoped_to_the_users_school(api, class_groups, class_subject):
    """A parent has no business reading the timetable surface at all."""
    from apps.accounts.constants import Role as R

    outsider = User.objects.create_user(
        username="ota", password=PASSWORD, role=R.PARENT, first_name="O", last_name="T"
    )
    response = as_user(api, outsider).get(reverse("teaching:teaching-classes"))
    assert response.status_code == 403


# --------------------------------------------------------------------------- #
# A lesson cannot be marked before it starts
# --------------------------------------------------------------------------- #
def mark(client, subject, day, student, status="PRESENT"):
    return client.post(
        reverse("teaching:teaching-roster", args=[subject.id]),
        {"date": day.isoformat(), "marks": [{"student": str(student.id), "status": status}]},
        format="json",
    )


def _timetable_at(admin_client, group, subject, start, end):
    """Put the lesson on today at the given clock times."""
    return add(admin_client, group, subject, TODAY.isoweekday(), start, end)


#: Fixed lesson windows, read against a pinned clock of 10:00.
NOW_HOUR = 10
BEFORE = ("09:00", "09:40")
AFTER = ("12:00", "12:40")


def test_the_register_is_locked_until_the_lesson_starts(
    admin_client, teacher_client, class_groups, class_subject, student, clock_at
):
    clock_at(NOW_HOUR)
    _timetable_at(admin_client, class_groups["7-A"], class_subject, *AFTER)

    response = mark(teacher_client, class_subject, TODAY, student)
    assert response.status_code == 409
    assert response.data["error"]["code"] == "LESSON_NOT_STARTED"
    assert AFTER[0] in response.data["error"]["message"]
    assert not Attendance.objects.exists()


def test_the_register_opens_once_the_lesson_has_begun(
    admin_client, teacher_client, class_groups, class_subject, student, clock_at
):
    clock_at(NOW_HOUR)
    _timetable_at(admin_client, class_groups["7-A"], class_subject, *BEFORE)

    assert mark(teacher_client, class_subject, TODAY, student).status_code == 200
    assert Attendance.objects.count() == 1


def test_an_existing_mark_cannot_be_changed_before_the_lesson_starts(
    admin_client, teacher_client, class_groups, class_subject, student, clock_at
):
    """Even a correction has to wait: the lesson has not happened yet."""
    assert mark(teacher_client, class_subject, TODAY, student).status_code == 200

    clock_at(NOW_HOUR)
    _timetable_at(admin_client, class_groups["7-A"], class_subject, *AFTER)

    response = mark(teacher_client, class_subject, TODAY, student, status="ABSENT")
    assert response.status_code == 409
    assert Attendance.objects.get().status == "PRESENT"


def test_a_past_day_is_always_open(
    admin_client, teacher_client, class_groups, class_subject, student
):
    """Yesterday's lesson is over whatever the clock says now."""
    yesterday = TODAY - timedelta(days=1)
    add(
        admin_client,
        class_groups["7-A"],
        class_subject,
        yesterday.isoweekday(),
        "23:30",
        "23:59",
    )
    assert mark(teacher_client, class_subject, yesterday, student).status_code == 200


def test_without_a_timetable_the_register_stays_open(
    teacher_client, class_subject, student
):
    assert mark(teacher_client, class_subject, TODAY, student).status_code == 200


def test_the_roster_says_when_the_register_opens(
    admin_client, teacher_client, class_groups, class_subject, student, clock_at
):
    clock_at(NOW_HOUR)
    _timetable_at(admin_client, class_groups["7-A"], class_subject, *AFTER)

    response = teacher_client.get(
        reverse("teaching:teaching-roster", args=[class_subject.id]),
        {"date": TODAY.isoformat()},
    )
    # The roll call does not open before the bell — not even to read.
    assert response.status_code == 409
    assert response.data["error"]["code"] == "LESSON_NOT_STARTED"
    assert AFTER[0] in response.data["error"]["message"]
    assert "students" not in response.data


def test_the_roster_opens_once_the_lesson_has_begun(
    admin_client, teacher_client, class_groups, class_subject, student, clock_at
):
    clock_at(NOW_HOUR)
    _timetable_at(admin_client, class_groups["7-A"], class_subject, *BEFORE)

    response = teacher_client.get(
        reverse("teaching:teaching-roster", args=[class_subject.id]),
        {"date": TODAY.isoformat()},
    )
    assert response.status_code == 200
    assert response.data["can_mark"] is True
    assert [row["id"] for row in response.data["students"]] == [str(student.id)]


def test_a_future_day_roster_does_not_open(teacher_client, class_subject, student):
    response = teacher_client.get(
        reverse("teaching:teaching-roster", args=[class_subject.id]),
        {"date": (TODAY + timedelta(days=1)).isoformat()},
    )
    assert response.status_code == 409
    assert response.data["error"]["code"] == "FUTURE_DATE"


def test_the_class_day_flags_which_lessons_are_open(
    admin_client, teacher_client, class_groups, class_subject, school, student, clock_at
):
    group = class_groups["7-A"]
    physics = Subject.objects.create(school=school, class_group=group, name="Fizika")
    physics.teachers.add(class_subject.teachers.first())

    clock_at(NOW_HOUR)
    _timetable_at(admin_client, group, class_subject, *BEFORE)
    clock_at(NOW_HOUR)
    _timetable_at(admin_client, group, physics, *AFTER)

    response = teacher_client.get(
        reverse("teaching:teaching-class-day", args=[group.id])
    )
    assert {row["subject_name"]: row["can_mark"] for row in response.data["lessons"]} == {
        "Matematika": True,
        "Fizika": False,
    }
