"""Report builders for the daily / weekly / monthly / yearly presence views.

The product measures *being at school*, so every report reads exactly one
source — the ``DailyPresence`` row the turnstile pipeline derives from the raw
passes — and hands the totals to :class:`PresenceTotals`, so a percentage can
only ever be computed one way.

A "school day" is a working weekday that is not a holiday and is not in the
future. Days the school was closed never enter a denominator.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta

from django.utils import timezone

from apps.schools.constants import MONTH_NAMES_UZ, WEEKDAY_SHORT_UZ, Weekday

from .. import selectors
from ..constants import (
    DAY_STATE_ABSENT,
    DAY_STATE_FUTURE,
    DAY_STATE_HOLIDAY,
    DAY_STATE_LATE,
    DAY_STATE_NO_DATA,
    DAY_STATE_PRESENT,
    DAY_STATE_WEEKEND,
)
from .periods import (
    DateRange,
    academic_year_range,
    calendar_grid_range,
    month_range,
    month_sequence,
    today,
    week_range,
)
from .presence_stats import PresenceTotals, totals_from_rows


# --------------------------------------------------------------------------- #
# Shared helpers
# --------------------------------------------------------------------------- #
def _presence_map(student, start: date, end: date) -> dict[date, object]:
    from apps.integrations.models import DailyPresence

    return {
        row.date: row
        for row in DailyPresence.objects.filter(
            student=student, date__gte=start, date__lte=end
        )
    }


def _clock(value) -> str | None:
    """``2026-09-09T08:24:11+05:00`` → ``08:24`` in the school's timezone."""
    if not value:
        return None
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    return timezone.localtime(value).strftime("%H:%M")


def _is_school_day(day: date, *, school, holiday, reference: date) -> bool:
    if day > reference:
        return False
    if holiday is not None and not holiday.is_working_day:
        return False
    return school.is_working_weekday(day.isoweekday())


def _day_state(day: date, *, presence, school, holiday, reference: date) -> str:
    if holiday is not None and not holiday.is_working_day:
        return DAY_STATE_HOLIDAY
    if not school.is_working_weekday(day.isoweekday()):
        return DAY_STATE_WEEKEND
    if day > reference:
        return DAY_STATE_FUTURE
    if presence is None or presence.first_in_at is None:
        # Today simply has not happened yet until the first pass arrives.
        return DAY_STATE_NO_DATA if day == reference else DAY_STATE_ABSENT
    if presence.arrived_too_late:
        # They did turn up — the arrival is still reported — but not in time
        # for the day to count as attended.
        return DAY_STATE_ABSENT
    return DAY_STATE_LATE if presence.late_minutes else DAY_STATE_PRESENT


