"""Celery tasks. Every task is safe to retry: the work behind it is idempotent."""
from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
    acks_late=True,
)
def notify_presence_event(self, event_id: str) -> int:
    """Tell the guardians that their child walked in or out of the building."""
    from apps.integrations.models import TerminalEvent

    from .services import notify_presence

    event = (
        TerminalEvent.objects.select_related(
            "student", "student__class_group", "student__class_group__grade",
            "student__school", "terminal",
        )
        .filter(pk=event_id)
        .first()
    )
    if event is None:
        logger.info("notify_presence_event: event %s no longer exists", event_id)
        return 0
    return len(notify_presence(event))


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
    acks_late=True,
)
def notify_attendance_event(self, attendance_id: str) -> int:
    """Create guardian notifications for one ABSENT/LATE attendance row."""
    from apps.attendance.models import Attendance

    from .services import notify_attendance

    attendance = (
        Attendance.objects.select_related(
            "student", "student__class_group", "student__class_group__grade", "lesson",
            "lesson__subject",
        )
        .filter(pk=attendance_id)
        .first()
    )
    if attendance is None:
        logger.info("notify_attendance_event: attendance %s no longer exists", attendance_id)
        return 0
    return len(notify_attendance(attendance))


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
    acks_late=True,
)
def deliver_telegram_notification(self, notification_id: str) -> bool:
    from .models import Notification
    from .services import deliver_to_telegram

    notification = (
        Notification.objects.select_related(
            "user", "student", "student__class_group", "student__class_group__grade"
        )
        .filter(pk=notification_id)
        .first()
    )
    if notification is None:
        return False
    delivery = deliver_to_telegram(notification)
    return delivery is not None


@shared_task
def generate_upcoming_lessons(days_ahead: int = 14) -> int:
    """Beat task: keep the timetable materialised a fortnight ahead."""
    from datetime import timedelta

    from apps.attendance.services.periods import today
    from apps.attendance.services.scheduling import generate_lessons
    from apps.schools.models import AcademicYear

    created = 0
    start = today()
    end = start + timedelta(days=days_ahead)
    for academic_year in AcademicYear.objects.filter(is_current=True).select_related("school"):
        window_start = max(start, academic_year.start_date)
        window_end = min(end, academic_year.end_date)
        if window_start <= window_end:
            created += generate_lessons(
                academic_year=academic_year, start=window_start, end=window_end
            )
    return created


@shared_task
def purge_expired_link_tokens() -> int:
    """Beat task: drop spent/expired Telegram link tokens."""
    from datetime import timedelta

    from django.utils import timezone

    from apps.telegram.models import TelegramLinkToken

    cutoff = timezone.now() - timedelta(days=1)
    deleted, _ = TelegramLinkToken.objects.filter(expires_at__lt=cutoff).delete()
    return deleted
