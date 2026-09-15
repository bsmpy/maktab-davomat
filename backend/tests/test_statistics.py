"""The presence formula: one place computes a percentage, and this pins it."""
from __future__ import annotations

from apps.attendance.services.presence_stats import (
    PresenceTotals,
    presence_rate,
    totals_from_rows,
)


def day(
    *,
    present: bool = True,
    late: int = 0,
    entries: int = 1,
    exits: int = 1,
    inside: int = 300,
    outside: int = 0,
) -> dict:
    return {
        "was_present": present,
        "late_minutes": late,
        "entries": entries,
        "exits": exits,
        "inside_minutes": inside,
        "outside_minutes": outside,
    }


def test_rate_is_days_present_over_school_days():
    assert presence_rate(school_days=20, days_present=19) == 95.0
    assert presence_rate(school_days=3, days_present=1) == 33.3


def test_an_empty_period_is_zero_not_a_division_error():
    assert presence_rate(school_days=0, days_present=0) == 0.0


def test_totals_count_days_not_passes():
    totals = totals_from_rows(
        [day(), day(late=12), day(present=False, entries=0, exits=0, inside=0)]
    )
    assert totals.school_days == 3
    assert totals.days_present == 2
    assert totals.days_absent == 1
    assert totals.days_late == 1
    assert totals.late_minutes == 12
    assert totals.rate == 66.7


def test_time_inside_and_outside_is_summed():
    totals = totals_from_rows(
        [day(inside=300, outside=30, entries=2, exits=2), day(inside=280, outside=0)]
    )
    assert totals.inside_minutes == 580
    assert totals.outside_minutes == 30
    assert totals.entries == 3
    assert totals.exits == 3


def test_average_time_inside_uses_days_actually_attended():
    totals = totals_from_rows([day(inside=300), day(inside=200), day(present=False, inside=0)])
    # 500 minutes over the two days they came, not over all three.
    assert totals.avg_inside_minutes == 250


def test_average_is_zero_when_the_pupil_never_came():
    assert totals_from_rows([day(present=False, inside=0)]).avg_inside_minutes == 0


def test_totals_add_up_and_recompute_the_rate():
    first = totals_from_rows([day(), day()])
    second = totals_from_rows([day(present=False, inside=0)])
    combined = first + second

    assert combined.school_days == 3
    assert combined.days_present == 2
    assert combined.rate == 66.7


def test_an_empty_totals_object_is_neutral():
    assert (PresenceTotals() + totals_from_rows([day()])).rate == 100.0
