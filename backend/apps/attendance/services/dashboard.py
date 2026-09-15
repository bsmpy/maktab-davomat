"""One aggregated payload for the parent dashboard.

The home screen must not need ten round-trips: today's gate activity, the
month-to-date totals, the recent-days strip and the unread notification count
all arrive together.
"""
from __future__ import annotations

from datetime import date

from apps.common.media import absolute_media_url
from apps.notifications.models import Notification

from ..constants import AbsenceRequestStatus
from .periods import DateRange, month_range, today
from .presence_reports import build_daily_presence, build_day_rows, build_recent_presence
from .presence_stats import totals_from_rows


def student_card(student, *, relation: str | None = None) -> dict:
    from apps.guardians.constants import Relation

    return {
        "id": str(student.id),
        "first_name": student.first_name,
        "last_name": student.last_name,
        "middle_name": student.middle_name,
        "full_name": student.full_name,
        "display_name": student.display_name,
        "initials": student.initials,
        "photo": absolute_media_url(student.photo),
        "class_group": student.class_group.display_name,
        "class_group_id": str(student.class_group_id),
        "grade_level": student.class_group.grade.level,
        "school": student.school.short_name or student.school.name,
        "gender": student.gender,
        "relation": relation,
        "relation_label": dict(Relation.choices).get(relation) if relation else None,
    }


def build_dashboard(student, user, *, day: date | None = None) -> dict:
    day = day or today()
    month = month_range(day.year, day.month)

    daily = build_daily_presence(student, day)
    month_days = [
        row
        for row in build_day_rows(student, DateRange(month.start, month.end), reference=day)
        if row["is_school_day"]
    ]

    pending_requests = student.absence_requests.filter(
        status=AbsenceRequestStatus.PENDING
    ).count()

    return {
        "student": student_card(student),
        "today": {
            "date": day.isoformat(),
            "state": daily["state"],
            "was_present": daily["was_present"],
            "arrived_too_late": daily["arrived_too_late"],
            "arrived_at": daily["arrived_at"],
            "is_inside": daily["is_inside"],
            "first_in": daily["first_in"],
            "last_out": daily["last_out"],
            "entries": daily["entries"],
            "exits": daily["exits"],
            "inside_minutes": daily["inside_minutes"],
            "outside_minutes": daily["outside_minutes"],
            "late_minutes": daily["late_minutes"],
            "visits": daily["visits"],
            "passes": daily["passes"],
            "summary": daily["summary"],
        },
        "current_month": {
            "year": day.year,
            "month": day.month,
            "start_date": month.start.isoformat(),
            "end_date": month.end.isoformat(),
            "summary": totals_from_rows(month_days).to_dict(),
        },
        "recent_days": build_recent_presence(student),
        "notifications_count": Notification.objects.filter(user=user, is_read=False).count(),
        "pending_absence_requests": pending_requests,
    }
