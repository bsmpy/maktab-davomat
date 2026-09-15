"""An ADMIN runs the register but reads nobody's attendance except their own.

No Davomat, no Kalendar, no school figures, no pupil's day, no colleague's week
at the gate — while the register itself (pupils, teachers, staff) stays open.
"""
from __future__ import annotations

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts import rbac
from apps.accounts.catalog import Perm, permissions_for
from apps.accounts.constants import Role
from apps.accounts.models import User
from apps.accounts.services.auth import issue_tokens
from apps.schools.models import StaffMember
from tests.conftest import PASSWORD

pytestmark = pytest.mark.django_db


def as_user(user):
    client = APIClient()
    access, _refresh, _ttl = issue_tokens(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return client


def make_user(username: str, role: str) -> User:
    user = User.objects.create_user(username=username, password=PASSWORD, role=role)
    rbac.set_roles(user, [role], keep_active=False)
    user.refresh_from_db()
    return user


@pytest.fixture
def admin(school) -> User:
    """An administrator who is also on the payroll, so has a day of their own."""
    user = make_user("maktab.admin", Role.ADMIN)
    StaffMember.objects.create(school=school, user=user, first_name="Maftuna", last_name="Xolmatova")
    return user


def test_the_catalogue_holds_back_every_attendance_permission():
    held = permissions_for(Role.ADMIN)
    for permission in (
        Perm.ATTENDANCE_VIEW,
        Perm.ATTENDANCE_MARK,
        Perm.ABSENCE_REVIEW,
        Perm.REPORTS_VIEW,
    ):
        assert permission not in held
    # The register and their own cabinet stay.
    assert {Perm.STUDENTS_VIEW, Perm.TEACHERS_VIEW, Perm.STAFF_CABINET} <= held


def test_an_admin_cannot_open_a_pupils_attendance(admin, student):
    client = as_user(admin)
    for name in ("child-calendar", "child-dashboard"):
        response = client.get(reverse(name, kwargs={"student_id": student.id}))
        assert response.status_code == 403, name


def test_a_super_admin_still_can(school, student):
    boss = make_user("boss", Role.SUPER_ADMIN)
    response = as_user(boss).get(reverse("child-calendar", kwargs={"student_id": student.id}))
    assert response.status_code == 200


def test_an_admin_gets_no_school_figures_registers_or_calendars(admin, class_subject):
    client = as_user(admin)
    for url in (
        reverse("management:overview"),
        reverse("teaching:teaching-subjects"),
        reverse("teaching:teaching-classes"),
        reverse("teaching:teacher-calendar"),
        reverse("settings:presence"),
    ):
        assert client.get(url).status_code == 403, url


def test_an_admin_opens_a_profile_without_the_week_at_the_gate(admin, teaching_teacher):
    body = as_user(admin).get(
        reverse("management:teacher-detail", args=[teaching_teacher.id])
    ).data
    assert body["full_name"]
    assert body["week"] is None


def test_an_admin_still_reads_their_own_day(admin):
    response = as_user(admin).get(reverse("teaching:teacher-dashboard"))
    assert response.status_code == 200
    assert "week" in response.data
    assert response.data["lessons_today"] is None
    assert response.data["groups_today"] is None
