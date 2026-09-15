"""When an arrival counts, when it is late, and when it is too late.

    up to 08:10   → on time
    after 08:10   → late, by the difference
    after 16:00   → the day does not count as attended, but the arrival is
                    still reported rather than hidden
"""
from __future__ import annotations

from datetime import datetime, time, timedelta

import pytest
from django.utils import timezone
from django.utils.timezone import make_aware

from apps.attendance.services import build_daily_presence
from apps.integrations.constants import EventDirection
from apps.integrations.models import DailyPresence, TerminalEvent
from apps.integrations.services.presence import build_visits, rebuild_daily_presence
from tests.conftest import TODAY, at, pass_through

pytestmark = pytest.mark.django_db


def arrive(terminal, student, hour: int, minute: int, *, serial: int = 900):
    event = pass_through(terminal, "S1001", at(hour, minute), serial=serial)
    TerminalEvent.objects.filter(pk=event.pk).update(student=student)
    return rebuild_daily_presence(student, TODAY)


# --------------------------------------------------------------------------- #
# On time
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("hour,minute", [(7, 30), (8, 0), (8, 9), (8, 10)])
def test_arriving_up_to_the_start_is_on_time(
    terminal, person, student, hour, minute
):
    presence = arrive(terminal, student, hour, minute)
    assert presence.late_minutes == 0
    assert presence.arrived_too_late is False

    report = build_daily_presence(student, TODAY)
    assert report["state"] == "PRESENT"
    assert report["was_present"] is True
    assert report["summary"]["days_present"] == 1


# --------------------------------------------------------------------------- #
# Late
# --------------------------------------------------------------------------- #
def test_a_minute_past_the_start_is_late(terminal, person, student):
    presence = arrive(terminal, student, 8, 11)
    assert presence.late_minutes == 1

    report = build_daily_presence(student, TODAY)
    assert report["state"] == "LATE"
    # Late is still attended: the pupil is at school.
    assert report["was_present"] is True
    assert report["summary"]["days_late"] == 1


@pytest.mark.parametrize(
    "hour,minute,expected",
    [
        (8, 25, 15),
        (9, 10, 60),
        (9, 40, 90),
        (11, 10, 180),
    ],
)
def test_late_minutes_are_the_difference_from_the_start(
    terminal, person, student, hour, minute, expected
):
    presence = arrive(terminal, student, hour, minute)
    assert presence.late_minutes == expected


def test_over_an_hour_late_is_still_reported_in_minutes(terminal, person, student):
    """The backend keeps one unit; the UI is what renders hours and minutes."""
    presence = arrive(terminal, student, 10, 25)
    assert presence.late_minutes == 135

    report = build_daily_presence(student, TODAY)
    assert report["late_minutes"] == 135


# --------------------------------------------------------------------------- #
# Too late to count
# --------------------------------------------------------------------------- #
def test_arriving_after_the_cutoff_does_not_count_as_attended(
    terminal, person, student
):
    presence = arrive(terminal, student, 16, 20)
    assert presence.arrived_too_late is True

    report = build_daily_presence(student, TODAY)
    assert report["was_present"] is False
    assert report["state"] == "ABSENT"
    assert report["summary"]["days_present"] == 0
    assert report["summary"]["days_absent"] == 1


def test_a_too_late_arrival_is_still_shown(terminal, person, student):
    """Not counted is not the same as hidden — the parent still sees 16:20."""
    arrive(terminal, student, 16, 20)
    report = build_daily_presence(student, TODAY)

    assert report["arrived_too_late"] is True
    assert report["arrived_at"] == "16:20"
    assert report["first_in"] == "16:20"
    assert [item["time"] for item in report["passes"]] == ["16:20"]


def test_the_cutoff_is_exact(terminal, person, student):
    """15:59 still counts; 16:00 does not."""
    presence = arrive(terminal, student, 15, 59, serial=901)
    assert presence.arrived_too_late is False

    DailyPresence.objects.all().delete()
    TerminalEvent.objects.all().delete()

    presence = arrive(terminal, student, 16, 0, serial=902)
    assert presence.arrived_too_late is True


