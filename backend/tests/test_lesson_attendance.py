"""Dars davomati — the register a teacher fills in, and what a parent reads.

    keldi                   → PRESENT
    kechikdi + daqiqa       → LATE
    kelmadi, sababsiz       → ABSENT
    kelmadi, sababli + izoh → EXCUSED
"""
from __future__ import annotations

from datetime import timedelta

import pytest
from django.urls import reverse

from apps.accounts.services.auth import issue_tokens
from apps.attendance.models import Attendance, Lesson
from tests.conftest import PASSWORD, TODAY

pytestmark = pytest.mark.django_db


def as_user(api, user):
    access, _refresh, _ttl = issue_tokens(user)
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return api


@pytest.fixture
def client(api, teaching_user):
    return as_user(api, teaching_user)


@pytest.fixture
def school_admin(school, db):
    """An administrator, scoped to the school through their teacher row."""
    from apps.accounts.constants import Role
    from apps.accounts.models import User
    from apps.schools.models import Teacher

    user = User.objects.create_user(
        username="maktabadmin", password=PASSWORD, role=Role.ADMIN,
        first_name="Nodir", last_name="Adminov",
    )
    Teacher.objects.create(school=school, user=user, first_name="Nodir", last_name="Adminov")
    return user


def roster_url(subject):
    return reverse("teaching:teaching-roster", args=[subject.id])


# --------------------------------------------------------------------------- #
# The cards
# --------------------------------------------------------------------------- #
def test_a_teacher_only_sees_their_own_subjects(client, class_subject, subject):
    """Rasulov carries Matematika 7-A; the other subject is not his."""
    response = client.get(reverse("teaching:teaching-subjects"))
    assert response.status_code == 200
    assert [row["display_name"] for row in response.data["results"]] == ["Matematika 7-A"]


def test_the_card_carries_the_class_and_how_much_is_done(
    client, class_subject, student, other_student
):
    response = client.get(reverse("teaching:teaching-subjects"))
    card = response.data["results"][0]
    assert card["class_group_name"] == "7-A"
    assert card["grade_level"] == 7
    # Only 7-A counts; other_student sits in 7-B.
    assert card["students_count"] == 1
    assert card["marked_count"] == 0
    assert card["teachers"] == ["Rasulov Saodaddin"]


def test_a_parent_cannot_open_the_register(api, parent_user, class_subject):
    response = as_user(api, parent_user).get(reverse("teaching:teaching-subjects"))
    assert response.status_code == 403


def test_an_admin_does_not_open_the_lesson_register(api, school_admin, class_subject):
    """An ADMIN runs the register of people, not anybody's attendance."""
    response = as_user(api, school_admin).get(reverse("teaching:teaching-subjects"))
    assert response.status_code == 403


# --------------------------------------------------------------------------- #
# The roster
# --------------------------------------------------------------------------- #
def test_the_roster_lists_the_class_with_no_marks_yet(client, class_subject, student):
    response = client.get(roster_url(class_subject), {"date": TODAY.isoformat()})
    assert response.status_code == 200
    assert response.data["subject"]["display_name"] == "Matematika 7-A"

    row = response.data["students"][0]
    assert row["full_name"] == student.full_name
    assert row["status"] is None
    assert row["late_minutes"] == 0
    # Reading the register must not create a lesson.
    assert not Lesson.objects.filter(subject=class_subject, date=TODAY).exists()


def test_a_teacher_cannot_open_somebody_elses_subject(api, teacher_user, class_subject):
    """``teacher_user`` carries the school-wide subject, not this one."""
    response = as_user(api, teacher_user).get(roster_url(class_subject))
    assert response.status_code == 404
    assert response.data["error"]["code"] == "SUBJECT_NOT_FOUND"


# --------------------------------------------------------------------------- #
# Marking
# --------------------------------------------------------------------------- #
def test_marking_present_creates_the_lesson_on_first_use(client, class_subject, student):
    response = client.post(
        roster_url(class_subject),
        {
            "date": TODAY.isoformat(),
            "marks": [{"student": str(student.id), "status": "PRESENT"}],
        },
        format="json",
    )
    assert response.status_code == 200
    assert response.data["students"][0]["status"] == "PRESENT"
    assert response.data["students"][0]["status_label"] == "Keldi"
    assert response.data["subject"]["marked_count"] == 1

    lesson = Lesson.objects.get(subject=class_subject, date=TODAY)
    assert lesson.class_group_id == class_subject.class_group_id
    assert Attendance.objects.get(lesson=lesson, student=student).status == "PRESENT"


