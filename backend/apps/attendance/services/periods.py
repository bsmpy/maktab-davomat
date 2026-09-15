"""Date-range helpers. All calendar maths is timezone-aware (Asia/Tashkent)."""
from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta

from django.utils import timezone


def today() -> date:
    """Local "today" — never the UTC date."""
    return timezone.localdate()


@dataclass(frozen=True)
class DateRange:
    start: date
    end: date

    def __iter__(self):
        cursor = self.start
        while cursor <= self.end:
            yield cursor
            cursor += timedelta(days=1)

    def contains(self, value: date) -> bool:
        return self.start <= value <= self.end


def week_range(anchor: date | None = None) -> DateRange:
    """Monday..Sunday week containing ``anchor``."""
    anchor = anchor or today()
    start = anchor - timedelta(days=anchor.weekday())
    return DateRange(start, start + timedelta(days=6))


def month_range(year: int, month: int) -> DateRange:
    last_day = calendar.monthrange(year, month)[1]
    return DateRange(date(year, month, 1), date(year, month, last_day))


def calendar_grid_range(year: int, month: int) -> DateRange:
    """Full Monday-aligned grid covering the month (for the calendar view)."""
    span = month_range(year, month)
    start = span.start - timedelta(days=span.start.weekday())
    end = span.end + timedelta(days=(6 - span.end.weekday()))
    return DateRange(start, end)


def academic_year_range(academic_year) -> DateRange:
    return DateRange(academic_year.start_date, academic_year.end_date)


def month_sequence(span: DateRange) -> list[tuple[int, int]]:
    """``[(2026, 9), (2026, 10), ...]`` covering the range."""
    months: list[tuple[int, int]] = []
    year, month = span.start.year, span.start.month
    while (year, month) <= (span.end.year, span.end.month):
        months.append((year, month))
        month += 1
        if month > 12:
            month = 1
            year += 1
    return months