def _running_presence(presence, day: date) -> tuple[int, list[dict]]:
    """Top an open visit up to the clock.

    The stored row froze at the last pass. A pupil who came in and has not left
    is still accumulating time, so today's "maktabda bo'lgan vaqt" is measured
    against now rather than against the last event.
    """
    sessions = list(presence.sessions or []) if presence else []
    if presence is None or not presence.is_inside or not sessions:
        return (presence.inside_minutes if presence else 0), sessions
    if day != timezone.localdate():
        return presence.inside_minutes, sessions

    last = dict(sessions[-1])
    if last.get("out") is not None or not last.get("in"):
        return presence.inside_minutes, sessions

    started = datetime.fromisoformat(last["in"])
    minutes = max(int((timezone.now() - started).total_seconds() // 60), 0)
    sessions[-1] = {**last, "minutes": minutes}
    total = presence.inside_minutes + minutes - int(last.get("minutes") or 0)
    return max(total, 0), sessions


def _visits_payload(sessions: list[dict]) -> list[dict]:
    return [
        {
            "in": _clock(visit.get("in")),
            "out": _clock(visit.get("out")),
            "minutes": visit.get("minutes", 0),
            "open": visit.get("out") is None,
        }
        for visit in sessions
    ]


def _day_payload(day: date, presence, *, state: str, holiday, is_school_day: bool) -> dict:
    """Everything one day contributes to any report."""
    inside_minutes, sessions = _running_presence(presence, day)
    return {
        "date": day.isoformat(),
        "weekday": day.isoweekday(),
        "weekday_short": WEEKDAY_SHORT_UZ[day.isoweekday()],
        "weekday_name": Weekday(day.isoweekday()).label,
        "state": state,
        "holiday": holiday.name if holiday is not None else None,
        "is_school_day": is_school_day,
        # An arrival past the cutoff is shown but does not count as a day at
        # school, so it never lands in `days_present`.
        "was_present": (
            presence is not None
            and presence.first_in_at is not None
            and not presence.arrived_too_late
        ),
        "arrived_too_late": bool(presence and presence.arrived_too_late),
        "arrived_at": _clock(presence.first_in_at) if presence else None,
        "is_inside": bool(presence and presence.is_inside),
        "first_in": _clock(presence.first_in_at) if presence else None,
        "last_out": _clock(presence.last_out_at) if presence else None,
        "first_out": _clock(presence.first_out_at) if presence else None,
        "last_in": _clock(presence.last_in_at) if presence else None,
        "entries": presence.entries_count if presence else 0,
        "exits": presence.exits_count if presence else 0,
        "inside_minutes": inside_minutes,
        "outside_minutes": presence.outside_minutes if presence else 0,
        "late_minutes": presence.late_minutes if presence else 0,
        "left_early": bool(presence and presence.left_early),
        "visits": _visits_payload(sessions),
    }


def _rows_for(days: list[dict]) -> list[dict]:
    """Only school days feed the totals — a Sunday is not an absence."""
    return [day for day in days if day["is_school_day"]]


def build_day_rows(student, span: DateRange, *, reference: date | None = None) -> list[dict]:
    reference = reference or today()
    presence = _presence_map(student, span.start, span.end)
    holidays = selectors.holiday_map(student.school_id, span.start, span.end)
    school = student.school

    days = []
    for day in span:
        holiday = holidays.get(day)
        row = presence.get(day)
        days.append(
            _day_payload(
                day,
                row,
                state=_day_state(
                    day, presence=row, school=school, holiday=holiday, reference=reference
                ),
                holiday=holiday,
                is_school_day=_is_school_day(
                    day, school=school, holiday=holiday, reference=reference
                ),
            )
        )
    return days


# --------------------------------------------------------------------------- #
# Daily
# --------------------------------------------------------------------------- #
def build_daily_presence(student, day: date | None = None) -> dict:
    day = day or today()
    report = build_day_rows(student, DateRange(day, day))[0]
    report["passes"] = _passes_payload(student, day)
    report["summary"] = totals_from_rows(_rows_for([report])).to_dict()
    return report


def _passes_payload(student, day: date) -> list[dict]:
    """The raw turnstile timeline — every pass, in order."""
    from apps.integrations.models import TerminalEvent

    events = (
        TerminalEvent.objects.filter(student=student, date=day)
        .select_related("terminal")
        .order_by("occurred_at")
    )
    return [
        {
            "id": str(event.id),
            "time": _clock(event.occurred_at),
            "direction": event.direction,
            "verify_mode": event.verify_mode,
            "terminal": event.terminal.name,
            "location": event.terminal.location,
        }
        for event in events
    ]


# --------------------------------------------------------------------------- #
# Weekly
# --------------------------------------------------------------------------- #
def build_weekly_presence(student, anchor: date | None = None) -> dict:
    span = week_range(anchor)
    days = build_day_rows(student, span)
    return {
        "start_date": span.start.isoformat(),
        "end_date": span.end.isoformat(),
        "days": days,
        "summary": totals_from_rows(_rows_for(days)).to_dict(),
    }


# --------------------------------------------------------------------------- #
# Monthly (calendar grid)
# --------------------------------------------------------------------------- #
def build_monthly_presence(student, year: int, month: int, *, include_grid: bool = True) -> dict:
    span = month_range(year, month)
    grid = calendar_grid_range(year, month) if include_grid else span
    reference = today()
    days = build_day_rows(student, grid, reference=reference)

    in_month = []
    for day in days:
        parsed = date.fromisoformat(day["date"])
        day["day"] = parsed.day
        day["in_month"] = parsed.year == year and parsed.month == month
        day["is_today"] = parsed == reference
        if day["in_month"]:
            in_month.append(day)

    return {
        "year": year,
        "month": month,
        "month_name": MONTH_NAMES_UZ[month],
        "start_date": span.start.isoformat(),
        "end_date": span.end.isoformat(),
        "grid_start": grid.start.isoformat(),
        "grid_end": grid.end.isoformat(),
        "weekday_labels": [WEEKDAY_SHORT_UZ[index] for index in range(1, 8)],
        "days": days,
        "summary": totals_from_rows(_rows_for(in_month)).to_dict(),
    }


# --------------------------------------------------------------------------- #
# Yearly
# --------------------------------------------------------------------------- #
def build_yearly_presence(student, academic_year=None, *, year: int | None = None) -> dict:
    if academic_year is None:
        academic_year = selectors.current_academic_year(student.school_id)

    if academic_year is not None:
        span = academic_year_range(academic_year)
        label = academic_year.name
    else:  # no academic year configured — fall back to a calendar year
        year = year or today().year
        span = DateRange(date(year, 1, 1), date(year, 12, 31))
        label = str(year)

    # The whole year day by day would be ~365 payloads; the yearly view only
    # needs per-month totals, so aggregate as we go.
    days = build_day_rows(student, span)
    per_month: dict[tuple[int, int], list] = defaultdict(list)
    for day in _rows_for(days):
        parsed = date.fromisoformat(day["date"])
        per_month[(parsed.year, parsed.month)].append(day)

    months = []
    year_totals = PresenceTotals()
    for year_number, month_number in month_sequence(span):
        totals = totals_from_rows(per_month.get((year_number, month_number), []))
        year_totals = year_totals + totals
        months.append(
            {
                "year": year_number,
                "month": month_number,
                "month_name": MONTH_NAMES_UZ[month_number],
                "summary": totals.to_dict(),
            }
        )

    return {
        "academic_year": label,
        "start_date": span.start.isoformat(),
        "end_date": span.end.isoformat(),
        "months": months,
        "summary": year_totals.to_dict(),
    }


# --------------------------------------------------------------------------- #
# Calendar section
# --------------------------------------------------------------------------- #
def build_presence_calendar(student, year: int, month: int) -> dict:
    """Monthly grid enriched with the parent's submitted absence reasons."""
    report = build_monthly_presence(student, year, month)
    span = DateRange(
        date.fromisoformat(report["grid_start"]), date.fromisoformat(report["grid_end"])
    )
    requests = {
        request.date: request
        for request in selectors.absence_requests_for(student, span.start, span.end)
    }
    for day in report["days"]:
        request = requests.get(date.fromisoformat(day["date"]))
        day["absence_request"] = (
            {
                "id": str(request.id),
                "status": request.status,
                "reason": request.reason.name,
                "comment": request.comment,
            }
            if request
            else None
        )
    return report


def build_recent_presence(student, *, days: int = 7) -> list[dict]:
    """The last few school days — the dashboard's activity strip."""
    end = today()
    start = end - timedelta(days=days)
    rows = build_day_rows(student, DateRange(start, end), reference=end)
    return [day for day in reversed(rows) if day["is_school_day"]]