def test_late_needs_the_minutes(client, class_subject, student):
    refused = client.post(
        roster_url(class_subject),
        {
            "date": TODAY.isoformat(),
            "marks": [{"student": str(student.id), "status": "LATE"}],
        },
        format="json",
    )
    assert refused.status_code == 400
    assert refused.data["error"]["code"] == "LATE_MINUTES_REQUIRED"
    assert not Attendance.objects.exists()

    accepted = client.post(
        roster_url(class_subject),
        {
            "date": TODAY.isoformat(),
            "marks": [{"student": str(student.id), "status": "LATE", "late_minutes": 12}],
        },
        format="json",
    )
    assert accepted.status_code == 200
    assert accepted.data["students"][0]["late_minutes"] == 12
    assert accepted.data["students"][0]["status_label"] == "Kechikdi"


def test_an_excused_absence_needs_a_written_reason(client, class_subject, student):
    refused = client.post(
        roster_url(class_subject),
        {
            "date": TODAY.isoformat(),
            "marks": [{"student": str(student.id), "status": "EXCUSED"}],
        },
        format="json",
    )
    assert refused.status_code == 400
    assert refused.data["error"]["code"] == "REASON_REQUIRED"

    accepted = client.post(
        roster_url(class_subject),
        {
            "date": TODAY.isoformat(),
            "marks": [
                {
                    "student": str(student.id),
                    "status": "EXCUSED",
                    "comment": "Shifokorga bordi",
                }
            ],
        },
        format="json",
    )
    assert accepted.status_code == 200
    assert accepted.data["students"][0]["comment"] == "Shifokorga bordi"


def test_an_unexcused_absence_needs_nothing_else(client, class_subject, student):
    response = client.post(
        roster_url(class_subject),
        {
            "date": TODAY.isoformat(),
            "marks": [{"student": str(student.id), "status": "ABSENT"}],
        },
        format="json",
    )
    assert response.status_code == 200
    assert response.data["students"][0]["status_label"] == "Kelmadi"
    assert response.data["students"][0]["comment"] == ""


def test_a_reason_is_dropped_from_a_present_pupil(client, class_subject, student):
    """Switching kelmadi → keldi must not leave the old reason behind."""
    client.post(
        roster_url(class_subject),
        {
            "date": TODAY.isoformat(),
            "marks": [
                {"student": str(student.id), "status": "EXCUSED", "comment": "Kasal"}
            ],
        },
        format="json",
    )
    response = client.post(
        roster_url(class_subject),
        {
            "date": TODAY.isoformat(),
            "marks": [
                {"student": str(student.id), "status": "PRESENT", "comment": "Kasal"}
            ],
        },
        format="json",
    )
    assert response.data["students"][0]["comment"] == ""
    assert Attendance.objects.count() == 1


def test_re_marking_updates_the_same_row(client, class_subject, student):
    for status in ("PRESENT", "ABSENT"):
        client.post(
            roster_url(class_subject),
            {
                "date": TODAY.isoformat(),
                "marks": [{"student": str(student.id), "status": status}],
            },
            format="json",
        )
    assert Attendance.objects.count() == 1
    assert Attendance.objects.get().status == "ABSENT"


def test_clearing_a_mark_removes_the_row(client, class_subject, student):
    client.post(
        roster_url(class_subject),
        {
            "date": TODAY.isoformat(),
            "marks": [{"student": str(student.id), "status": "PRESENT"}],
        },
        format="json",
    )
    response = client.post(
        roster_url(class_subject),
        {"date": TODAY.isoformat(), "marks": [{"student": str(student.id), "status": ""}]},
        format="json",
    )
    assert response.data["students"][0]["status"] is None
    assert not Attendance.objects.exists()


def test_a_pupil_from_another_class_cannot_be_marked(client, class_subject, other_student):
    response = client.post(
        roster_url(class_subject),
        {
            "date": TODAY.isoformat(),
            "marks": [{"student": str(other_student.id), "status": "PRESENT"}],
        },
        format="json",
    )
    assert response.status_code == 404
    assert response.data["error"]["code"] == "STUDENT_NOT_IN_GROUP"


