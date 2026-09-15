"""Turning device events into ``TerminalEvent`` rows.

Two ingestion paths, one code path afterwards:

* **push** – the device's "HTTP Listening" notification posts to
  ``/api/v1/terminals/events/<ingest_token>/``. Works when the device can reach
  the backend; nothing has to be reachable on the LAN.
* **pull** – a Celery beat task calls ``AcsEvent`` on a schedule. Works when the
  backend can reach the device; survives the device being unable to call out.

Running both is fine and is in fact the recommended setup: the unique
``(terminal, external_id)`` constraint makes duplicates impossible, so push
gives low latency and poll guarantees nothing is lost while the backend is down.
"""
from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import datetime, timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from ..constants import (
    HIKVISION_DIRECTION_MAP,
    HIKVISION_GRANTED_MINOR,
    HIKVISION_VERIFY_MAP,
    EventDirection,
    IntegrationKind,
    TerminalDirection,
    VerifyMode,
)
from ..models import Terminal, TerminalEvent, TerminalPerson
from .hikvision import AccessEvent, HikvisionClient, HikvisionError, _parse_device_time
from .registry import integration_config

logger = logging.getLogger(__name__)


def _direction_for(terminal: Terminal, attendance_status: str) -> str:
    """A one-way reader always wins; a two-way one is trusted to label itself."""
    if terminal.direction == TerminalDirection.IN:
        return EventDirection.IN
    if terminal.direction == TerminalDirection.OUT:
        return EventDirection.OUT
    return HIKVISION_DIRECTION_MAP.get(attendance_status, EventDirection.UNKNOWN)


def _verify_mode(raw: str) -> str:
    return HIKVISION_VERIFY_MAP.get((raw or "").strip(), VerifyMode.OTHER)


def _resolve_person(terminal: Terminal, person_code: str):
    """Whose pass this is: a pupil, a teacher, another employee, or nobody.

    Returns ``(student, teacher, staff)`` with at most one of them set — the
    enrolment record decides, so there is one source of truth for all three
    registers.
    """
    empty = (None, None, None)
    if not person_code:
        return empty
    person = (
        TerminalPerson.objects.filter(school_id=terminal.school_id, person_code=person_code)
        .select_related(
            "student", "student__class_group", "student__school", "teacher", "staff"
        )
        .first()
    )
    if person is None:
        return empty
    return person.student, person.teacher, person.staff


def store_event(terminal: Terminal, event: AccessEvent) -> TerminalEvent | None:
    """Persist one normalised event. Returns ``None`` when it is a duplicate.

    Denied attempts are dropped: an unrecognised face at the turnstile is not an
    arrival, and recording it would let a stranger mark a pupil present.
    """
    if event.minor and event.minor not in HIKVISION_GRANTED_MINOR:
        logger.debug("Ignoring non-granted event minor=%s on %s", event.minor, terminal.name)
        return None

    student, teacher, staff = _resolve_person(terminal, event.person_code)

    try:
        with transaction.atomic():
            record = TerminalEvent.objects.create(
                terminal=terminal,
                external_id=event.external_id,
                occurred_at=event.occurred_at,
                direction=_direction_for(terminal, event.attendance_status),
                verify_mode=_verify_mode(event.verify_mode),
                person_code=event.person_code,
                person_name=event.person_name,
                student=student,
                teacher=teacher,
                staff=staff,
                picture_url=event.picture_url,
                raw=event.raw,
            )
    except IntegrityError:
        return None  # already ingested — push and poll overlapping is expected

    return record


def ingest_events(terminal: Terminal, events: Iterable[AccessEvent]) -> list[TerminalEvent]:
    stored = [record for event in events if (record := store_event(terminal, event)) is not None]

    if stored:
        latest = max(record.occurred_at for record in stored)
        if terminal.last_event_at is None or latest > terminal.last_event_at:
            terminal.last_event_at = latest
            terminal.save(update_fields=["last_event_at", "updated_at"])
    return stored


