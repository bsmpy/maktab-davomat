"""Celery tasks for the terminal integration.

All of them are safe to retry: ingestion is deduplicated by
``(terminal, external_id)`` and the presence/attendance derivations are pure
functions of the stored events.
"""
from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, acks_late=True)
def poll_terminal(self, terminal_id: str) -> dict:
    """Pull new access events from one device."""
    from .models import Terminal
    from .services.ingest import poll_terminal as run_poll

    terminal = Terminal.objects.filter(pk=terminal_id, is_active=True).select_related(
        "school"
    ).first()
    if terminal is None:
        return {"ok": False, "error": "terminal not found"}
    return run_poll(terminal)


@shared_task
def poll_all_terminals() -> dict:
    """Beat task: poll every active device.

    Each device is dispatched as its own task so one unreachable turnstile
    cannot delay the others.
    """
    from .models import Terminal

    terminal_ids = list(
        Terminal.objects.filter(is_active=True, deleted_at__isnull=True).values_list(
            "id", flat=True
        )
    )
    for terminal_id in terminal_ids:
        poll_terminal.delay(str(terminal_id))
    return {"dispatched": len(terminal_ids)}


@shared_task(bind=True, acks_late=True)
def process_terminal_events(self, event_ids: list[str]) -> dict:
    """Derive presence + attendance for a batch of freshly ingested events."""
    from .models import TerminalEvent
    from .services.presence import process_events

    events = list(
        TerminalEvent.objects.filter(pk__in=event_ids).select_related(
            "student", "student__class_group", "student__school"
        )
    )
    if not events:
        return {"students": 0}
    return process_events(events)


@shared_task
def close_school_day(school_id: str | None = None, day: str | None = None) -> dict:
    """Beat task: settle every pupil still counted as inside the building.

    An entry with no matching exit keeps accruing time until the school day is
    over; this rebuilds those days once more, now that it is.
    """
    from datetime import date as date_type

    from apps.attendance.services.periods import today
    from apps.schools.models import School

    from .services.presence import close_open_visits

    target = date_type.fromisoformat(day) if day else today()
    schools = School.objects.filter(is_active=True)
    if school_id:
        schools = schools.filter(pk=school_id)

    closed = 0
    for school in schools:
        closed += close_open_visits(school, target)
    return {"date": target.isoformat(), "closed": closed}


@shared_task(bind=True, acks_late=True)
def enroll_student_on_terminals(self, student_id: str) -> dict:
    """Push one pupil (and their face) onto every active device."""
    from apps.students.models import Student

    from .services.enrollment import enroll_person

    student = (
        Student.objects.filter(pk=student_id).select_related("school", "class_group").first()
    )
    if student is None:
        return {"ok": False, "error": "student not found"}
    return enroll_person(student)


@shared_task(bind=True, acks_late=True)
def enroll_teacher_on_terminals(self, teacher_id: str) -> dict:
    """Push one member of staff onto every active device."""
    from apps.schools.models import Teacher

    from .services.enrollment import enroll_person

    teacher = Teacher.objects.filter(pk=teacher_id).select_related("school").first()
    if teacher is None:
        return {"ok": False, "error": "teacher not found"}
    return enroll_person(teacher)


@shared_task(bind=True, acks_late=True)
def enroll_staff_on_terminals(self, staff_id: str) -> dict:
    """Push one non-teaching employee onto every active device.

    Same gate, same face library, same enrolment path as a pupil or a teacher —
    only the register row differs.
    """
    from apps.schools.models import StaffMember

    from .services.enrollment import enroll_person

    staff = StaffMember.objects.filter(pk=staff_id).select_related("school").first()
    if staff is None:
        return {"ok": False, "error": "staff not found"}
    return enroll_person(staff)


@shared_task(bind=True, acks_late=True)
def remove_student_from_terminals(self, student_id: str) -> dict:
    """Take a pupil off every device — a pupil who left must not open the gate."""
    from apps.students.models import Student

    from .services.enrollment import remove_student

    student = (
        Student.all_objects.filter(pk=student_id).select_related("school", "class_group").first()
    )
    if student is None:
        return {"ok": False, "error": "student not found"}
    return remove_student(student)


@shared_task
def sync_all_students(school_id: str | None = None) -> dict:
    """Bulk enrolment — typically run once at the start of a school year."""
    from apps.students.models import Student

    from .models import Terminal
    from .services.enrollment import enroll_student

    students = Student.objects.active().select_related("school", "class_group")
    if school_id:
        students = students.filter(school_id=school_id)

    cache: dict = {}
    total = {"students": 0, "faces": 0, "errors": 0}
    for student in students.iterator(chunk_size=100):
        terminals = cache.get(student.school_id)
        if terminals is None:
            terminals = list(
                Terminal.objects.filter(school_id=student.school_id, is_active=True)
            )
            cache[student.school_id] = terminals
        if not terminals:
            continue
        result = enroll_student(student, terminals)
        total["students"] += 1
        total["faces"] += result["faces"]
        total["errors"] += len(result["errors"])
    return total


@shared_task
def sync_terminal_clocks() -> dict:
    """Beat task: keep device clocks aligned — drift corrupts attendance."""
    from .constants import IntegrationKind
    from .models import Terminal
    from .services.hikvision import HikvisionClient, HikvisionError
    from .services.registry import integration_config

    synced, failed = 0, 0
    for terminal in Terminal.objects.filter(is_active=True).select_related("school"):
        config = integration_config(IntegrationKind.TERMINALS, terminal.school)
        if not config.get("sync_device_time", True):
            continue
        try:
            with HikvisionClient.for_terminal(terminal) as client:
                client.sync_time()
            synced += 1
        except HikvisionError as error:
            terminal.mark_offline(str(error))
            failed += 1
    return {"synced": synced, "failed": failed}
