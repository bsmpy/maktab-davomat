"""What a teacher's and a curator's home screen show beyond their own day.

The rule is the same for both: nothing about anybody the person is not
responsible for. A teacher sees the lessons the timetable puts *them* in front
of today — not the class's whole day, not every subject they carry. A curator
sees the groups they were given — not the school.
"""
from __future__ import annotations

from datetime import date as date_type

from django.db.models import Count


def _is_school_day(school, day: date_type) -> bool:
    from .. import selectors

    holiday = selectors.holiday_map(school.id, day, day).get(day)
    if holiday is not None and not holiday.is_working_day:
        return False
    return school.is_working_weekday(day.isoweekday())


def lessons_today(teacher, day: date_type) -> list[dict]:
    """The lessons this teacher must give on ``day``, in bell order.

    Strictly the timetable rows that name this teacher. There is no fallback to
    "every subject they carry" the way the marking page has one: a day with no
    lessons is an empty list, and the page says so.
    """
    from apps.attendance.models import Lesson, Schedule
    from apps.students.models import Student

    if not _is_school_day(teacher.school, day):
        return []

    entries = [
        entry
        for entry in Schedule.objects.filter(
            teacher=teacher, weekday=day.isoweekday(), is_active=True
        )
        .select_related("subject", "class_group", "class_group__grade")
        .order_by("start_time", "lesson_number")
        if entry.covers(day)
    ]
    if not entries:
        return []

    group_ids = {entry.class_group_id for entry in entries}
    sizes = dict(
        Student.objects.active()
        .filter(class_group_id__in=group_ids)
        .values_list("class_group_id")
        .annotate(total=Count("id"))
    )
    marked = {
        (subject_id, number): total
        for subject_id, number, total in Lesson.objects.filter(
            subject_id__in={entry.subject_id for entry in entries}, date=day
        )
        .values_list("subject_id", "lesson_number")
        .annotate(total=Count("attendances"))
    }

    return [
        {
            "id": str(entry.id),
            "subject": str(entry.subject_id),
            "subject_name": entry.subject.name,
            "class_group": str(entry.class_group_id),
            "class_group_name": entry.class_group.display_name,
            "lesson_number": entry.lesson_number,
            "start_time": entry.start_time.strftime("%H:%M"),
            "end_time": entry.end_time.strftime("%H:%M"),
            "room": entry.room,
            "students_count": sizes.get(entry.class_group_id, 0),
            "marked_count": marked.get((entry.subject_id, entry.lesson_number), 0),
        }
        for entry in entries
    ]


def curator_groups_today(user, day: date_type) -> list[dict]:
    """Today's figures for each group this curator was put in charge of — and no other."""
    from apps.accounts.rbac import curator_group_ids
    from apps.schools.models import ClassGroup
    from apps.schools.services.overview import lesson_marks, pupils_today
    from apps.students.models import Student

    groups = (
        ClassGroup.objects.filter(id__in=curator_group_ids(user))
        .select_related("grade")
        .order_by("grade__level", "name")
    )
    rows = []
    for group in groups:
        students = Student.objects.active().filter(class_group=group)
        rows.append(
            {
                "id": str(group.id),
                "display_name": group.display_name,
                "grade_level": group.grade.level,
                "pupils": pupils_today(students, day),
                "lessons": lesson_marks(students, day),
            }
        )
    return rows
