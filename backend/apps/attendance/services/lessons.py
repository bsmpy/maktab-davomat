"""Lesson attendance — the part a teacher fills in by hand.

The turnstile answers *was the pupil at school*; only the person standing in
front of the class can answer *was the pupil in this lesson*. So this module
owns the second question and nothing else.

A subject already carries its class group ("Matematika 1-A"), which makes the
roster obvious: everyone in that group. The teacher opens the card, marks the
row and the mark lands on a :class:`~apps.attendance.models.Lesson` for that
subject and that date — created on demand, because the schools here do not keep
a timetable and should not have to build one before they can mark a register.
"""
from __future__ import annotations

from datetime import date as date_type
from datetime import datetime, time, timedelta

from django.db import transaction
from django.db.models import Count
from django.utils import timezone

from apps.accounts.constants import Role
from apps.common.exceptions import AppError, ConflictError, NotFoundError
from apps.common.media import absolute_media_url
from apps.schools.models import ClassGroup, Subject
from apps.schools.services.management import accessible_schools, current_academic_year
from apps.students.models import Student

from ..constants import MISSED_STATUSES, AttendanceSource, AttendanceStatus
from ..models import MAX_LESSON_NUMBER, Attendance, Lesson, Schedule
from .timetable import (
    assert_marking_open,
    entries_for,
    entry_payload,
    marking_opens_at,
    schedule_state,
)

#: The first slot of the day, and how long one lesson runs. Only used to give a
#: generated lesson a plausible time; nothing in the marking flow reads them.
DEFAULT_FIRST_LESSON = time(8, 30)
LESSON_MINUTES = 45

#: Marking a lesson that has not happened yet is always a mistake.
FUTURE_ERROR = "Kelajakdagi kun uchun davomat qo'yib bo'lmaydi."


# --------------------------------------------------------------------------- #
# Who may mark what
# --------------------------------------------------------------------------- #
def teacher_of(user):
    return getattr(user, "teacher_profile", None)


def visible_subjects(user):
    """Subjects whose register this user may open.

    A teacher sees exactly the subjects attached to them — Rasulov opens
    Matematika 1-A and nothing else. An administrator sees the whole school,
    because somebody has to be able to fix a mark when a teacher is away, and a
    MODERATOR sees the same list read-only. A curator sees the subjects of the
    groups they were given: they are watching those classes, so the register of
    those classes is theirs to read — the *marking* is refused at the endpoint,
    which is where the write permission is checked.
    """
    queryset = (
        Subject.objects.filter(class_group__isnull=False)
        .select_related("class_group", "class_group__grade", "school")
        .order_by("class_group__grade__level", "class_group__name", "name")
    )
    if user.role in Role.admin_roles():
        return queryset.filter(school__in=accessible_schools(user))

    if user.role == Role.CURATOR:
        from apps.accounts.rbac import curator_group_ids

        return queryset.filter(class_group_id__in=curator_group_ids(user))

    teacher = teacher_of(user)
    if teacher is None:
        return queryset.none()
    return queryset.filter(teachers=teacher)


def get_subject_for(user, subject_id) -> Subject:
    subject = visible_subjects(user).filter(pk=subject_id).first()
    if subject is None:
        raise NotFoundError("Fan topilmadi.", code="SUBJECT_NOT_FOUND")
    return subject


# --------------------------------------------------------------------------- #
# The lesson a mark hangs on
# --------------------------------------------------------------------------- #
def _lesson_times(lesson_number: int) -> tuple[time, time]:
    start = datetime.combine(date_type.today(), DEFAULT_FIRST_LESSON) + timedelta(
        minutes=LESSON_MINUTES * (lesson_number - 1)
    )
    return start.time(), (start + timedelta(minutes=LESSON_MINUTES)).time()


def _next_lesson_number(class_group, day: date_type) -> int:
    taken = set(
        Lesson.objects.filter(class_group=class_group, date=day).values_list(
            "lesson_number", flat=True
        )
    )
    for number in range(1, MAX_LESSON_NUMBER + 1):
        if number not in taken:
            return number
    raise ConflictError(
        f"Bu sinf uchun bir kunda {MAX_LESSON_NUMBER} tadan ortiq dars bo'lmaydi.",
        code="TOO_MANY_LESSONS",
    )


def ensure_lesson(subject: Subject, day: date_type, *, create: bool = True) -> Lesson | None:
    """The lesson row for this subject on this day, made on first use."""
    lesson = (
        Lesson.objects.filter(subject=subject, class_group=subject.class_group, date=day)
        .order_by("lesson_number")
        .first()
    )
    if lesson is not None or not create:
        return lesson

    year = current_academic_year(subject.school)
    if year is None:
        raise ConflictError(
            "Avval o'quv yilini yarating: Boshqaruv → O'quv yili.",
            code="ACADEMIC_YEAR_MISSING",
        )
    number = _next_lesson_number(subject.class_group, day)
    start, end = _lesson_times(number)
    return Lesson.objects.create(
        academic_year=year,
        class_group=subject.class_group,
        subject=subject,
        teacher=subject.teachers.first(),
        date=day,
        lesson_number=number,
        start_time=start,
        end_time=end,
    )


