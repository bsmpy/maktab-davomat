"""Object-level access control.

A parent may only ever reach their own verified children — and passing a
different id from the frontend must not change that.
"""
from __future__ import annotations

import pytest
from django.urls import reverse

from apps.accounts.services.auth import issue_tokens
from apps.guardians.models import GuardianStudent

pytestmark = pytest.mark.django_db

CHILD_ENDPOINTS = (
    "child-dashboard",
    "attendance-daily",
    "attendance-weekly",
    "attendance-monthly",
    "attendance-yearly",
    "child-calendar",
    "child-absence-requests",
)


def as_user(api, user):
    access, _refresh, _ttl = issue_tokens(user)
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return api


def test_parent_sees_only_their_own_children(auth_client, student, sibling, other_student):
    response = auth_client.get(reverse("children"))
    assert response.status_code == 200
    ids = {item["id"] for item in response.data["results"]}
    assert ids == {str(student.id), str(sibling.id)}
    assert str(other_student.id) not in ids


@pytest.mark.parametrize("endpoint", CHILD_ENDPOINTS)
def test_parent_cannot_read_another_parents_child(auth_client, other_student, endpoint):
    response = auth_client.get(reverse(endpoint, args=[other_student.id]))
    assert response.status_code == 404
    assert response.data["error"]["code"] == "STUDENT_NOT_FOUND"


@pytest.mark.parametrize("endpoint", CHILD_ENDPOINTS)
def test_own_child_is_readable(auth_client, student, endpoint):
    assert auth_client.get(reverse(endpoint, args=[student.id])).status_code == 200


def test_unverified_link_does_not_grant_access(auth_client, parent_user, student):
    GuardianStudent.objects.filter(student=student).update(verified=False)
    assert auth_client.get(reverse("child-dashboard", args=[student.id])).status_code == 404
    assert auth_client.get(reverse("children")).data["count"] == 1


def test_soft_deleted_child_disappears(auth_client, student):
    student.delete()  # soft delete
    assert auth_client.get(reverse("child-dashboard", args=[student.id])).status_code == 404


def test_parent_cannot_review_absence_requests(auth_client, student, reason, parent_user):
    from apps.attendance.services.absence import submit_absence_request
    from tests.conftest import TODAY

    request = submit_absence_request(
        student=student, day=TODAY, reason=reason, submitted_by=parent_user
    )
    response = auth_client.post(
        reverse("teaching:review-absence-request", args=[request.id, "approve"]),
        {},
        format="json",
    )
    assert response.status_code == 403


def test_teacher_sees_their_own_classes_only(api, teacher_user, schedule, student, other_student):
    client = as_user(api, teacher_user)
    assert client.get(reverse("child-dashboard", args=[student.id])).status_code == 200
    assert client.get(reverse("child-dashboard", args=[other_student.id])).status_code == 404


def test_teacher_can_review_a_reason_for_their_own_pupil(
    api, teacher_user, schedule, student, reason, parent_user
):
    from apps.attendance.services.absence import submit_absence_request
    from tests.conftest import TODAY

    request = submit_absence_request(
        student=student, day=TODAY, reason=reason, submitted_by=parent_user
    )
    client = as_user(api, teacher_user)
    response = client.post(
        reverse("teaching:review-absence-request", args=[request.id, "approve"]),
        {},
        format="json",
    )
    assert response.status_code == 200
    assert response.data["status"] == "APPROVED"


def test_teacher_cannot_review_a_reason_for_someone_elses_pupil(
    api, teacher_user, schedule, other_student, reason, other_parent
):
    from apps.attendance.services.absence import submit_absence_request
    from tests.conftest import TODAY

    request = submit_absence_request(
        student=other_student, day=TODAY, reason=reason, submitted_by=other_parent
    )
    client = as_user(api, teacher_user)
    response = client.post(
        reverse("teaching:review-absence-request", args=[request.id, "approve"]),
        {},
        format="json",
    )
    assert response.status_code == 403
