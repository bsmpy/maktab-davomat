"""Cross-cutting security guarantees: masking, logging, throttling, errors."""
from __future__ import annotations

import contextlib
import logging

import pytest
from django.urls import reverse

from apps.audit.services import sanitize
from apps.common.crypto import decrypt, hash_value, mask_jshshir, mask_phone, normalize_jshshir
from apps.common.logging import redact

pytestmark = pytest.mark.django_db

JSHSHIR = "31234567890123"


# --------------------------------------------------------------------------- #
# JSHSHIR storage
# --------------------------------------------------------------------------- #
def test_jshshir_is_never_stored_in_plaintext(guardian):
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT jshshir_hash, jshshir_encrypted, jshshir_last4 FROM guardians_guardian "
            "WHERE id = %s",
            [str(guardian.id)],
        )
        digest, ciphertext, last4 = cursor.fetchone()

    assert JSHSHIR not in digest
    assert JSHSHIR not in ciphertext
    assert last4 == "0123"
    assert digest == hash_value(JSHSHIR)
    # Privileged code can still recover it.
    assert decrypt(ciphertext) == JSHSHIR


def test_masking_helpers():
    assert mask_jshshir("0123") == "**********0123"
    assert mask_phone("+998901234567") == "+998*****4567"
    assert mask_phone("") == ""


def test_lookup_is_by_hash_not_by_value(guardian):
    from apps.guardians.models import Guardian

    assert Guardian.objects.find_by_jshshir(JSHSHIR).first() == guardian
    assert not Guardian.objects.find_by_jshshir("99999999999999").exists()


@pytest.mark.parametrize("bad", ["123", "3123456789012a", "", "311111111111111"])
def test_invalid_jshshir_is_refused(bad):
    with pytest.raises(ValueError):
        normalize_jshshir(bad)


def test_a_jshshir_only_reaches_the_person_it_belongs_to(auth_client, guardian, student):
    """The cabinet shows a guardian their own number, as the school asked for.

    It stays off every other payload: a pupil card, the dashboard and the child
    list have no business carrying somebody's national identifier, and no
    anonymous surface may carry one at all.
    """
    assert JSHSHIR in str(auth_client.get(reverse("auth:me")).data)

    for url in (
        reverse("children"),
        reverse("child-detail", args=[student.id]),
        reverse("child-dashboard", args=[student.id]),
    ):
        assert JSHSHIR not in str(auth_client.get(url).data), url


def test_no_anonymous_surface_can_reach_a_jshshir(api, guardian, student, class_groups):
    """Registration is unauthenticated; the number must never appear there."""
    response = api.get(
        reverse("registration:student-search"),
        {"class_group": str(class_groups["7-A"].id), "q": student.last_name[:4]},
    )
    assert JSHSHIR not in str(response.data)


# --------------------------------------------------------------------------- #
# Logging + audit scrubbing
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("raw", "must_not_contain"),
    [
        (f"guardian jshshir={JSHSHIR}", JSHSHIR),
        ('{"password": "SuperSecret1"}', "SuperSecret1"),
        ("otp_code=483920 sent", "483920"),
        ("Authorization: eyJhbGciOi.eyJzdWIiOiIx.dBjftJeZ4C", "eyJhbGciOi.eyJzdWIiOiIx"),
    ],
)
def test_log_filter_redacts_secrets(raw, must_not_contain):
    assert must_not_contain not in redact(raw)


def test_log_records_are_scrubbed(caplog):
    from apps.common.logging import RedactingFilter

    record = logging.LogRecord(
        "test", logging.INFO, __file__, 1, "login for jshshir %s", (JSHSHIR,), None
    )
    RedactingFilter().filter(record)
    assert JSHSHIR not in record.getMessage()


