"""A settable clock, so the cabinet can be demonstrated on a day that is not today.

Setting ``CLOCK_OFFSET_SECONDS`` shifts every time the application reads by a
fixed amount. Because the shift is constant, time still runs at its normal
speed — set it to next Monday 10:10 and it goes on to 10:11, 10:12 and so on —
and it survives a restart, unlike anchoring to a moment at boot.

This exists for demonstrations and for testing a timetable on a weekday that
has not arrived yet. It is off by default (offset 0) and should stay off in a
real deployment: everything the pipeline writes — turnstile passes, marks,
audit rows — is stamped with the shifted clock, not the wall clock.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

#: Set by :func:`install`, so the patched ``now`` can reach the real one.
_real_now = None


def offset() -> timedelta:
    return timedelta(seconds=getattr(settings, "CLOCK_OFFSET_SECONDS", 0) or 0)


def is_shifted() -> bool:
    return bool(getattr(settings, "CLOCK_OFFSET_SECONDS", 0))


def real_now() -> datetime:
    """The wall clock, whatever the offset says."""
    return _real_now() if _real_now is not None else timezone.now()


def offset_for(target: datetime) -> int:
    """Seconds to put in ``CLOCK_OFFSET_SECONDS`` to make now read ``target``."""
    return round((target - real_now()).total_seconds())


def install() -> None:
    """Patch ``django.utils.timezone.now`` once, at startup.

    Everything in the project reads the clock through ``timezone.now()`` or
    ``timezone.localdate()`` — and ``localdate`` calls ``now`` by module lookup
    — so this single patch shifts the whole application consistently.
    """
    global _real_now
    if _real_now is not None or not is_shifted():
        return

    _real_now = timezone.now
    shift = offset()

    def shifted_now():
        return _real_now() + shift

    timezone.now = shifted_now
    logger.warning(
        "Clock is shifted by %s — now reads %s. Unset CLOCK_OFFSET_SECONDS to stop.",
        shift,
        timezone.localtime(shifted_now()).isoformat(timespec="seconds"),
    )


def uninstall() -> None:
    """Put the wall clock back. The test suite always runs on real time."""
    global _real_now
    if _real_now is None:
        return
    timezone.now = _real_now
    _real_now = None
