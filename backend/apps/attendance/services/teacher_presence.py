"""A teacher's own presence at school, read from the turnstile.

The pupil pipeline stores a ``DailyPresence`` row per pupil per day because
those rows are read constantly and aggregated across a year. A teacher reads
their own week, and only their own, so this computes it on demand from the raw
passes instead of adding a second stored table to keep in sync.

The pairing itself is not re-implemented: :func:`build_visits` already knows how
to turn a stream of ins and outs into visits, including a pupil — or a teacher —
who is still inside.
"""
from __future__ import annotations

from datetime import date as date_type
from datetime import datetime, timedelta

from django.db.models import Count
from django.utils import timezone

from apps.common.media import absolute_media_url
from apps.integrations.constants import EventDirection, IntegrationKind
from apps.integrations.models import TerminalEvent
from apps.integrations.services.presence import (
    _debounce,
    build_visits,
    school_day_bounds,
)
from apps.integrations.services.registry import integration_config

from .periods import week_range

#: The band the day timeline covers — a working day fits inside it comfortably.
TIMELINE_START = 6
TIMELINE_END = 24


def _events(person, start: date_type, end: date_type) -> list[TerminalEvent]:
    """Every pass this person made in the window.

    ``person`` is a teacher *or* any other employee: both walk through the same
    turnstile and both have a column on the event, so the only difference is
    which one to filter on.
    """
    from apps.integrations.services.enrollment import person_field

    return list(
        TerminalEvent.objects.filter(
            date__gte=start, date__lte=end, **{person_field(person): person}
        )
        .select_related("terminal")
        .order_by("occurred_at")
    )


def _config(person) -> dict:
    return integration_config(IntegrationKind.TERMINALS, person.school)


def _clock(value: datetime | None) -> str | None:
    return timezone.localtime(value).strftime("%H:%M") if value else None


def day_report(teacher, day: date_type, *, config: dict | None = None) -> dict:
    """One day: the visits, the totals, and the first in / last out."""
    config = config if config is not None else _config(teacher)
    events = _debounce(_events(teacher, day, day), int(config.get("debounce_seconds", 60)))
    _day_start, day_end = school_day_bounds(config, day)
    visits, entries, exits, outside, is_inside = build_visits(
        events, day_end=day_end, now=timezone.now()
    )

    ins = [event for event in events if event.direction != EventDirection.OUT]
    outs = [event for event in events if event.direction == EventDirection.OUT]
    first_in = ins[0].occurred_at if ins else None
    last_out = outs[-1].occurred_at if outs else None

    return {
        "date": day.isoformat(),
        "visits": visits,
        "entries": entries,
        "exits": exits,
        "inside_minutes": sum(visit["minutes"] for visit in visits),
        "outside_minutes": outside,
        "is_inside": is_inside,
        "first_in": first_in,
        "last_out": last_out,
    }


def timeline(teacher, day: date_type) -> dict:
    """The day as a band of coloured segments, 06:00 to 00:00.

    Every stretch inside the school is one segment and every gap is another, so
    a teacher who steps out at noon and comes back shows two green blocks — not
    one long one from the first entry to the last exit.
    """
    report = day_report(teacher, day)
    band_start = timezone.make_aware(datetime.combine(day, datetime.min.time())) + timedelta(
        hours=TIMELINE_START
    )
    band_end = timezone.make_aware(datetime.combine(day, datetime.min.time())) + timedelta(
        hours=TIMELINE_END
    )
    span = (band_end - band_start).total_seconds()

    def position(moment: datetime) -> float:
        clamped = min(max(moment, band_start), band_end)
        return round((clamped - band_start).total_seconds() / span * 100, 4)

    segments: list[dict] = []
    cursor = band_start
    for visit in report["visits"]:
        started = datetime.fromisoformat(visit["in"])
        ended = (
            datetime.fromisoformat(visit["out"])
            if visit["out"]
            else min(timezone.now(), band_end)
        )
        if ended <= band_start or started >= band_end:
            continue
        if started > cursor:
            segments.append(_segment("OUT", cursor, started, position))
        segments.append(_segment("IN", max(started, band_start), ended, position))
        cursor = max(cursor, ended)

    if cursor < band_end:
        segments.append(_segment("OUT", cursor, band_end, position))

    return {
        "date": day.isoformat(),
        "start_hour": TIMELINE_START,
        "end_hour": TIMELINE_END,
        "segments": [segment for segment in segments if segment["width"] > 0],
        "first_in": _clock(report["first_in"]),
        "last_out": _clock(report["last_out"]) if not report["is_inside"] else None,
        "is_inside": report["is_inside"],
        "inside_minutes": report["inside_minutes"],
    }


