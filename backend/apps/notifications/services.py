"""Notification creation + fan-out.

Idempotency is enforced by two unique constraints rather than by application
bookkeeping:

* ``Notification(user, dedupe_key)`` — the same real-world event yields one row.
* ``NotificationDelivery(notification, channel)`` — one send per channel.

So a retried Celery task, a re-saved attendance row, or two workers racing all
converge on a single message.
"""
from __future__ import annotations

import logging

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.attendance.constants import AbsenceRequestStatus, AttendanceStatus

from .constants import NotificationChannel, NotificationType
from .models import Notification, NotificationDelivery

logger = logging.getLogger(__name__)

_STATUS_EMOJI = {
    AttendanceStatus.PRESENT: "✅",
    AttendanceStatus.ABSENT: "❌",
    AttendanceStatus.LATE: "🟡",
    AttendanceStatus.EXCUSED: "🔵",
}


def create_notification(
    *,
    user,
    notification_type: str,
    title: str,
    message: str,
    student=None,
    payload: dict | None = None,
    dedupe_key: str = "",
) -> tuple[Notification, bool]:
    """Create (or fetch) a notification. Returns ``(notification, created)``."""
    if dedupe_key:
        existing = Notification.objects.filter(user=user, dedupe_key=dedupe_key).first()
        if existing is not None:
            return existing, False
    try:
        with transaction.atomic():
            notification = Notification.objects.create(
                user=user,
                student=student,
                type=notification_type,
                title=title,
                message=message,
                payload=payload or {},
                dedupe_key=dedupe_key,
            )
        return notification, True
    except IntegrityError:
        # Lost the race against a concurrent worker — reuse its row.
        return Notification.objects.get(user=user, dedupe_key=dedupe_key), False


def recipients_for_student(student):
    """Verified guardians of the pupil who own an account and want alerts."""
    from apps.guardians.models import GuardianStudent

    links = (
        GuardianStudent.objects.filter(
            student=student,
            verified=True,
            notifications_enabled=True,
            guardian__user__isnull=False,
            guardian__is_active=True,
            guardian__deleted_at__isnull=True,
        )
        .select_related("guardian", "guardian__user")
    )
    return [link.guardian.user for link in links if link.guardian.user.is_active]


# --------------------------------------------------------------------------- #
# Attendance events
# --------------------------------------------------------------------------- #
def build_attendance_message(attendance) -> tuple[str, str, str]:
    """Returns ``(notification_type, title, message)``."""
    student = attendance.student
    lesson = attendance.lesson
    subject = lesson.subject.name
    when = lesson.start_time.strftime("%H:%M")

    if attendance.status == AttendanceStatus.LATE:
        return (
            NotificationType.ATTENDANCE_LATE,
            f"{student.display_name} darsga kechikdi",
            f"{subject} darsiga {attendance.late_minutes} daqiqa kechikdi "
            f"({attendance.date:%d.%m.%Y}, {when}).",
        )
    return (
        NotificationType.ATTENDANCE_ABSENT,
        f"{student.display_name} darsga kelmadi",
        f"{when} dagi {subject} darsiga kelmadi ({attendance.date:%d.%m.%Y}).",
    )


def notify_attendance(attendance) -> list[Notification]:
    """Fan an ABSENT/LATE mark out to every verified guardian."""
    if attendance.status not in (AttendanceStatus.ABSENT, AttendanceStatus.LATE):
        return []

    notification_type, title, message = build_attendance_message(attendance)
    dedupe_key = f"attendance:{attendance.id}:{attendance.status}"
    created: list[Notification] = []

    for user in recipients_for_student(attendance.student):
        notification, is_new = create_notification(
            user=user,
            notification_type=notification_type,
            title=title,
            message=message,
            student=attendance.student,
            payload={
                "attendance_id": str(attendance.id),
                "student_id": str(attendance.student_id),
                "date": attendance.date.isoformat(),
                "lesson": attendance.lesson.subject.name,
                "status": attendance.status,
                "late_minutes": attendance.late_minutes,
                "emoji": _STATUS_EMOJI.get(attendance.status, ""),
            },
            dedupe_key=dedupe_key,
        )
        if is_new:
            created.append(notification)
            queue_telegram_delivery(notification)
    return created


# --------------------------------------------------------------------------- #
# Turnstile events — the pupil walked in or out of the building
# --------------------------------------------------------------------------- #
def build_presence_message(event) -> tuple[str, str, str, str]:
    """Returns ``(notification_type, title, message, emoji)`` for one pass."""
    from apps.integrations.constants import EventDirection

    student = event.student
    when = timezone.localtime(event.occurred_at).strftime("%H:%M")
    where = event.terminal.location or event.terminal.name

    if event.direction == EventDirection.IN:
        return (
            NotificationType.SCHOOL_ENTRY,
            f"{student.display_name} maktabga kirdi",
            f"{when} da maktabga kirdi ({where}).",
            "🟢",
        )
    return (
        NotificationType.SCHOOL_EXIT,
        f"{student.display_name} maktabdan chiqdi",
        f"{when} da maktabdan chiqdi ({where}).",
        "🔴",
    )


