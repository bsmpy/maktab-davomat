"""Presence reports (kirish-chiqish) and the absence-reason workflow."""
from __future__ import annotations

from datetime import timedelta

import pytest
from django.urls import reverse

from apps.attendance.constants import AbsenceRequestStatus
from apps.attendance.services import (
    build_daily_presence,
    build_monthly_presence,
    build_weekly_presence,
    build_yearly_presence,
)
from apps.attendance.services.absence import (
    approve_absence_request,
    reject_absence_request,
    submit_absence_request,
)
from tests.conftest import TODAY

pytestmark = pytest.mark.django_db


def _sunday_after(day):
    """The first Sunday strictly after ``day`` — the school's only closed day."""
    return day + timedelta(days=(7 - day.isoweekday()) or 7)


# --------------------------------------------------------------------------- #
# Daily
# --------------------------------------------------------------------------- #
def test_daily_report_describes_the_day_at_the_gate(student, present_day):
    report = build_daily_presence(student, TODAY)

    assert report["date"] == TODAY.isoformat()
    assert report["was_present"] is True
    assert report["first_in"] == "08:24"
    assert report["last_out"] == "13:40"
    # They stepped out at 11:00 and came back at 11:30.
    assert report["first_out"] == "11:00"
    assert report["last_in"] == "11:30"
    assert report["entries"] == 2
    assert report["exits"] == 2
    assert report["is_inside"] is False


def test_daily_report_splits_the_day_into_visits(student, present_day):
    report = build_daily_presence(student, TODAY)

    assert [(visit["in"], visit["out"]) for visit in report["visits"]] == [
        ("08:24", "11:00"),
        ("11:30", "13:40"),
    ]
    # 08:24→11:00 is 156 minutes, 11:30→13:40 is 130.
    assert report["inside_minutes"] == 286
    assert report["outside_minutes"] == 30


def test_daily_report_lists_every_raw_pass(student, present_day):
    report = build_daily_presence(student, TODAY)
    assert [item["time"] for item in report["passes"]] == ["08:24", "11:00", "11:30", "13:40"]
    assert [item["direction"] for item in report["passes"]] == ["IN", "OUT", "IN", "OUT"]


def test_a_day_with_no_passes_is_absent(student):
    yesterday = TODAY - timedelta(days=1)
    report = build_daily_presence(student, yesterday)

    assert report["was_present"] is False
    assert report["entries"] == 0
    assert report["inside_minutes"] == 0
    assert report["state"] in {"ABSENT", "WEEKEND", "HOLIDAY"}


def test_a_closed_weekday_is_a_weekend_not_an_absence(student):
    report = build_daily_presence(student, _sunday_after(TODAY))
    assert report["state"] == "WEEKEND"
    assert report["is_school_day"] is False
    assert report["summary"]["school_days"] == 0


def test_a_holiday_never_counts_against_the_pupil(student, school, academic_year):
    from apps.schools.models import Holiday

    Holiday.objects.create(
        school=school, academic_year=academic_year, date=TODAY, name="Mustaqillik kuni"
    )
    report = build_daily_presence(student, TODAY)

    assert report["state"] == "HOLIDAY"
    assert report["holiday"] == "Mustaqillik kuni"
    assert report["summary"]["school_days"] == 0


def test_arriving_after_the_school_day_starts_is_late(student, person, terminal):
    from apps.integrations.models import TerminalEvent
    from apps.integrations.services.presence import rebuild_daily_presence
    from tests.conftest import at, pass_through

    event = pass_through(terminal, "S1001", at(9, 10), serial=700)
    TerminalEvent.objects.filter(pk=event.pk).update(student=student)
    rebuild_daily_presence(student, TODAY)

    report = build_daily_presence(student, TODAY)
    # The school day starts 08:10, and a minute past it is already late.
    assert report["late_minutes"] == 60
    assert report["state"] == "LATE"


def test_daily_endpoint_matches_the_service(auth_client, student, present_day):
    response = auth_client.get(
        reverse("attendance-daily", args=[student.id]), {"date": TODAY.isoformat()}
    )
    assert response.status_code == 200
    assert response.data["summary"] == build_daily_presence(student, TODAY)["summary"]
    assert response.data["first_in"] == "08:24"


# --------------------------------------------------------------------------- #
# Weekly / monthly / yearly
# --------------------------------------------------------------------------- #
def test_weekly_report_covers_monday_to_sunday(student, present_day):
    report = build_weekly_presence(student, TODAY)

    assert len(report["days"]) == 7
    marked = next(day for day in report["days"] if day["date"] == TODAY.isoformat())
    assert marked["inside_minutes"] == 286
    assert report["summary"]["days_present"] == 1
    assert report["summary"]["inside_minutes"] == 286


def test_weekly_totals_ignore_the_days_the_school_is_shut(student, present_day):
    report = build_weekly_presence(student, TODAY)
    school_days = [day for day in report["days"] if day["is_school_day"]]
    assert report["summary"]["school_days"] == len(school_days)
    assert all(day["state"] != "WEEKEND" for day in school_days)