def _segment(state: str, start: datetime, end: datetime, position) -> dict:
    left = position(start)
    right = position(end)
    return {
        "state": state,
        "start": _clock(start),
        "end": _clock(end),
        "minutes": max(int((end - start).total_seconds() // 60), 0),
        "left": left,
        "width": round(right - left, 4),
    }


def range_summary(person, start: date_type, end: date_type, *, config=None) -> dict:
    """One person's presence over any span: a week, a month, a whole year.

    The passes are fetched **once** and bucketed by date. A year read day by
    day would be 365 round trips for a screen that shows six numbers, which is
    why this exists rather than a loop over :func:`day_report`.

    "Out" is measured against the school's own working day, not against the
    clock — an evening at home is not absence — and a day the school was shut
    counts as neither present nor absent.
    """
    config = config if config is not None else _config(person)
    school = person.school
    today = timezone.localdate()
    grace = int(config.get("late_grace_minutes", 0))
    debounce = int(config.get("debounce_seconds", 60))
    now = timezone.now()

    by_day: dict[date_type, list] = {}
    for event in _events(person, start, end):
        by_day.setdefault(event.date, []).append(event)

    active = inactive = late_days = school_days = present_days = 0
    current = start
    while current <= end:
        if current > today or not school.is_working_weekday(current.isoweekday()):
            current += timedelta(days=1)
            continue

        school_days += 1
        day_start, day_end = school_day_bounds(config, current)
        working_minutes = max(int((day_end - day_start).total_seconds() // 60), 0)

        events = _debounce(by_day.get(current, []), debounce)
        visits, _entries, _exits, _outside, _inside = build_visits(
            events, day_end=day_end, now=now
        )
        inside = sum(visit["minutes"] for visit in visits)
        active += inside
        inactive += max(working_minutes - inside, 0)

        ins = [event for event in events if event.direction != EventDirection.OUT]
        if ins:
            present_days += 1
            if ins[0].occurred_at > day_start + timedelta(minutes=grace):
                late_days += 1

        current += timedelta(days=1)

    return {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "school_days": school_days,
        "days_present": present_days,
        "days_absent": max(school_days - present_days, 0),
        "active_minutes": active,
        "inactive_minutes": inactive,
        "late_days": late_days,
        # Computed here and never on the client, the same rule the pupil
        # reports follow: one place decides what a percentage means.
        "rate": round(present_days / school_days, 4) if school_days else 0.0,
    }


def week_summary(teacher, day: date_type) -> dict:
    """This week at school: time in, time out, and the days that started late."""
    span = week_range(day)
    return range_summary(teacher, span.start, span.end)


def school_day_totals(school, day: date_type) -> dict:
    """Every teacher's day at the gate, rolled into one set of figures.

    The home screen asks the same four questions of the teachers that the pupil
    pipeline answers from ``DailyPresence`` — who came, who was late, who is
    still inside — plus the three averages beside them. Teachers have no stored
    daily row, so this walks the day's passes once and pairs them per person
    rather than firing a query per teacher.

    The averages deliberately skip the people they would not describe: the
    average time inside is over those who actually came, and the average
    lateness is over those who were actually late. Averaging in a row of zeroes
    would quietly flatter both.
    """
    from collections import defaultdict

    from apps.schools.models import Teacher

    teachers = list(Teacher.objects.filter(school=school, is_active=True))
    total = len(teachers)
    if not total:
        return _empty_totals()

    config = integration_config(IntegrationKind.TERMINALS, school)
    debounce = int(config.get("debounce_seconds", 60))
    grace = int(config.get("late_grace_minutes", 0))
    day_start, day_end = school_day_bounds(config, day)
    working_minutes = max(int((day_end - day_start).total_seconds() // 60), 0)
    now = timezone.now()

    by_teacher: dict = defaultdict(list)
    passes = (
        TerminalEvent.objects.filter(teacher__in=teachers, date=day)
        .select_related("terminal")
        .order_by("occurred_at")
    )
    for event in passes:
        by_teacher[event.teacher_id].append(event)

    arrived = inside_now = late_people = 0
    inside_total = outside_total = late_total = 0

    for teacher in teachers:
        events = _debounce(by_teacher.get(teacher.id, []), debounce)
        if not events:
            continue
        visits, _entries, _exits, _outside, is_inside = build_visits(
            events, day_end=day_end, now=now
        )
        ins = [event for event in events if event.direction != EventDirection.OUT]
        if not ins:
            continue

        arrived += 1
        inside_minutes = sum(visit["minutes"] for visit in visits)
        inside_total += inside_minutes
        outside_total += max(working_minutes - inside_minutes, 0)
        if is_inside:
            inside_now += 1

        overdue = (ins[0].occurred_at - day_start).total_seconds() / 60
        if overdue > grace:
            late_people += 1
            late_total += int(overdue)

    return {
        "total": total,
        "arrived": arrived,
        "absent": max(total - arrived, 0),
        "inside": inside_now,
        "late": late_people,
        "rate": round(arrived / total * 100, 1) if total else 0.0,
        "avg_active_minutes": round(inside_total / arrived) if arrived else 0,
        "avg_inactive_minutes": round(outside_total / arrived) if arrived else 0,
        "avg_late_minutes": round(late_total / late_people) if late_people else 0,
    }


def _empty_totals() -> dict:
    return {
        "total": 0,
        "arrived": 0,
        "absent": 0,
        "inside": 0,
        "late": 0,
        "rate": 0.0,
        "avg_active_minutes": 0,
        "avg_inactive_minutes": 0,
        "avg_late_minutes": 0,
    }


def recent_passes(person, limit: int = 6) -> list[dict]:
    """The last few passes, newest first — the turnstile as a plain log."""
    from apps.integrations.services.enrollment import person_field

    events = (
        TerminalEvent.objects.filter(**{person_field(person): person})
        .select_related("terminal")
        .order_by("-occurred_at")[:limit]
    )
    return [
        {
            "id": str(event.id),
            "direction": (
                EventDirection.OUT
                if event.direction == EventDirection.OUT
                else EventDirection.IN
            ),
            "label": "Chiqdi" if event.direction == EventDirection.OUT else "Kirdi",
            "at": timezone.localtime(event.occurred_at).isoformat(timespec="seconds"),
            "time": _clock(event.occurred_at),
            "date": timezone.localtime(event.occurred_at).date().isoformat(),
            "terminal": event.terminal.name,
        }
        for event in events
    ]


def teacher_card(teacher) -> dict:
    """Who the cabinet is showing — the header and the navbar both read this."""
    return {
        "id": str(teacher.id),
        "first_name": teacher.first_name,
        "last_name": teacher.last_name,
        "middle_name": teacher.middle_name,
        "full_name": f"{teacher.last_name} {teacher.first_name} {teacher.middle_name}".strip(),
        "photo": absolute_media_url(teacher.photo),
        "email": teacher.email,
        "school": {
            "id": str(teacher.school_id),
            "name": teacher.school.name,
            "short_name": teacher.school.short_name,
            "logo": absolute_media_url(teacher.school.logo),
        },
    }


# --------------------------------------------------------------------------- #
# The teacher's calendar
# --------------------------------------------------------------------------- #
def _my_subjects(user):
    """The subjects whose lessons belong on this user's calendar.

    A teacher's calendar is the classes they personally stand in front of, a
    curator's is the groups they were given, and an administrator's is the
    whole school — they are not teaching, they are watching, and a calendar
    showing only their own (usually empty) timetable would be useless to them.
    Each of those is already what ``visible_subjects`` returns for that role.
    """
    from .lessons import visible_subjects

    return list(
        visible_subjects(user).select_related("class_group", "class_group__grade")
    )


def teaching_calendar(user, teacher, year: int, month: int) -> dict:
    """A month grid saying, for each day, whether this teacher has lessons.

    Green means the timetable puts them in front of a class that day; red means
    it does not. A holiday or a weekend is never a teaching day, whatever the
    timetable says.
    """
    from apps.attendance.models import Schedule

    from .. import selectors
    from .periods import calendar_grid_range, month_range

    subjects = _my_subjects(user)
    weekdays: dict[int, set] = {}
    if subjects:
        for weekday, group_id in Schedule.objects.filter(
            subject__in=subjects, is_active=True
        ).values_list("weekday", "class_group_id"):
            weekdays.setdefault(weekday, set()).add(group_id)

    span = calendar_grid_range(year, month)
    month_span = month_range(year, month)
    holidays = selectors.holiday_map(teacher.school_id, span.start, span.end)
    school = teacher.school

    days = []
    for day in span:
        holiday = holidays.get(day)
        working = school.is_working_weekday(day.isoweekday()) and not (
            holiday is not None and not holiday.is_working_day
        )
        groups = weekdays.get(day.isoweekday(), set()) if working else set()
        days.append(
            {
                "date": day.isoformat(),
                "weekday": day.isoweekday(),
                "in_month": month_span.start <= day <= month_span.end,
                "is_school_day": working,
                "holiday": holiday.name if holiday is not None else None,
                "teaches": bool(groups),
                "groups_count": len(groups),
            }
        )

    return {
        "year": year,
        "month": month,
        "start_date": span.start.isoformat(),
        "end_date": span.end.isoformat(),
        "today": timezone.localdate().isoformat(),
        "days": days,
    }


def teaching_day(user, teacher, day: date_type) -> dict:
    """One day of the calendar: the classes taught, and each class's lessons."""
    from apps.attendance.models import Lesson
    from apps.students.models import Student

    from .. import selectors
    from .timetable import entries_for

    subjects = {subject.id: subject for subject in _my_subjects(user)}
    groups = {}
    for subject in subjects.values():
        groups.setdefault(subject.class_group_id, subject.class_group)

    marked = dict(
        Lesson.objects.filter(subject_id__in=subjects, date=day)
        .values_list("subject_id")
        .annotate(total=Count("attendances"))
    )
    sizes = dict(
        Student.objects.active()
        .filter(class_group_id__in=groups)
        .values_list("class_group_id")
        .annotate(total=Count("id"))
    )

    payload = []
    for group_id, group in groups.items():
        lessons = []
        for entry in entries_for(group, day.isoweekday()):
            subject = subjects.get(entry.subject_id)
            if subject is None:
                continue
            lessons.append(
                {
                    "subject": str(subject.id),
                    "subject_name": subject.name,
                    "lesson_number": entry.lesson_number,
                    "start_time": entry.start_time.strftime("%H:%M"),
                    "end_time": entry.end_time.strftime("%H:%M"),
                    "room": entry.room,
                    "marked_count": marked.get(subject.id, 0),
                    "students_count": sizes.get(group_id, 0),
                }
            )
        if not lessons:
            continue
        payload.append(
            {
                "id": str(group_id),
                "display_name": group.display_name,
                "grade_level": group.grade.level,
                "students_count": sizes.get(group_id, 0),
                "lessons": lessons,
            }
        )

    holiday = selectors.holiday_map(teacher.school_id, day, day).get(day)
    payload.sort(key=lambda row: (row["grade_level"], row["display_name"]))
    return {
        "date": day.isoformat(),
        "weekday": day.isoweekday(),
        "holiday": holiday.name if holiday is not None else None,
        "groups": payload,
    }