# --------------------------------------------------------------------------- #
# Reading the register
# --------------------------------------------------------------------------- #
def subject_card(subject: Subject, day: date_type, marks: dict[str, int]) -> dict:
    group = subject.class_group
    return {
        "id": str(subject.id),
        "name": subject.name,
        "display_name": subject.display_name,
        "class_group": str(group.id),
        "class_group_name": group.display_name,
        "grade_level": group.grade.level,
        "students_count": marks.get("students", 0),
        "marked_count": marks.get("marked", 0),
        "teachers": [teacher.full_name for teacher in subject.teachers.all()],
    }


def subject_cards(user, day: date_type) -> list[dict]:
    """One card per subject, each carrying how much of the day is already done."""
    subjects = list(visible_subjects(user).prefetch_related("teachers"))
    if not subjects:
        return []

    group_ids = {subject.class_group_id for subject in subjects}
    sizes = dict(
        Student.objects.active()
        .filter(class_group_id__in=group_ids)
        .values_list("class_group_id")
        .annotate(total=Count("id"))
    )
    # How much of today is already filled in, per subject.
    marked = dict(
        Lesson.objects.filter(subject__in=subjects, date=day)
        .values_list("subject_id")
        .annotate(total=Count("attendances"))
    )

    return [
        subject_card(
            subject,
            day,
            {
                "students": sizes.get(subject.class_group_id, 0),
                "marked": marked.get(subject.id, 0),
            },
        )
        for subject in subjects
    ]


def _mark_payload(attendance: Attendance | None) -> dict:
    if attendance is None:
        return {"status": None, "status_label": "", "late_minutes": 0, "comment": ""}
    return {
        "status": attendance.status,
        "status_label": attendance.get_status_display(),
        "late_minutes": attendance.late_minutes,
        "comment": attendance.comment,
    }


def roster(subject: Subject, day: date_type) -> dict:
    """Everyone in the class group, with whatever mark they already carry."""
    lesson = ensure_lesson(subject, day, create=False)
    marks = (
        {row.student_id: row for row in Attendance.objects.filter(lesson=lesson)}
        if lesson is not None
        else {}
    )
    students = (
        Student.objects.active()
        .for_class_group(subject.class_group_id)
        .order_by("last_name", "first_name")
    )
    opens = marking_opens_at(subject, day)
    return {
        "subject": subject_card(
            subject,
            day,
            {"students": students.count(), "marked": len(marks)},
        ),
        "date": day.isoformat(),
        # The register only opens once the lesson has started: before that
        # nothing has happened to record.
        "can_mark": opens is None and day <= timezone.localdate(),
        "opens_at": timezone.localtime(opens).strftime("%H:%M") if opens else None,
        "students": [
            {
                "id": str(student.id),
                "full_name": student.full_name,
                "display_name": student.display_name,
                "initials": student.initials,
                "photo": absolute_media_url(student.photo),
                **_mark_payload(marks.get(student.id)),
            }
            for student in students
        ],
    }


# --------------------------------------------------------------------------- #
# Writing the register
# --------------------------------------------------------------------------- #
def _clean_mark(entry: dict) -> dict:
    """One row of the form, checked against what each status needs."""
    status = entry.get("status")
    late_minutes = int(entry.get("late_minutes") or 0)
    comment = (entry.get("comment") or "").strip()

    if status == AttendanceStatus.LATE and late_minutes < 1:
        raise AppError(
            "Necha daqiqa kechikkanini kiriting.",
            code="LATE_MINUTES_REQUIRED",
            fields={"late_minutes": ["Necha daqiqa kechikkanini kiriting."]},
        )
    if status == AttendanceStatus.EXCUSED and not comment:
        raise AppError(
            "Sababini yozing.",
            code="REASON_REQUIRED",
            fields={"comment": ["Sababini yozing."]},
        )
    if status not in MISSED_STATUSES:
        # A reason belongs to an absence; keep it off a present pupil's row.
        comment = ""
    return {
        "status": status,
        "late_minutes": late_minutes if status == AttendanceStatus.LATE else 0,
        "comment": comment,
    }


@transaction.atomic
def save_marks(subject: Subject, day: date_type, entries: list[dict], *, user) -> dict:
    """Upsert one mark per pupil. Sending no status clears the row."""
    if day > timezone.localdate():
        raise ConflictError(FUTURE_ERROR, code="FUTURE_DATE")
    assert_marking_open(subject, day)

    allowed = set(
        Student.objects.active()
        .for_class_group(subject.class_group_id)
        .values_list("id", flat=True)
    )
    lesson = ensure_lesson(subject, day)

    for entry in entries:
        student_id = entry.get("student")
        if student_id not in allowed:
            raise NotFoundError("O'quvchi bu sinfda emas.", code="STUDENT_NOT_IN_GROUP")

        if not entry.get("status"):
            Attendance.objects.filter(lesson=lesson, student_id=student_id).delete()
            continue

        Attendance.objects.update_or_create(
            lesson=lesson,
            student_id=student_id,
            defaults={
                **_clean_mark(entry),
                "source": AttendanceSource.MANUAL,
                "marked_by": user,
                "marked_at": timezone.now(),
            },
        )
    return roster(subject, day)


