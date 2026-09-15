"""Turnstile events → visits → one ``DailyPresence`` row per pupil per day.

The product tracks *being at school*, not being at a lesson: how many times a
pupil walked in, how many times they walked out, when the first entry and the
last exit were, how long they were inside and how long they were outside
between visits.

``rebuild_daily_presence``
    Collapses a day's raw passes into visits (an entry paired with the exit
    that follows it) and stores the aggregates the reports read.

Everything is idempotent — a late-arriving event, a device resync or a manual
re-run converge on the same answer, because the raw ``TerminalEvent`` rows are
the only source of truth and the day is always rebuilt from scratch.
"""
from __future__ import annotations

import logging
from datetime import date as date_type
from datetime import datetime, time, timedelta

from django.db import transaction
from django.utils import timezone

from ..constants import EventDirection, IntegrationKind, PresenceSource
from ..models import DailyPresence, TerminalEvent
from .registry import integration_config

logger = logging.getLogger(__name__)

DEFAULT_SCHOOL_START = time(8, 10)
DEFAULT_SCHOOL_END = time(14, 0)
#: Arriving after this is too late for the day to count as attended.
DEFAULT_ARRIVAL_CUTOFF = time(16, 0)


def _combine(day: date_type, moment: time) -> datetime:
    """School times are naive clock times; anchor them to the school's day."""
    return timezone.make_aware(datetime.combine(day, moment), timezone.get_current_timezone())


def _parse_time(value, fallback: time) -> time:
    if isinstance(value, time):
        return value
    try:
        hour, _, minute = str(value).partition(":")
        return time(int(hour), int(minute or 0))
    except (TypeError, ValueError):
        return fallback


def school_day_bounds(config: dict, day: date_type) -> tuple[datetime, datetime]:
    start = _parse_time(config.get("school_start_time"), DEFAULT_SCHOOL_START)
    end = _parse_time(config.get("school_end_time"), DEFAULT_SCHOOL_END)
    return _combine(day, start), _combine(day, end)


def arrival_cutoff(config: dict, day: date_type) -> datetime:
    """After this moment an arrival no longer makes the day count."""
    return _combine(
        day, _parse_time(config.get("arrival_cutoff_time"), DEFAULT_ARRIVAL_CUTOFF)
    )


def _ordered_events(student, day: date_type) -> list[TerminalEvent]:
    return list(
        TerminalEvent.objects.filter(student=student, date=day)
        .select_related("terminal")
        .order_by("occurred_at")
    )


def _debounce(events: list[TerminalEvent], seconds: int) -> list[TerminalEvent]:
    """Drop repeat reads in the same direction within the debounce window.

    A turnstile happily records three passes while a pupil fumbles their bag;
    those are one entry, not three.
    """
    if seconds <= 0:
        return events
    window = timedelta(seconds=seconds)
    kept: list[TerminalEvent] = []
    for event in events:
        if kept:
            previous = kept[-1]
            same_direction = previous.direction == event.direction
            if same_direction and event.occurred_at - previous.occurred_at < window:
                continue
        kept.append(event)
    return kept


def _directed(events: list[TerminalEvent]) -> list[tuple[str, datetime]]:
    """Give every pass a direction.

    A reader configured as ``BOTH`` may not label the pass at all. Undirected
    passes simply alternate from the first one: in, out, in, out …
    """
    resolved: list[tuple[str, datetime]] = []
    for event in events:
        direction = event.direction
        if direction not in (EventDirection.IN, EventDirection.OUT):
            previous = resolved[-1][0] if resolved else EventDirection.OUT
            direction = (
                EventDirection.OUT if previous == EventDirection.IN else EventDirection.IN
            )
        resolved.append((direction, event.occurred_at))
    return resolved