def test_audit_payloads_drop_secrets():
    cleaned = sanitize(
        {
            "username": "a.valiyev",
            "password": "SuperSecret1",
            "jshshir": JSHSHIR,
            "nested": {"otp_code": "123456", "keep": "visible"},
            "list": [{"token": "abc"}],
        }
    )
    assert cleaned["username"] == "a.valiyev"
    assert cleaned["password"] == "[REDACTED]"
    assert cleaned["jshshir"] == "[REDACTED]"
    assert cleaned["nested"]["otp_code"] == "[REDACTED]"
    assert cleaned["nested"]["keep"] == "visible"
    assert cleaned["list"][0]["token"] == "[REDACTED]"


def test_audit_payloads_are_json_serialisable():
    import json
    import uuid
    from datetime import date

    cleaned = sanitize({"id": uuid.uuid4(), "date": date(2026, 9, 8), "n": 3})
    json.dumps(cleaned)  # must not raise


def test_login_audit_never_stores_the_password(api, parent_user):
    from apps.audit.models import AuditLog
    from tests.conftest import PASSWORD

    api.post(
        reverse("auth:login"), {"login": "a.valiyev", "password": PASSWORD}, format="json"
    )
    for entry in AuditLog.objects.all():
        assert PASSWORD not in str(entry.new_data) + str(entry.old_data) + str(entry.metadata)


# --------------------------------------------------------------------------- #
# Error envelope
# --------------------------------------------------------------------------- #
def test_errors_share_one_shape(api, parent_user):
    response = api.post(
        reverse("auth:login"), {"login": "a.valiyev", "password": "wrong"}, format="json"
    )
    assert response.data["success"] is False
    assert set(response.data["error"]) == {"code", "message", "fields"}
    assert response.data["error"]["code"] == "INVALID_CREDENTIALS"


def test_validation_errors_report_field_names(api):
    response = api.post(reverse("auth:login"), {}, format="json")
    assert response.status_code == 400
    assert response.data["error"]["code"] == "VALIDATION_ERROR"
    assert set(response.data["error"]["fields"]) == {"login", "password"}


def test_no_traceback_reaches_the_client(api, parent_user, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("internal detail that must not leak")

    monkeypatch.setattr("apps.accounts.services.auth.resolve_user", boom)
    response = api.post(
        reverse("auth:login"), {"login": "x", "password": "y"}, format="json"
    )
    assert response.status_code == 500
    assert response.data["error"]["code"] == "INTERNAL_ERROR"
    assert "internal detail" not in str(response.data)
    assert "Traceback" not in str(response.data)


# --------------------------------------------------------------------------- #
# Throttling
# --------------------------------------------------------------------------- #
def test_login_is_throttled(api, settings, parent_user):
    settings.REST_FRAMEWORK = {
        **settings.REST_FRAMEWORK,
        "DEFAULT_THROTTLE_RATES": {
            **settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"],
            "login": "3/hour",
        },
    }
    from apps.common.throttling import LoginThrottle

    LoginThrottle.THROTTLE_RATES = settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]
    try:
        codes = [
            api.post(
                reverse("auth:login"), {"login": "a.valiyev", "password": "no"}, format="json"
            ).status_code
            for _ in range(5)
        ]
        assert 429 in codes
    finally:
        LoginThrottle.THROTTLE_RATES = settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]


def test_student_search_is_throttled(api, settings, class_groups, student):
    from apps.common.throttling import StudentSearchThrottle

    rates = {**settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"], "student_search": "2/hour"}
    StudentSearchThrottle.THROTTLE_RATES = rates
    try:
        payload = {"class_group": str(class_groups["7-A"].id), "query": "Valiyev"}
        codes = [
            api.post(reverse("registration:student-search"), payload, format="json").status_code
            for _ in range(4)
        ]
        assert codes[-1] == 429
    finally:
        StudentSearchThrottle.THROTTLE_RATES = settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]


# --------------------------------------------------------------------------- #
# Soft delete
# --------------------------------------------------------------------------- #
@pytest.fixture
def attendance_rows(student, lessons):
    """Historical per-lesson rows.

    Attendance is produced at the gate now, but the table still holds the
    school's history — and the soft-delete and audit guarantees that protect it
    are exactly what these tests pin.
    """
    from apps.attendance.constants import AttendanceStatus
    from apps.attendance.models import Attendance

    return [
        Attendance.objects.create(
            lesson=lesson, student=student, status=AttendanceStatus.PRESENT
        )
        for lesson in lessons
    ]