# --------------------------------------------------------------------------- #
# The teacher's cabinet: classes first, subjects inside them
# --------------------------------------------------------------------------- #
def _lesson_open(entry, day: date_type, now) -> bool:
    """A timetabled lesson can be marked from its start time onwards."""
    if day > now.date():
        return False
    if day < now.date():
        return True
    return now >= timezone.make_aware(datetime.combine(day, entry.start_time))


def class_cards(user, day: date_type) -> list[dict]:
    """The classes this user teaches, each flagged today / tomorrow / neither.

    A teacher thinks in classes — "am I in 1-A this morning?" — so the cabinet
    opens on those rather than on a flat list of subjects.
    """
    subjects = list(visible_subjects(user).prefetch_related("teachers"))
    if not subjects:
        return []

    by_group: dict = {}
    for subject in subjects:
        by_group.setdefault(subject.class_group_id, []).append(subject)

    sizes = dict(
        Student.objects.active()
        .filter(class_group_id__in=by_group)
        .values_list("class_group_id")
        .annotate(total=Count("id"))
    )
    # Which weekdays each class has one of *these* subjects on.
    weekdays: dict = {}
    for group_id, subject_id, weekday in Schedule.objects.filter(
        subject__in=subjects, is_active=True
    ).values_list("class_group_id", "subject_id", "weekday"):
        del subject_id
        weekdays.setdefault(group_id, set()).add(weekday)

    marked = dict(
        Lesson.objects.filter(subject__in=subjects, date=day)
        .values_list("class_group_id")
        .annotate(total=Count("attendances"))
    )

    cards = []
    for group_id, group_subjects in by_group.items():
        group = group_subjects[0].class_group
        cards.append(
            {
                "id": str(group.id),
                "display_name": group.display_name,
                "grade_level": group.grade.level,
                "students_count": sizes.get(group_id, 0),
                "marked_count": marked.get(group_id, 0),
                "schedule_state": schedule_state(weekdays.get(group_id, set()), day),
                "subjects": [
                    {
                        "id": str(subject.id),
                        "name": subject.name,
                        "display_name": subject.display_name,
                    }
                    for subject in group_subjects
                ],
            }
        )
    return sorted(cards, key=lambda card: (card["grade_level"], card["display_name"]))


def get_class_group_for(user, class_group_id) -> ClassGroup:
    """One class group, checked against the same scope the list uses.

    Deliberately ``accessible_class_groups`` rather than "groups I carry a
    subject in": a curator is given 7-A itself, and a class with no subjects
    entered yet is still their class. A group outside that scope is a 404, the
    same answer as one that does not exist.
    """
    from apps.accounts.rbac import get_accessible_group

    group = get_accessible_group(user, class_group_id)
    if group is None:
        raise NotFoundError("Sinf guruhi topilmadi.", code="CLASS_GROUP_NOT_FOUND")
    return group


def class_day(user, group: ClassGroup, day: date_type) -> dict:
    """One class on one day: the timetable, or every subject if there is none.

    The timetable is what an administrator uploads; until they do, the teacher
    still needs to be able to mark a register, so the fallback is simply their
    own subjects for that class with no times attached.
    """
    mine = {
        subject.id: subject
        for subject in visible_subjects(user).filter(class_group=group)
    }
    entries = list(entries_for(group, day.isoweekday()))
    students_count = Student.objects.active().for_class_group(group.id).count()
    marked = dict(
        Lesson.objects.filter(subject_id__in=mine, date=day)
        .values_list("subject_id")
        .annotate(total=Count("attendances"))
    )

    if entries:
        now = timezone.now()
        lessons = [
            {
                **entry_payload(entry),
                "is_mine": entry.subject_id in mine,
                "marked_count": marked.get(entry.subject_id, 0),
                "students_count": students_count,
                "can_mark": _lesson_open(entry, day, now),
            }
            for entry in entries
        ]
    else:
        lessons = [
            {
                "id": None,
                "lesson_number": index,
                "start_time": None,
                "end_time": None,
                "room": "",
                "subject": str(subject.id),
                "subject_name": subject.name,
                "subject_display": subject.display_name,
                "teacher": None,
                "teacher_name": "",
                "is_mine": True,
                "marked_count": marked.get(subject.id, 0),
                "students_count": students_count,
                # Nothing times it, so there is nothing to wait for.
                "can_mark": day <= timezone.localdate(),
            }
            for index, subject in enumerate(mine.values(), start=1)
        ]

    return {
        "class_group": {
            "id": str(group.id),
            "display_name": group.display_name,
            "grade_level": group.grade.level,
            "students_count": students_count,
        },
        "date": day.isoformat(),
        "weekday": day.isoweekday(),
        "has_timetable": bool(entries),
        "lessons": lessons,
    }
