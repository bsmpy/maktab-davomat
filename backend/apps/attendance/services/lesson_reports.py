"""What a parent sees under "Dars davomati".

The gate reports tell a parent their child was at school; this one tells them
what happened lesson by lesson — came, did not come, came late, and with what
reason. It reads the marks a teacher entered and nothing else: a lesson nobody
marked simply does not appear.
"""
from __future__ import annotations

from datetime import date

from ..constants import AttendanceStatus
from ..models import Attendance
from .periods import today


def _row(attendance: Attendance) -> dict:
    lesson = attendance.lesson
    subject = lesson.subject
    teacher = lesson.teacher
    return {
        "id": str(attendance.id),
        "date": attendance.date.isoformat(),
        "lesson_number": lesson.lesson_number,
        "subject": subject.name,
        "subject_display": subject.display_name,
        "subject_id": str(subject.id),
        "teacher": teacher.full_name if teacher else "",
        "status": attendance.status,
        "status_label": attendance.get_status_display(),
        "late_minutes": attendance.late_minutes,
        "comment": attendance.comment,
        "is_canceled": lesson.is_canceled,
    }


def _blank_totals() -> dict:
    return {
        "lessons": 0,
        "present": 0,
        "late": 0,
        "absent": 0,
        "excused": 0,
        "attended": 0,
        "rate": 0.0,
    }


def _count(totals: dict, status: str) -> None:
    totals["lessons"] += 1
    if status == AttendanceStatus.PRESENT:
        totals["present"] += 1
    elif status == AttendanceStatus.LATE:
        totals["late"] += 1
    elif status == AttendanceStatus.EXCUSED:
        totals["excused"] += 1
    else:
        totals["absent"] += 1


def _finish(totals: dict) -> dict:
    totals["attended"] = totals["present"] + totals["late"]
    totals["rate"] = (
        round(totals["attended"] / totals["lessons"] * 100, 1) if totals["lessons"] else 0.0
    )
    return totals


def build_lesson_attendance(
    student, start: date, end: date, *, include_days: bool = True
) -> dict:
    """Marks for a range, summed overall, per subject and (optionally) per day.

    ``include_days`` is what keeps a whole-year request small: the yearly view
    only ever renders the per-subject table.
    """
    rows = [
        _row(attendance)
        for attendance in (
            Attendance.objects.for_student(student.id)
            .in_range(start, end)
            .counted()
            .with_details()
            .select_related("lesson__subject__class_group__grade")
            .order_by("date", "lesson__lesson_number")
        )
    ]

    summary = _blank_totals()
    per_subject: dict[str, dict] = {}
    per_day: dict[str, list[dict]] = {}

    for row in rows:
        _count(summary, row["status"])
        subject = per_subject.setdefault(
            row["subject_id"],
            {
                "id": row["subject_id"],
                "name": row["subject"],
                "display_name": row["subject_display"],
                "teacher": row["teacher"],
                **_blank_totals(),
            },
        )
        _count(subject, row["status"])
        if include_days:
            per_day.setdefault(row["date"], []).append(row)

    return {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "summary": _finish(summary),
        "subjects": [
            _finish(subject)
            for subject in sorted(per_subject.values(), key=lambda item: item["display_name"])
        ],
        "days": [
            {"date": day, "lessons": lessons} for day, lessons in sorted(per_day.items())
        ]
        if include_days
        else [],
        "today": today().isoformat(),
    }
