"""Dars jadvali — the weekly timetable an administrator fills in.

A row says "1-A has Matematika on Monday, 08:00–08:40". It is what turns the
teacher's cabinet from a flat list of subjects into a set of classes with a
today / tomorrow marker on each, and it is what tells the register which
lessons a day is supposed to contain.

The timetable is optional: a school that has not built one can still mark
attendance — the register then simply offers every subject of the class.
"""
from __future__ import annotations

from datetime import date as date_type
from datetime import datetime, timedelta

from django.db import transaction
from django.utils import timezone

from apps.common.exceptions import ConflictError, NotFoundError
from apps.schools.models import ClassGroup, Subject, Teacher
from apps.schools.services.management import current_academic_year

from ..models import MAX_LESSON_NUMBER, Schedule

#: Which of the two upcoming days a class is next seen on.
STATE_TODAY = "TODAY"
STATE_TOMORROW = "TOMORROW"
STATE_NONE = "NONE"


def _year_for(class_group: ClassGroup):
    year = current_academic_year(class_group.school)
    if year is None:
        raise ConflictError(
            "Avval o'quv yilini yarating: Boshqaruv → O'quv yili.",
            code="ACADEMIC_YEAR_MISSING",
        )
    return year


def entries_for(class_group: ClassGroup, weekday: int):
    return (
        Schedule.objects.filter(class_group=class_group, weekday=weekday, is_active=True)
        .select_related("subject", "subject__class_group", "teacher")
        .order_by("lesson_number", "start_time")
    )


def entry_payload(entry: Schedule) -> dict:
    return {
        "id": str(entry.id),
        "weekday": entry.weekday,
        "weekday_label": entry.get_weekday_display(),
        "lesson_number": entry.lesson_number,
        "start_time": entry.start_time.strftime("%H:%M"),
        "end_time": entry.end_time.strftime("%H:%M"),
        "room": entry.room,
        "subject": str(entry.subject_id),
        "subject_name": entry.subject.name,
        "subject_display": entry.subject.display_name,
        "teacher": str(entry.teacher_id) if entry.teacher_id else None,
        "teacher_name": entry.teacher.full_name if entry.teacher_id else "",
    }


def _next_lesson_number(class_group: ClassGroup, weekday: int, year) -> int:
    taken = set(
        Schedule.objects.filter(
            academic_year=year, class_group=class_group, weekday=weekday
        ).values_list("lesson_number", flat=True)
    )
    for number in range(1, MAX_LESSON_NUMBER + 1):
        if number not in taken:
            return number
    raise ConflictError(
        f"Bir kunda {MAX_LESSON_NUMBER} tadan ortiq dars bo'lmaydi.",
        code="TOO_MANY_LESSONS",
    )


def _resolve_subject(class_group: ClassGroup, subject_id) -> Subject:
    subject = Subject.objects.filter(pk=subject_id, class_group=class_group).first()
    if subject is None:
        raise NotFoundError(
            "Bu sinf guruhida bunday fan yo'q.", code="SUBJECT_NOT_IN_GROUP"
        )
    return subject


def _resolve_teacher(subject: Subject, teacher_id) -> Teacher | None:
    if teacher_id:
        teacher = subject.teachers.filter(pk=teacher_id).first()
        if teacher is None:
            raise NotFoundError(
                "Bu o'qituvchi shu fanga biriktirilmagan.", code="TEACHER_NOT_ON_SUBJECT"
            )
        return teacher
    # Nobody chosen: the subject usually has exactly one teacher anyway.
    return subject.teachers.first()


@transaction.atomic
def add_entry(class_group: ClassGroup, data: dict) -> Schedule:
    """Append one lesson to a weekday, keeping the slots in time order."""
    year = _year_for(class_group)
    subject = _resolve_subject(class_group, data["subject"])
    teacher = _resolve_teacher(subject, data.get("teacher"))
    weekday = data["weekday"]

    if data["end_time"] <= data["start_time"]:
        raise ConflictError(
            "Dars tugash vaqti boshlanish vaqtidan keyin bo'lishi kerak.",
            code="INVALID_TIME_RANGE",
        )
    overlap = entries_for(class_group, weekday).filter(
        start_time__lt=data["end_time"], end_time__gt=data["start_time"]
    )
    if overlap.exists():
        raise ConflictError(
            "Bu vaqtda shu sinfda boshqa dars bor.", code="LESSON_OVERLAP"
        )

    entry = Schedule.objects.create(
        academic_year=year,
        class_group=class_group,
        subject=subject,
        teacher=teacher,
        weekday=weekday,
        lesson_number=_next_lesson_number(class_group, weekday, year),
        start_time=data["start_time"],
        end_time=data["end_time"],
        room=data.get("room", ""),
    )
    renumber(class_group, weekday)
    entry.refresh_from_db()
    return entry


@transaction.atomic
def renumber(class_group: ClassGroup, weekday: int) -> None:
    """Lesson 1 is the earliest of the day, whatever order rows were added in."""
    entries = list(
        Schedule.objects.filter(class_group=class_group, weekday=weekday).order_by(
            "start_time", "end_time"
        )
    )
    # Park them out of the way first: the slot is unique per (day, number), so
    # renumbering in place would collide with the rows not yet moved.
    for offset, entry in enumerate(entries, start=1):
        Schedule.objects.filter(pk=entry.pk).update(lesson_number=MAX_LESSON_NUMBER + offset)
    for number, entry in enumerate(entries, start=1):
        Schedule.objects.filter(pk=entry.pk).update(lesson_number=number)


@transaction.atomic
def remove_entry(entry: Schedule) -> None:
    class_group, weekday = entry.class_group, entry.weekday
    entry.delete()
    renumber(class_group, weekday)


def starts_at(subject, day: date_type) -> datetime | None:
    """When this subject's lesson begins on that day, per the timetable.

    ``None`` when the school has not timetabled it — there is then no start to
    measure against, and marking is open.
    """
    entry = (
        Schedule.objects.filter(
            class_group_id=subject.class_group_id,
            subject=subject,
            weekday=day.isoweekday(),
            is_active=True,
        )
        .order_by("start_time")
        .first()
    )
    if entry is None:
        return None
    return timezone.make_aware(datetime.combine(day, entry.start_time))


def marking_opens_at(subject, day: date_type) -> datetime | None:
    """The moment the register unlocks, or ``None`` if it is already open."""
    moment = starts_at(subject, day)
    if moment is None or timezone.now() >= moment:
        return None
    return moment


def assert_marking_open(subject, day: date_type) -> None:
    """A lesson that has not started cannot be marked — nothing has happened yet."""
    opens = marking_opens_at(subject, day)
    if opens is None:
        return
    raise ConflictError(
        "Dars hali boshlanmadi. Davomatni "
        f"{timezone.localtime(opens):%H:%M} dan keyin belgilash mumkin.",
        code="LESSON_NOT_STARTED",
    )


# --------------------------------------------------------------------------- #
# Today / tomorrow, as the teacher's cabinet shows it
# --------------------------------------------------------------------------- #
def schedule_state(weekdays: set[int], day: date_type) -> str:
    """Green for today, amber for tomorrow, grey for anything further away."""
    if day.isoweekday() in weekdays:
        return STATE_TODAY
    if (day + timedelta(days=1)).isoweekday() in weekdays:
        return STATE_TOMORROW
    return STATE_NONE