def build_visits(
    events: list[TerminalEvent], *, day_end: datetime, now: datetime
) -> tuple[list[dict], int, int, int, bool]:
    """Pair entries with exits.

    Returns ``(visits, entries, exits, outside_minutes, is_inside)``. A visit is
    ``{"in": iso, "out": iso|null, "minutes": int}``; the last one stays open
    while the pupil is still inside, and is measured against "now" today or the
    end of the school day for a day that is already over.
    """
    passes = _directed(events)
    entries = sum(1 for direction, _ in passes if direction == EventDirection.IN)
    exits = sum(1 for direction, _ in passes if direction == EventDirection.OUT)

    visits: list[dict] = []
    open_since: datetime | None = None
    for direction, moment in passes:
        if direction == EventDirection.IN:
            # Two entries in a row: the exit was missed, keep the earlier one.
            if open_since is None:
                open_since = moment
            continue
        if open_since is None:
            # An exit with no matching entry (the pupil arrived before the
            # device was reachable). Nothing to measure — skip it.
            continue
        visits.append(
            {
                "in": open_since.isoformat(),
                "out": moment.isoformat(),
                "minutes": max(int((moment - open_since).total_seconds() // 60), 0),
            }
        )
        open_since = None

    is_inside = open_since is not None
    if is_inside:
        # Still inside, so "maktabda bo'lgan vaqt" is a running total: now minus
        # the entry, and it keeps counting after lessons end. On a day that is
        # already over the measure stops at the end of the school day instead,
        # so a forgotten exit cannot grow without bound.
        still_today = now.date() == day_end.date()
        closes_at = max(now if still_today else day_end, open_since)
        visits.append(
            {
                "in": open_since.isoformat(),
                "out": None,
                "minutes": max(int((closes_at - open_since).total_seconds() // 60), 0),
            }
        )

    # Time spent outside = the gaps between one visit ending and the next
    # starting. Time before the first entry and after the last exit is not
    # "outside school", it is simply not a school visit.
    outside_minutes = 0
    for previous, following in zip(visits, visits[1:], strict=False):
        if previous["out"] is None:
            continue
        gap = datetime.fromisoformat(following["in"]) - datetime.fromisoformat(previous["out"])
        outside_minutes += max(int(gap.total_seconds() // 60), 0)

    return visits, entries, exits, outside_minutes, is_inside


@transaction.atomic
def rebuild_daily_presence(student, day: date_type) -> DailyPresence | None:
    """Recompute one pupil's whole day from the raw passes."""
    config = integration_config(IntegrationKind.TERMINALS, student.school)
    events = _debounce(_ordered_events(student, day), int(config.get("debounce_seconds", 60)))

    if not events:
        DailyPresence.objects.filter(student=student, date=day).delete()
        return None

    day_start, day_end = school_day_bounds(config, day)
    visits, entries, exits, outside_minutes, is_inside = build_visits(
        events, day_end=day_end, now=timezone.now()
    )

    first_in = datetime.fromisoformat(visits[0]["in"]) if visits else events[0].occurred_at
    closed = [visit for visit in visits if visit["out"]]
    last_out = datetime.fromisoformat(closed[-1]["out"]) if closed else None

    # On time up to the start; a minute past it is late. The grace period stays
    # configurable but defaults to nothing, so the rule is the clock.
    grace = int(config.get("late_grace_minutes", 0))
    overdue = (first_in - day_start).total_seconds() / 60
    late_minutes = min(int(overdue), 600) if overdue > grace else 0
    left_early = bool(last_out and not is_inside and last_out < day_end)
    too_late = first_in >= arrival_cutoff(config, day)

    presence, _created = DailyPresence.objects.update_or_create(
        student=student,
        date=day,
        defaults={
            "first_in_at": first_in,
            "last_out_at": last_out,
            "entries_count": entries,
            "exits_count": exits,
            "source": PresenceSource.TERMINAL,
            "late_minutes": late_minutes,
            "left_early": left_early,
            "inside_minutes": sum(visit["minutes"] for visit in visits),
            "outside_minutes": outside_minutes,
            "sessions": visits,
            "is_inside": is_inside,
            "arrived_too_late": too_late,
        },
    )
    return presence


def process_events(events) -> dict:
    """Resolve → presence → notify for a batch of freshly ingested passes."""
    touched: set[tuple] = set()
    for event in events:
        if event.student_id:
            touched.add((event.student_id, event.date))

    from apps.students.models import Student

    students = {
        student.id: student
        for student in Student.objects.filter(
            id__in={student_id for student_id, _ in touched}
        ).select_related("class_group", "class_group__grade", "school")
    }

    summary = {"students": 0, "notified": 0}
    for student_id, day in sorted(touched, key=lambda item: str(item[0])):
        student = students.get(student_id)
        if student is None:
            continue
        rebuild_daily_presence(student, day)
        summary["students"] += 1

    # Notify per pass, not per day: a parent wants to know about each entry and
    # each exit, and the dedupe key is the event itself so a re-ingest is silent.
    for event in events:
        if event.student_id and queue_presence_notification(event):
            summary["notified"] += 1

    TerminalEvent.objects.filter(pk__in=[event.pk for event in events]).update(
        processed=True, processed_at=timezone.now()
    )
    return summary


def queue_presence_notification(event: TerminalEvent) -> bool:
    """Schedule the entry/exit push for one pass once the transaction commits."""
    if event.direction not in (EventDirection.IN, EventDirection.OUT):
        return False

    from apps.notifications.tasks import notify_presence_event

    event_id = str(event.pk)
    transaction.on_commit(lambda: notify_presence_event.delay(event_id))
    return True


def close_open_visits(school, day: date_type) -> int:
    """End-of-day sweep: settle every day that still has an open visit.

    Once the school day is over an unmatched entry must stop growing, so the
    row is rebuilt one last time with the day already finished.
    """
    from apps.students.models import Student

    open_ids = list(
        DailyPresence.objects.filter(
            date=day, is_inside=True, student__school=school
        ).values_list("student_id", flat=True)
    )
    if not open_ids:
        return 0

    students = (
        Student.objects.active()
        .filter(id__in=open_ids)
        .select_related("class_group", "school")
    )
    closed = 0
    for student in students.iterator(chunk_size=200):
        rebuild_daily_presence(student, day)
        closed += 1
    return closed
