"""Materialise concrete lessons from the recurring timetable.

Attendance always attaches to a ``Lesson`` row, so the timetable has to be
expanded into dates before a register can be marked. ``generate_lessons`` is
idempotent: re-running it for the same range creates nothing new.
"""
from __future__ import annotations

from datetime import date

from django.db import transaction

from apps.schools.models import Holiday

from ..models import Lesson, Schedule
from .periods import DateRange


def _school_days(school, span: DateRange, holidays: dict[date, Holiday]) -> list[date]:
    days = []
    for day in span:
        holiday = holidays.get(day)
        if holiday is not None:
            if holiday.is_working_day:
                days.append(day)
            continue
        if school.is_working_weekday(day.isoweekday()):
            days.append(day)
    return days


@transaction.atomic
def generate_lessons(*, academic_year, start: date, end: date, class_group=None) -> int:
    """Create missing lessons for the range. Returns the number created."""
    school = academic_year.school
    span = DateRange(start, end)
    holidays = {
        holiday.date: holiday
        for holiday in Holiday.objects.filter(
            school=school, date__gte=start, date__lte=end
        )
    }
    days = _school_days(school, span, holidays)
    if not days:
        return 0

    schedules = Schedule.objects.filter(
        academic_year=academic_year, is_active=True
    ).select_related("class_group", "subject", "teacher")
    if class_group is not None:
        schedules = schedules.filter(class_group=class_group)
    schedules = list(schedules)
    if not schedules:
        return 0

    existing = set(
        Lesson.objects.filter(
            class_group__in={schedule.class_group_id for schedule in schedules},
            date__gte=start,
            date__lte=end,
        ).values_list("class_group_id", "date", "lesson_number")
    )

    to_create: list[Lesson] = []
    for day in days:
        weekday = day.isoweekday()
        for schedule in schedules:
            if schedule.weekday != weekday or not schedule.covers(day):
                continue
            key = (schedule.class_group_id, day, schedule.lesson_number)
            if key in existing:
                continue
            existing.add(key)
            to_create.append(
                Lesson(
                    academic_year=academic_year,
                    schedule=schedule,
                    class_group=schedule.class_group,
                    subject=schedule.subject,
                    teacher=schedule.teacher,
                    date=day,
                    lesson_number=schedule.lesson_number,
                    start_time=schedule.start_time,
                    end_time=schedule.end_time,
                    room=schedule.room,
                )
            )

    if to_create:
        Lesson.objects.bulk_create(to_create, batch_size=1000, ignore_conflicts=True)
    return len(to_create)
