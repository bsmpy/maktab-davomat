"""The home screen per hat: a teacher's lessons today, a curator's groups today."""
from __future__ import annotations

from datetime import time

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts import rbac
from apps.accounts.constants import Role
from apps.accounts.services.auth import issue_tokens
from apps.attendance.models import Schedule
from apps.schools.models import CuratorAssignment, Subject, Teacher
from tests.conftest import TODAY, at

pytestmark = pytest.mark.django_db


def as_user(user):
    client = APIClient()
    access, _refresh, _ttl = issue_tokens(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return client


@pytest.fixture
def every_day_school(school):
    """Whatever weekday the fixture day falls on, it is a school day."""
    school.working_weekdays = [1, 2, 3, 4, 5, 6, 7]
    school.save(update_fields=["working_weekdays"])
    return school


def lesson(academic_year, group, subject, teacher, *, weekday, number, start, end):
    return Schedule.objects.create(
        academic_year=academic_year,
        class_group=group,
        subject=subject,
        teacher=teacher,
        weekday=weekday,
        lesson_number=number,
        start_time=start,
        end_time=end,
    )


@pytest.fixture
def timetable(every_day_school, academic_year, class_groups, class_subject, teaching_teacher):
    """Rasulov gives Matematika 7-A today; a colleague gives 7-A something else
    today; Rasulov also teaches on another weekday."""
    weekday = TODAY.isoweekday()
    other_day = weekday % 7 + 1
    colleague = Teacher.objects.create(
        school=every_day_school, first_name="Nodira", last_name="Usmonova"
    )
    reading = Subject.objects.create(
        school=every_day_school, class_group=class_groups["7-A"], name="Ona tili"
    )
    colleague.subjects.add(reading)

    lesson(academic_year, class_groups["7-A"], class_subject, teaching_teacher,
           weekday=weekday, number=2, start=time(8, 50), end=time(9, 35))
    lesson(academic_year, class_groups["7-A"], reading, colleague,
           weekday=weekday, number=1, start=time(8, 0), end=time(8, 45))
    lesson(academic_year, class_groups["7-A"], class_subject, teaching_teacher,
           weekday=other_day, number=3, start=time(9, 40), end=time(10, 25))


def test_a_teacher_sees_only_the_lessons_they_give_today(
    teaching_user, timetable, student
):
    body = as_user(teaching_user).get(reverse("teaching:teacher-dashboard")).data

    assert [(row["subject_name"], row["class_group_name"], row["start_time"])
            for row in body["lessons_today"]] == [("Matematika", "7-A", "08:50")]
    assert body["lessons_today"][0]["students_count"] == 1
    assert body["lessons_today"][0]["marked_count"] == 0
    # Not a curator right now: no group figures at all.
    assert body["groups_today"] is None


def test_a_teacher_with_nothing_today_gets_an_empty_list(teaching_user, every_day_school):
    body = as_user(teaching_user).get(reverse("teaching:teacher-dashboard")).data
    assert body["lessons_today"] == []


def test_a_curator_sees_only_their_own_groups_today(
    teaching_user, class_groups, student, other_student, timetable
):
    from apps.integrations.models import DailyPresence

    rbac.grant_role(teaching_user, Role.CURATOR)
    rbac.set_active_role(teaching_user, Role.CURATOR)
    CuratorAssignment.objects.create(user=teaching_user, class_group=class_groups["7-B"])
    # Both pupils came in late; only 7-B is this curator's.
    for pupil in (student, other_student):
        DailyPresence.objects.create(
            student=pupil, date=TODAY, first_in_at=at(8, 20), late_minutes=10
        )

    body = as_user(teaching_user).get(reverse("teaching:teacher-dashboard")).data

    assert [row["display_name"] for row in body["groups_today"]] == ["7-B"]
    pupils = body["groups_today"][0]["pupils"]
    assert (pupils["total"], pupils["arrived"], pupils["absent"], pupils["late"]) == (1, 1, 0, 1)
    # Working as a curator, not as a teacher: no lesson list.
    assert body["lessons_today"] is None