def test_the_thresholds_are_configurable(terminal, person, student, school):
    from apps.integrations.constants import IntegrationKind
    from apps.integrations.models import Integration

    Integration.objects.create(
        kind=IntegrationKind.TERMINALS,
        school=school,
        is_enabled=True,
        config={"school_start_time": "09:00", "arrival_cutoff_time": "12:00"},
    )
    presence = arrive(terminal, student, 8, 30)

    # Early for a 09:00 start, and nowhere near a noon cutoff.
    assert presence.late_minutes == 0
    assert presence.arrived_too_late is False


# --------------------------------------------------------------------------- #
# Still inside: the clock keeps running
# --------------------------------------------------------------------------- #
@pytest.fixture
def fixture_day():
    return TODAY


def _passes(day, *times):
    """Alternating IN/OUT stubs at the given local times."""
    events = []
    for index, moment in enumerate(times):
        events.append(
            TerminalEvent(
                direction=(
                    EventDirection.IN if index % 2 == 0 else EventDirection.OUT
                ),
                occurred_at=make_aware(datetime.combine(day, moment)),
            )
        )
    return events


def test_time_inside_counts_to_now_while_the_pupil_is_still_in(fixture_day):
    """Entered, not left: maktabda bo'lgan vaqt = hozirgi vaqt − kirgan vaqt."""
    day_end = make_aware(datetime.combine(fixture_day, time(14, 0)))
    now = make_aware(datetime.combine(fixture_day, time(11, 30)))

    visits, _entries, _exits, _outside, is_inside = build_visits(
        _passes(fixture_day, time(8, 0)), day_end=day_end, now=now
    )

    assert is_inside is True
    assert visits[-1]["out"] is None
    assert visits[-1]["minutes"] == 210  # 08:00 → 11:30


def test_the_running_total_does_not_stop_when_lessons_end(fixture_day):
    """Still inside at 16:20 — the count is 8 h 20 m, not frozen at 14:00."""
    day_end = make_aware(datetime.combine(fixture_day, time(14, 0)))
    now = make_aware(datetime.combine(fixture_day, time(16, 20)))

    visits, _entries, _exits, _outside, is_inside = build_visits(
        _passes(fixture_day, time(8, 0)), day_end=day_end, now=now
    )

    assert is_inside is True
    assert visits[-1]["minutes"] == 500  # 08:00 → 16:20


def test_a_forgotten_exit_on_a_past_day_stops_at_the_school_end(fixture_day):
    """Yesterday's open visit is measured to the end of the school day."""
    past = fixture_day - timedelta(days=1)
    day_end = make_aware(datetime.combine(past, time(14, 0)))
    now = make_aware(datetime.combine(fixture_day, time(10, 0)))

    visits, _entries, _exits, _outside, is_inside = build_visits(
        _passes(past, time(8, 0)), day_end=day_end, now=now
    )

    assert is_inside is True
    assert visits[-1]["minutes"] == 360  # 08:00 → 14:00, not into today


def test_a_closed_visit_is_measured_between_the_two_passes(fixture_day):
    day_end = make_aware(datetime.combine(fixture_day, time(14, 0)))
    now = make_aware(datetime.combine(fixture_day, time(16, 0)))

    visits, entries, exits, _outside, is_inside = build_visits(
        _passes(fixture_day, time(8, 0), time(13, 30)), day_end=day_end, now=now
    )

    assert (entries, exits, is_inside) == (1, 1, False)
    assert visits[0]["minutes"] == 330


def test_the_report_keeps_counting_for_a_pupil_who_is_still_inside(
    terminal, student, class_groups, clock_at
):
    """The stored row froze at the entry; the report tops it up to now."""
    clock_at(11, 30)
    arrive(terminal, student, 8, 0)
    presence = DailyPresence.objects.get(student=student, date=TODAY)
    assert presence.is_inside is True

    # Pretend the row was written the moment the pupil walked in.
    DailyPresence.objects.filter(pk=presence.pk).update(
        inside_minutes=0, sessions=[{"in": at(8, 0).isoformat(), "out": None, "minutes": 0}]
    )

    report = build_daily_presence(student, TODAY)
    elapsed = int((timezone.now() - at(8, 0)).total_seconds() // 60)
    assert report["inside_minutes"] == elapsed
    assert report["visits"][-1]["open"] is True
    assert report["visits"][-1]["minutes"] == elapsed
