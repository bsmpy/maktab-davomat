"""The single source of truth for presence arithmetic.

Every endpoint (daily, weekly, monthly, yearly, dashboard, Telegram) funnels
through :func:`totals_from_rows`. Nothing recomputes a percentage anywhere
else — the frontend renders ``summary.rate`` and never derives it.

    rate = days_present / school_days

A school day is a working weekday that is not a holiday and is not in the
future; days the school was closed never enter the denominator, so a term that
has not started yet reads 0 out of 0 rather than a wall of absences.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass


def presence_rate(*, school_days: int, days_present: int) -> float:
    """Percentage rounded to one decimal. Returns ``0.0`` for an empty period."""
    if school_days <= 0:
        return 0.0
    return round(days_present * 100 / school_days, 1)


@dataclass
class PresenceTotals:
    """Counts for a period plus the derived percentage."""

    school_days: int = 0
    days_present: int = 0
    days_absent: int = 0
    days_late: int = 0
    entries: int = 0
    exits: int = 0
    inside_minutes: int = 0
    outside_minutes: int = 0
    late_minutes: int = 0
    rate: float = 0.0

    @property
    def avg_inside_minutes(self) -> int:
        """Average time in the building over the days the pupil actually came."""
        if self.days_present <= 0:
            return 0
        return int(self.inside_minutes / self.days_present)

    def recompute(self) -> PresenceTotals:
        self.rate = presence_rate(
            school_days=self.school_days, days_present=self.days_present
        )
        return self

    def to_dict(self) -> dict:
        data = asdict(self)
        data["avg_inside_minutes"] = self.avg_inside_minutes
        return data

    def __add__(self, other: PresenceTotals) -> PresenceTotals:
        return PresenceTotals(
            school_days=self.school_days + other.school_days,
            days_present=self.days_present + other.days_present,
            days_absent=self.days_absent + other.days_absent,
            days_late=self.days_late + other.days_late,
            entries=self.entries + other.entries,
            exits=self.exits + other.exits,
            inside_minutes=self.inside_minutes + other.inside_minutes,
            outside_minutes=self.outside_minutes + other.outside_minutes,
            late_minutes=self.late_minutes + other.late_minutes,
        ).recompute()


def totals_from_rows(days) -> PresenceTotals:
    """Aggregate already-built day payloads. ``days`` must be school days only."""
    totals = PresenceTotals()
    for day in days:
        totals.school_days += 1
        if day["was_present"]:
            totals.days_present += 1
            if day["late_minutes"]:
                totals.days_late += 1
                totals.late_minutes += day["late_minutes"]
        else:
            totals.days_absent += 1
        totals.entries += day["entries"]
        totals.exits += day["exits"]
        totals.inside_minutes += day["inside_minutes"]
        totals.outside_minutes += day["outside_minutes"]
    return totals.recompute()