def test_a_future_day_cannot_be_marked(client, class_subject, student):
    response = client.post(
        roster_url(class_subject),
        {
            "date": (TODAY + timedelta(days=1)).isoformat(),
            "marks": [{"student": str(student.id), "status": "PRESENT"}],
        },
        format="json",
    )
    assert response.status_code == 409
    assert response.data["error"]["code"] == "FUTURE_DATE"


def test_two_subjects_for_one_class_get_their_own_lesson_slot(
    client, class_subject, class_groups, school, student
):
    """Marking a second subject the same day must not collide on the slot."""
    from apps.schools.models import Subject

    second = Subject.objects.create(
        school=school, class_group=class_groups["7-A"], name="Fizika"
    )
    second.teachers.add(class_subject.teachers.first())

    for subject in (class_subject, second):
        response = client.post(
            roster_url(subject),
            {
                "date": TODAY.isoformat(),
                "marks": [{"student": str(student.id), "status": "PRESENT"}],
            },
            format="json",
        )
        assert response.status_code == 200

    numbers = sorted(
        Lesson.objects.filter(class_group=class_groups["7-A"], date=TODAY).values_list(
            "lesson_number", flat=True
        )
    )
    assert numbers == [1, 2]


# --------------------------------------------------------------------------- #
# What the parent sees
# --------------------------------------------------------------------------- #
def test_a_parent_reads_the_marks_their_teacher_entered(
    api, client, parent_user, class_subject, student
):
    client.post(
        roster_url(class_subject),
        {
            "date": TODAY.isoformat(),
            "marks": [{"student": str(student.id), "status": "LATE", "late_minutes": 7}],
        },
        format="json",
    )

    response = as_user(api, parent_user).get(
        reverse("attendance-lessons", args=[student.id]), {"start": TODAY.isoformat()}
    )
    assert response.status_code == 200
    assert response.data["summary"]["lessons"] == 1
    assert response.data["summary"]["late"] == 1
    assert response.data["summary"]["rate"] == 100.0

    lesson = response.data["days"][0]["lessons"][0]
    assert lesson["subject_display"] == "Matematika 7-A"
    assert lesson["status_label"] == "Kechikdi"
    assert lesson["late_minutes"] == 7
    assert lesson["teacher"] == "Rasulov Saodaddin"


def test_the_parent_summary_counts_each_status(api, client, parent_user, class_subject, student):
    for offset, mark in enumerate(
        [
            {"status": "PRESENT"},
            {"status": "LATE", "late_minutes": 5},
            {"status": "ABSENT"},
            {"status": "EXCUSED", "comment": "Kasal"},
        ]
    ):
        client.post(
            roster_url(class_subject),
            {
                "date": (TODAY - timedelta(days=offset)).isoformat(),
                "marks": [{"student": str(student.id), **mark}],
            },
            format="json",
        )

    response = as_user(api, parent_user).get(
        reverse("attendance-lessons", args=[student.id]),
        {"start": (TODAY - timedelta(days=3)).isoformat(), "end": TODAY.isoformat()},
    )
    summary = response.data["summary"]
    assert (summary["present"], summary["late"], summary["absent"], summary["excused"]) == (
        1,
        1,
        1,
        1,
    )
    assert summary["attended"] == 2
    assert summary["rate"] == 50.0

    # Per subject, the same four lessons.
    assert response.data["subjects"][0]["display_name"] == "Matematika 7-A"
    assert response.data["subjects"][0]["lessons"] == 4


def test_the_yearly_view_can_skip_the_day_by_day_list(
    api, client, parent_user, class_subject, student
):
    client.post(
        roster_url(class_subject),
        {
            "date": TODAY.isoformat(),
            "marks": [{"student": str(student.id), "status": "PRESENT"}],
        },
        format="json",
    )
    response = as_user(api, parent_user).get(
        reverse("attendance-lessons", args=[student.id]),
        {"start": TODAY.isoformat(), "include_days": "false"},
    )
    assert response.data["days"] == []
    assert response.data["subjects"][0]["lessons"] == 1


def test_a_parent_cannot_read_another_familys_lessons(api, other_parent, student):
    response = as_user(api, other_parent).get(
        reverse("attendance-lessons", args=[student.id])
    )
    assert response.status_code == 404
