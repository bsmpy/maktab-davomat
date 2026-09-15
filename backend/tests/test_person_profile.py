"""Профиль по клику на карточку: полнота данных и кто его может открыть."""
from __future__ import annotations

from datetime import time

import pytest
from django.urls import reverse

from apps.accounts import rbac
from apps.accounts.constants import Role
from apps.accounts.models import User
from apps.accounts.services.auth import issue_tokens
from apps.attendance.models import Schedule
from apps.schools.models import CuratorAssignment, StaffMember

from .conftest import PASSWORD

pytestmark = pytest.mark.django_db


def as_user(api, user):
    access, _refresh, _ttl = issue_tokens(user)
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return api


def make_user(username: str, *roles: str) -> User:
    user = User.objects.create_user(username=username, password=PASSWORD, role=roles[0])
    rbac.set_roles(user, roles, keep_active=False)
    user.refresh_from_db()
    return user


@pytest.fixture
def developer() -> User:
    return make_user("owner", Role.DEVELOPER)


@pytest.fixture
def curating_teacher(teaching_user, teaching_teacher, class_subject, academic_year, class_groups):
    """Matematika 7-A, куратор той же группы, два урока в расписании."""
    rbac.grant_role(teaching_user, Role.CURATOR)
    CuratorAssignment.objects.create(user=teaching_user, class_group=class_groups["7-A"])
    teaching_teacher.passport_id = "AB1234567"
    teaching_teacher.set_jshshir("31501198712345")
    teaching_teacher.save()
    for weekday, number, start, end in (
        (1, 1, time(8, 0), time(8, 45)),
        (3, 2, time(8, 50), time(9, 35)),
    ):
        Schedule.objects.create(
            academic_year=academic_year,
            class_group=class_groups["7-A"],
            subject=class_subject,
            teacher=teaching_teacher,
            weekday=weekday,
            lesson_number=number,
            start_time=start,
            end_time=end,
        )
    return teaching_teacher


def test_a_teacher_profile_carries_everything_the_card_opens(api, developer, curating_teacher):
    body = as_user(api, developer).get(
        reverse("management:teacher-detail", args=[curating_teacher.id])
    ).data

    assert body["kind"] == "teacher"
    assert body["passport_id"] == "AB1234567"
    assert body["jshshir"] == "31501198712345"
    # Аккаунт: логин и все роли, но ни следа пароля.
    assert body["account"]["username"] == "s.rasulov"
    assert set(body["account"]["roles"]) == {Role.TEACHER, Role.CURATOR}
    assert "password" not in body["account"]
    # Работа: предметы по классам, кураторство и неделя из расписания.
    assert body["subjects"] == [{"class_group": "7-A", "subjects": ["Matematika"]}]
    assert [row["display_name"] for row in body["curator_groups"]] == ["7-A"]
    assert body["timetable"]["lessons_per_week"] == 2
    assert [day["label"] for day in body["timetable"]["days"]] == ["Dushanba", "Chorshanba"]


def test_a_staff_profile_has_the_position_and_no_timetable(api, developer, school):
    person = make_user("oshpaz", Role.STAFF)
    member = StaffMember.objects.create(
        school=school, user=person, first_name="Zilola", last_name="Umarova",
        phone="+998901112233", email="z.umarova@maktab.uz",
    )
    body = as_user(api, developer).get(
        reverse("management:staff-detail", args=[member.id])
    ).data

    assert body["kind"] == "staff"
    assert body["email"] == "z.umarova@maktab.uz"
    assert body["account"]["roles"] == [Role.STAFF]
    assert body["timetable"] == {"lessons_per_week": 0, "days": []}


def test_a_moderator_may_open_a_profile(api, curating_teacher):
    moderator = make_user("watcher", Role.MODERATOR)
    response = as_user(api, moderator).get(
        reverse("management:teacher-detail", args=[curating_teacher.id])
    )
    assert response.status_code == 200


def test_a_teacher_may_not_open_a_colleagues_profile(api, curating_teacher, teacher_user):
    """Карточки — раздел реестра; учителю туда нельзя и через прямой URL."""
    response = as_user(api, teacher_user).get(
        reverse("management:teacher-detail", args=[curating_teacher.id])
    )
    assert response.status_code == 403


def test_a_curator_card_knows_whose_profile_to_open(api, developer, curating_teacher):
    rows = as_user(api, developer).get(reverse("management:curators")).data["results"]
    assert rows[0]["teacher_id"] == str(curating_teacher.id)
    assert rows[0]["staff_id"] is None