def test_monthly_report_returns_a_full_calendar_grid(student, present_day):
    report = build_monthly_presence(student, TODAY.year, TODAY.month)

    assert report["month"] == TODAY.month
    assert len(report["days"]) % 7 == 0  # Monday-aligned grid
    marked = next(day for day in report["days"] if day["date"] == TODAY.isoformat())
    assert marked["in_month"] is True
    assert marked["was_present"] is True
    assert report["summary"]["days_present"] == 1


def test_yearly_report_breaks_down_by_month(student, present_day, academic_year):
    report = build_yearly_presence(student, academic_year)

    assert report["academic_year"] == academic_year.name
    current = next(
        month
        for month in report["months"]
        if month["year"] == TODAY.year and month["month"] == TODAY.month
    )
    assert current["summary"]["days_present"] == 1
    assert report["summary"]["days_present"] == 1


def test_reports_agree_with_each_other(student, present_day):
    daily = build_daily_presence(student, TODAY)["summary"]
    weekly = build_weekly_presence(student, TODAY)["summary"]
    monthly = build_monthly_presence(student, TODAY.year, TODAY.month)["summary"]

    # The same day is counted once, whichever period asks for it.
    assert daily["days_present"] == 1
    assert weekly["days_present"] == monthly["days_present"] == 1
    assert weekly["inside_minutes"] == monthly["inside_minutes"] == daily["inside_minutes"]


def test_a_pupil_still_inside_has_an_open_visit(student, person, terminal):
    from apps.integrations.models import TerminalEvent
    from apps.integrations.services.presence import rebuild_daily_presence
    from tests.conftest import at, pass_through

    event = pass_through(terminal, "S1001", at(8, 25), serial=710)
    TerminalEvent.objects.filter(pk=event.pk).update(student=student)
    rebuild_daily_presence(student, TODAY)

    report = build_daily_presence(student, TODAY)
    assert report["is_inside"] is True
    assert report["last_out"] is None
    assert report["visits"][-1]["open"] is True


# --------------------------------------------------------------------------- #
# Absence reasons
# --------------------------------------------------------------------------- #
def test_parent_submits_a_reason(auth_client, student, reason):
    response = auth_client.post(
        reverse("child-absence-requests", args=[student.id]),
        {"date": TODAY.isoformat(), "reason": str(reason.id), "comment": "Shifokorda edi"},
        format="json",
    )
    assert response.status_code == 201
    assert response.data["status"] == AbsenceRequestStatus.PENDING
    assert response.data["reason_name"] == "Kasallik"


def test_only_one_pending_request_per_day(auth_client, student, reason):
    payload = {"date": TODAY.isoformat(), "reason": str(reason.id)}
    url = reverse("child-absence-requests", args=[student.id])
    assert auth_client.post(url, payload, format="json").status_code == 201
    duplicate = auth_client.post(url, payload, format="json")
    assert duplicate.status_code == 409
    assert duplicate.data["error"]["code"] == "ABSENCE_REQUEST_PENDING"


def test_approval_records_the_reviewer(student, reason, parent_user, teacher_user):
    request = submit_absence_request(
        student=student, day=TODAY, reason=reason, submitted_by=parent_user
    )
    approve_absence_request(request, reviewer=teacher_user, comment="Ma'lumotnoma keltirildi")

    request.refresh_from_db()
    assert request.status == AbsenceRequestStatus.APPROVED
    assert request.reviewed_by == teacher_user
    assert request.review_comment == "Ma'lumotnoma keltirildi"


def test_rejection_is_recorded(student, reason, parent_user, teacher_user):
    request = submit_absence_request(
        student=student, day=TODAY, reason=reason, submitted_by=parent_user
    )
    reject_absence_request(request, reviewer=teacher_user, comment="Hujjat yo'q")

    request.refresh_from_db()
    assert request.status == AbsenceRequestStatus.REJECTED


def test_a_request_cannot_be_reviewed_twice(student, reason, parent_user, teacher_user):
    from apps.common.exceptions import ConflictError

    request = submit_absence_request(
        student=student, day=TODAY, reason=reason, submitted_by=parent_user
    )
    approve_absence_request(request, reviewer=teacher_user)
    with pytest.raises(ConflictError):
        reject_absence_request(request, reviewer=teacher_user)


def test_approval_is_audited(student, reason, parent_user, teacher_user):
    from apps.audit.constants import AuditAction
    from apps.audit.models import AuditLog

    request = submit_absence_request(
        student=student, day=TODAY, reason=reason, submitted_by=parent_user
    )
    approve_absence_request(request, reviewer=teacher_user)
    assert AuditLog.objects.filter(action=AuditAction.ABSENCE_REASON_APPROVE).exists()


# --------------------------------------------------------------------------- #
# Dashboard
# --------------------------------------------------------------------------- #
def test_dashboard_returns_everything_in_one_request(auth_client, student, present_day):
    response = auth_client.get(reverse("child-dashboard", args=[student.id]))
    assert response.status_code == 200
    data = response.data

    assert set(data) >= {
        "student",
        "today",
        "current_month",
        "recent_days",
        "notifications_count",
    }
    assert data["student"]["class_group"] == "7-A"
    assert data["today"]["first_in"] == "08:24"
    assert data["today"]["inside_minutes"] == 286
    assert data["current_month"]["summary"]["days_present"] == 1