def test_deleting_a_student_keeps_the_row_and_its_attendance(student, attendance_rows):
    from apps.attendance.models import Attendance
    from apps.students.models import Student

    student_id = student.id
    student.delete()

    assert not Student.objects.filter(pk=student_id).exists()
    assert Student.all_objects.filter(pk=student_id).exists()
    assert Attendance.objects.filter(student_id=student_id).count() == 6

    Student.all_objects.get(pk=student_id).restore()
    assert Student.objects.filter(pk=student_id).exists()


# --------------------------------------------------------------------------- #
# Bulk-operation audit suppression
# --------------------------------------------------------------------------- #
def test_single_deletion_is_audited_row_by_row(student, attendance_rows):
    from apps.attendance.models import Attendance
    from apps.audit.constants import AuditAction
    from apps.audit.models import AuditLog

    Attendance.objects.filter(pk=attendance_rows[0].pk).delete()
    assert AuditLog.objects.filter(action=AuditAction.ATTENDANCE_DELETE).count() == 1


def test_bulk_delete_writes_one_summary_not_one_row_each(student, attendance_rows):
    """A reseed must not emit an audit INSERT per attendance record."""
    from apps.attendance.models import Attendance
    from apps.audit.constants import AuditAction
    from apps.audit.models import AuditLog
    from apps.audit.services import suppressed

    assert Attendance.objects.count() == 6
    with suppressed({"command": "test"}, action=AuditAction.ATTENDANCE_DELETE):
        Attendance.objects.all().delete()

    entries = AuditLog.objects.filter(action=AuditAction.ATTENDANCE_DELETE)
    assert entries.count() == 1
    assert entries.first().metadata == {"bulk": True, "command": "test"}


def test_suppression_is_lifted_afterwards(student, lessons):
    from apps.attendance.constants import AttendanceStatus
    from apps.attendance.models import Attendance
    from apps.audit.constants import AuditAction
    from apps.audit.models import AuditLog
    from apps.audit.services import is_suppressed, suppressed

    with suppressed():
        Attendance.objects.create(
            lesson=lessons[0], student=student, status=AttendanceStatus.PRESENT
        )
    assert not is_suppressed()
    assert not AuditLog.objects.filter(action=AuditAction.ATTENDANCE_CREATE).exists()

    Attendance.objects.create(
        lesson=lessons[1], student=student, status=AttendanceStatus.PRESENT
    )
    assert AuditLog.objects.filter(action=AuditAction.ATTENDANCE_CREATE).count() == 1


def test_suppression_survives_an_exception(student, lessons):
    from apps.audit.services import is_suppressed, suppressed

    with contextlib.suppress(RuntimeError), suppressed():
        raise RuntimeError("boom")
    assert not is_suppressed()


def test_bulk_delete_of_students_is_also_soft(student, sibling, attendance_rows):
    """An admin mass-deleting from the changelist must not lose attendance."""
    from apps.attendance.models import Attendance
    from apps.students.models import Student

    Student.objects.all().delete()

    assert Student.objects.count() == 0
    assert Student.all_objects.count() == 2
    assert Attendance.objects.filter(student=student).count() == 6

    Student.all_objects.all().restore()
    assert Student.objects.count() == 2


def test_bulk_delete_of_guardians_is_also_soft(guardian):
    from apps.guardians.models import Guardian

    Guardian.objects.all().delete()
    assert Guardian.objects.count() == 0
    assert Guardian.all_objects.count() == 1


def test_hard_delete_really_removes_rows(student):
    """Explicit, and the only way the seed's --flush wipes a demo dataset."""
    from apps.students.models import Student

    Student.all_objects.all().hard_delete()
    assert Student.all_objects.count() == 0