def notify_presence(event) -> list[Notification]:
    """Fan one turnstile pass out to every verified guardian.

    The dedupe key is the event itself, so a device resync or a retried task
    can never produce a second message for the same pass.
    """
    from apps.integrations.constants import EventDirection, IntegrationKind
    from apps.integrations.services.registry import integration_config

    if event.direction not in (EventDirection.IN, EventDirection.OUT):
        return []
    if event.student is None:
        return []

    config = integration_config(IntegrationKind.TELEGRAM_BOT, event.student.school)
    wanted = "send_entry" if event.direction == EventDirection.IN else "send_exit"
    if not config.get(wanted, True):
        return []

    notification_type, title, message, emoji = build_presence_message(event)
    dedupe_key = f"presence:{event.id}"
    created: list[Notification] = []

    for user in recipients_for_student(event.student):
        notification, is_new = create_notification(
            user=user,
            notification_type=notification_type,
            title=title,
            message=message,
            student=event.student,
            payload={
                "event_id": str(event.id),
                "student_id": str(event.student_id),
                "date": event.date.isoformat(),
                "occurred_at": event.occurred_at.isoformat(),
                "direction": event.direction,
                "terminal": event.terminal.name,
                "emoji": emoji,
            },
            dedupe_key=dedupe_key,
        )
        if is_new:
            created.append(notification)
            queue_telegram_delivery(notification)
    return created


def notify_absence_request_reviewed(absence_request) -> list[Notification]:
    approved = absence_request.status == AbsenceRequestStatus.APPROVED
    notification_type = (
        NotificationType.ABSENCE_REASON_APPROVED
        if approved
        else NotificationType.ABSENCE_REASON_REJECTED
    )
    student = absence_request.student
    verdict = "tasdiqlandi" if approved else "rad etildi"
    message = (
        f"{absence_request.date:%d.%m.%Y} uchun yuborilgan sabab "
        f"({absence_request.reason.name}) {verdict}."
    )
    if absence_request.review_comment:
        message += f"\nIzoh: {absence_request.review_comment}"

    created = []
    for user in recipients_for_student(student):
        notification, is_new = create_notification(
            user=user,
            notification_type=notification_type,
            title=f"Sabab {verdict}",
            message=message,
            student=student,
            payload={
                "absence_request_id": str(absence_request.id),
                "date": absence_request.date.isoformat(),
                "status": absence_request.status,
            },
            dedupe_key=f"absence_request:{absence_request.id}:{absence_request.status}",
        )
        if is_new:
            created.append(notification)
            queue_telegram_delivery(notification)
    return created


def create_announcement(*, users, title: str, message: str, key: str = "") -> list[Notification]:
    created = []
    for user in users:
        notification, is_new = create_notification(
            user=user,
            notification_type=NotificationType.ANNOUNCEMENT,
            title=title,
            message=message,
            dedupe_key=f"announcement:{key}" if key else "",
        )
        if is_new:
            created.append(notification)
            queue_telegram_delivery(notification)
    return created


# --------------------------------------------------------------------------- #
# Delivery
# --------------------------------------------------------------------------- #
def queue_telegram_delivery(notification: Notification) -> None:
    """Schedule the Telegram push after the surrounding transaction commits."""
    from .tasks import deliver_telegram_notification

    notification_id = str(notification.id)
    transaction.on_commit(lambda: deliver_telegram_notification.delay(notification_id))


def deliver_to_telegram(notification: Notification) -> NotificationDelivery | None:
    """Send one notification to Telegram, exactly once."""
    from apps.telegram.models import TelegramAccount
    from apps.telegram.services import TelegramError, send_message

    from .constants import DeliveryStatus

    account = TelegramAccount.objects.filter(
        user=notification.user, is_active=True, notifications_enabled=True
    ).first()
    if account is None:
        return None

    delivery, created = NotificationDelivery.objects.get_or_create(
        notification=notification,
        channel=NotificationChannel.TELEGRAM,
        defaults={"status": DeliveryStatus.PENDING},
    )
    if not created and delivery.status == DeliveryStatus.SENT:
        return delivery  # already delivered — nothing to do

    emoji = notification.payload.get("emoji", "🔔")
    student_line = ""
    if notification.student_id:
        student = notification.student
        student_line = (
            f"👦 <b>{student.display_name}</b>\n"
            f"🏫 {student.class_group.display_name}\n\n"
        )
    text = f"{emoji} <b>{notification.title}</b>\n\n{student_line}{notification.message}"

    delivery.attempts += 1
    try:
        result = send_message(account.telegram_id, text)
    except TelegramError as exc:
        delivery.status = DeliveryStatus.FAILED
        delivery.error = str(exc)[:255]
        if exc.blocked:
            account.is_active = False
            account.save(update_fields=["is_active", "updated_at"])
            delivery.status = DeliveryStatus.SKIPPED
        delivery.save(update_fields=["status", "error", "attempts", "updated_at"])
        logger.warning("Telegram delivery failed for notification=%s", notification.id)
        return delivery

    delivery.status = DeliveryStatus.SENT
    delivery.sent_at = timezone.now()
    delivery.external_id = str(result.get("message_id", ""))
    delivery.error = ""
    delivery.save(
        update_fields=["status", "sent_at", "external_id", "error", "attempts", "updated_at"]
    )
    return delivery
