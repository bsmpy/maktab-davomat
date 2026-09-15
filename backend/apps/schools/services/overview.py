"""The numbers an administrator's home screen opens on.

One query set per figure, computed on demand: the register is small enough that
a stored summary would be a cache to invalidate rather than a saving.
"""
from __future__ import annotations

from datetime import date as date_type

from django.db.models import Avg, Count, Q
from django.utils import timezone


def pupils_today(students, day: date_type) -> dict:
    """Who of ``students`` came through the gate on ``day``, and how.

    Shared by the school's home screen and a curator's: the same questions over
    a different set of pupils.
    """
    from apps.integrations.models import DailyPresence

    presence = DailyPresence.objects.filter(student__in=students, date=day)
    counts = presence.aggregate(
        arrived=Count("id", filter=Q(first_in_at__isnull=False)),
        inside=Count("id", filter=Q(is_inside=True)),
        late=Count("id", filter=Q(late_minutes__gt=0, arrived_too_late=False)),
    )
    total = students.count()
    arrived = counts["arrived"] or 0

    # The averages describe the people they are about: time inside is averaged
    # over those who came, lateness over those who were late. A register full of
    # zeroes for everyone who stayed home would drag both towards nothing.
    came = presence.filter(first_in_at__isnull=False)
    were_late = presence.filter(late_minutes__gt=0, arrived_too_late=False)
    averages = came.aggregate(
        active=Avg("inside_minutes"),
        inactive=Avg("outside_minutes"),
    )
    late_average = were_late.aggregate(late=Avg("late_minutes"))["late"]

    return {
        "total": total,
        "arrived": arrived,
        "absent": max(total - arrived, 0),
        "inside": counts["inside"] or 0,
        "late": counts["late"] or 0,
        # Attendance percentage of the register, not of those who were marked.
        "rate": round(arrived / total * 100, 1) if total else 0.0,
        "avg_active_minutes": round(averages["active"] or 0),
        "avg_inactive_minutes": round(averages["inactive"] or 0),
        "avg_late_minutes": round(late_average or 0),
    }


def lesson_marks(students, day: date_type) -> dict:
    """The lesson register for ``students`` on ``day``: marks, absences, excuses."""
    from apps.attendance.constants import AttendanceStatus
    from apps.attendance.models import Attendance

    marks = Attendance.objects.filter(student__in=students, date=day).aggregate(
        marked=Count("id"),
        absent=Count("id", filter=Q(status=AttendanceStatus.ABSENT)),
        excused=Count("id", filter=Q(status=AttendanceStatus.EXCUSED)),
    )
    return {
        "marked": marks["marked"] or 0,
        "absent": marks["absent"] or 0,
        "excused": marks["excused"] or 0,
    }


def school_overview(school, day: date_type | None = None) -> dict:
    """Register size, today at the gate, and the state of the devices.

    The home screen reads the two halves of the school the same way — the
    teachers and the pupils each get who came, who was late, who did not come
    and who is inside right now, and the same three averages beside them. The
    figures come from different places (pupils have a stored daily row,
    teachers are paired from the raw passes), but they answer the same
    questions and are shaped alike here so the screen can lay them out as one.
    """
    from apps.attendance.models import Schedule
    from apps.attendance.services.teacher_presence import school_day_totals
    from apps.guardians.models import Guardian
    from apps.integrations.models import Terminal
    from apps.students.models import Student

    from ..models import ClassGroup, Position, StaffMember, Subject, Teacher

    day = day or timezone.localdate()

    students = Student.objects.active().filter(school=school)
    total = students.count()
    students_today = pupils_today(students, day)
    teachers_today = school_day_totals(school, day)

    from apps.integrations.constants import IntegrationStatus

    terminals = Terminal.objects.filter(school=school, is_active=True)
    return {
        "date": day.isoformat(),
        "register": {
            "students": total,
            "teachers": Teacher.objects.filter(school=school, is_active=True).count(),
            "staff": StaffMember.objects.filter(school=school, is_active=True).count(),
            "positions": Position.objects.filter(school=school).count(),
            "class_groups": ClassGroup.objects.filter(school=school, is_active=True).count(),
            "subjects": Subject.objects.filter(school=school, is_active=True).count(),
            "guardians": Guardian.objects.filter(school=school).count(),
            "lessons_scheduled": Schedule.objects.filter(
                class_group__school=school, is_active=True
            ).count(),
        },
        #: Kept for the screens that already read it; ``students_today`` is the
        #: same figures under the name that says whose they are.
        "today": students_today,
        "students_today": students_today,
        "teachers_today": teachers_today,
        "lessons": lesson_marks(students, day),
        "terminals": {
            "total": terminals.count(),
            "online": terminals.filter(status=IntegrationStatus.OK).count(),
            "offline": terminals.exclude(status=IntegrationStatus.OK).count(),
        },
    }