# --------------------------------------------------------------------------- #
# Push
# --------------------------------------------------------------------------- #
def parse_push_payload(payload: dict) -> list[AccessEvent]:
    """Normalise a device's HTTP-listening notification.

    Firmware differs in how it wraps the record — sometimes ``AccessControllerEvent``
    inside ``event_log``, sometimes a bare ``AcsEvent`` info block — so several
    shapes are accepted.
    """
    candidates: list[dict] = []

    if "AccessControllerEvent" in payload:
        merged = dict(payload["AccessControllerEvent"])
        merged.setdefault("time", payload.get("dateTime") or payload.get("time"))
        candidates.append(merged)

    event_log = payload.get("event_log") or payload.get("EventNotificationAlert")
    if isinstance(event_log, dict):
        inner = event_log.get("AccessControllerEvent")
        if isinstance(inner, dict):
            merged = dict(inner)
            merged.setdefault("time", event_log.get("dateTime") or event_log.get("time"))
            candidates.append(merged)

    for key in ("AcsEvent", "InfoList"):
        block = payload.get(key)
        if isinstance(block, dict):
            candidates.extend(block.get("InfoList") or [])
        elif isinstance(block, list):
            candidates.extend(block)

    if not candidates and payload.get("employeeNoString") or payload.get("employeeNo"):
        candidates.append(payload)

    events: list[AccessEvent] = []
    for record in candidates:
        occurred_at = _parse_device_time(str(record.get("time") or record.get("dateTime") or ""))
        if occurred_at is None:
            continue
        person_code = str(
            record.get("employeeNoString") or record.get("employeeNo") or ""
        ).strip()
        serial = record.get("serialNo")
        external_id = (
            f"sn:{serial}"
            if serial not in (None, "", 0)
            else f"tm:{person_code}:{occurred_at.isoformat()}"
        )
        events.append(
            AccessEvent(
                external_id=external_id[:128],
                occurred_at=occurred_at,
                person_code=person_code[:64],
                person_name=str(record.get("name") or "")[:150],
                minor=int(record.get("minor") or 0),
                attendance_status=str(record.get("attendanceStatus") or ""),
                verify_mode=str(
                    record.get("currentVerifyMode") or record.get("verifyMode") or ""
                ),
                picture_url=str(record.get("pictureURL") or ""),
                raw=record,
            )
        )
    return events


# --------------------------------------------------------------------------- #
# Pull
# --------------------------------------------------------------------------- #
def poll_terminal(
    terminal: Terminal, *, since: datetime | None = None, until: datetime | None = None
) -> dict:
    """Fetch new events from one device. Safe to call as often as you like."""
    config = integration_config(IntegrationKind.TERMINALS, terminal.school)
    window = int(config.get("poll_window_minutes", 120))

    until = until or timezone.now()
    if since is None:
        # Overlap the previous window by a minute so an event landing exactly on
        # the boundary cannot slip between two polls.
        since = (
            terminal.last_event_at - timedelta(minutes=1)
            if terminal.last_event_at
            else until - timedelta(minutes=window)
        )

    try:
        with HikvisionClient.for_terminal(terminal) as client:
            info = client.device_info()
            terminal.mark_online(firmware=info.firmware, serial=info.serial_number)
            events = list(client.search_events(since, until))
    except HikvisionError as error:
        terminal.mark_offline(str(error))
        logger.warning("Poll failed for terminal %s: %s", terminal.name, error)
        return {"terminal": terminal.name, "ok": False, "error": str(error), "stored": 0}

    stored = ingest_events(terminal, events)
    terminal.last_polled_at = timezone.now()
    terminal.save(update_fields=["last_polled_at", "updated_at"])

    from .presence import process_events

    summary = process_events(stored) if stored else {"students": 0, "created": 0, "updated": 0}

    return {
        "terminal": terminal.name,
        "ok": True,
        "fetched": len(events),
        "stored": len(stored),
        **summary,
    }
