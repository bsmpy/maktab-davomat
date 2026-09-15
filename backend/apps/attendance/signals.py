"""Attendance signals: history trail + notification fan-out.

The heavy lifting (creating notifications, pushing Telegram messages) is done
by Celery tasks so marking a register stays fast; the tasks are idempotent, so
a retry never double-notifies.
"""
from __future__ import annotations

from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from apps.audit.constants import AuditAction
from apps.audit.services import log_action, model_snapshot

from .constants import AttendanceStatus
from .models import Attendance, AttendanceHistory

_TRACKED_FIELDS = ("status", "late_minutes", "reason_id", "comment")


@receiver(pre_save, sender=Attendance)
def remember_previous_state(sender, instance: Attendance, **kwargs):
    if instance._state.adding or not instance.pk:
        instance._previous = None
        return
    instance._previous = (
        Attendance.objects.filter(pk=instance.pk)
        .values("status", "late_minutes", "reason_id", "comment")
        .first()
    )


@receiver(post_save, sender=Attendance)
def record_history_and_notify(sender, instance: Attendance, created: bool, **kwargs):
    previous = getattr(instance, "_previous", None)
    changed = created or (
        previous is not None
        and any(previous[field] != getattr(instance, field) for field in _TRACKED_FIELDS)
    )
    if not changed:
        return

    AttendanceHistory.objects.create(
        attendance=instance,
        changed_by=instance.marked_by,
        old_status=(previous or {}).get("status", "") or "",
        new_status=instance.status,
        old_late_minutes=(previous or {}).get("late_minutes", 0) or 0,
        new_late_minutes=instance.late_minutes,
    )

    log_action(
        AuditAction.ATTENDANCE_CREATE if created else AuditAction.ATTENDANCE_UPDATE,
        user=instance.marked_by,
        entity=instance,
        old_data=previous,
        new_data={field: getattr(instance, field) for field in _TRACKED_FIELDS},
        metadata={"student_id": str(instance.student_id), "date": instance.date.isoformat()},
    )

    status_changed = created or (previous or {}).get("status") != instance.status
    if status_changed and instance.status in (AttendanceStatus.ABSENT, AttendanceStatus.LATE):
        from apps.notifications.tasks import notify_attendance_event

        transaction.on_commit(
            lambda: notify_attendance_event.delay(str(instance.pk))
        )


@receiver(post_delete, sender=Attendance)
def audit_attendance_delete(sender, instance: Attendance, **kwargs):
    """Individual deletions are audited row by row.

    Bulk maintenance (reseeding, archiving a year) must wrap the delete in
    ``apps.audit.services.suppressed`` — otherwise every row would emit its own
    INSERT.
    """
    log_action(
        AuditAction.ATTENDANCE_DELETE,
        entity_type=Attendance._meta.label,
        entity_id=str(instance.pk),
        old_data=model_snapshot(instance, fields=_TRACKED_FIELDS + ("date",)),
    )
