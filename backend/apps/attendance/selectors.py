"""Query helpers shared by the report builders and the API layer.

Keeping the querysets here is what keeps N+1s out: every consumer gets a
queryset that already carries the joins it needs.
"""
from __future__ import annotations

from datetime import date

from django.db.models import Prefetch, QuerySet

from apps.schools.models import AcademicYear, Holiday

from .models import Attendance, Lesson


def lessons_for_student(student, start: date, end: date) -> QuerySet[Lesson]:
    return (
        Lesson.objects.filter(
            class_group_id=student.class_group_id, date__gte=start, date__lte=end
        )
        .with_details()
        .order_by("date", "lesson_number")
    )


def attendance_for_student(student, start: date, end: date) -> QuerySet[Attendance]:
    return (
        Attendance.objects.filter(student=student, date__gte=start, date__lte=end)
        .counted()
        .with_details()
    )


def attendance_map(student, start: date, end: date) -> dict:
    """``{lesson_id: Attendance}`` for the period, in one query."""
    return {
        row.lesson_id: row
        for row in attendance_for_student(student, start, end)
    }


def current_academic_year(school_id) -> AcademicYear | None:
    return (
        AcademicYear.objects.filter(school_id=school_id, is_current=True).first()
        or AcademicYear.objects.filter(school_id=school_id).order_by("-start_date").first()
    )


def academic_year_for_date(school_id, day: date) -> AcademicYear | None:
    return (
        AcademicYear.objects.filter(
            school_id=school_id, start_date__lte=day, end_date__gte=day
        ).first()
        or current_academic_year(school_id)
    )


def holiday_map(school_id, start: date, end: date) -> dict[date, Holiday]:
    return {
        holiday.date: holiday
        for holiday in Holiday.objects.filter(
            school_id=school_id, date__gte=start, date__lte=end
        )
    }


def absence_requests_for(student, start: date, end: date):
    from .models import AbsenceRequest

    return (
        AbsenceRequest.objects.filter(student=student, date__gte=start, date__lte=end)
        .select_related("reason", "submitted_by", "reviewed_by")
        .prefetch_related(Prefetch("lessons", queryset=Lesson.objects.only("id")))
        .order_by("-date")
    )
