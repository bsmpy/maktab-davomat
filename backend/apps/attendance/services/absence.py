"""Parent-submitted absence reasons ("Sabab bildirish") and their review.

A reason explains a whole day — attendance is measured at the gate, not per
lesson, so there is nothing finer to attach an explanation to.
"""
from __future__ import annotations

from datetime import date

from django.db import transaction
from django.utils import timezone

from apps.audit.constants import AuditAction
from apps.audit.services import log_action
from apps.common.exceptions import ConflictError

from ..constants import AbsenceRequestStatus
from ..models import AbsenceRequest


@transaction.atomic
def submit_absence_request(
    *,
    student,
    day: date,
    reason,
    comment: str = "",
    submitted_by,
) -> AbsenceRequest:
    if reason.requires_comment and not comment.strip():
        raise ConflictError("Bu sabab uchun izoh kiritish majburiy.", code="COMMENT_REQUIRED")
    if AbsenceRequest.objects.filter(
        student=student, date=day, status=AbsenceRequestStatus.PENDING
    ).exists():
        raise ConflictError(
            "Bu kun uchun ariza allaqachon yuborilgan va ko'rib chiqilmoqda.",
            code="ABSENCE_REQUEST_PENDING",
        )

    request = AbsenceRequest.objects.create(
        student=student,
        date=day,
        reason=reason,
        comment=comment,
        submitted_by=submitted_by,
        submitted_at=timezone.now(),
    )

    log_action(
        AuditAction.ABSENCE_REASON_SUBMIT,
        user=submitted_by,
        entity=request,
        new_data={"student": str(student.id), "date": day.isoformat(), "reason": reason.code},
    )
    return request


@transaction.atomic
def approve_absence_request(request: AbsenceRequest, *, reviewer, comment: str = "") -> AbsenceRequest:
    if request.status != AbsenceRequestStatus.PENDING:
        raise ConflictError("Ariza allaqachon ko'rib chiqilgan.", code="ALREADY_REVIEWED")

    request.status = AbsenceRequestStatus.APPROVED
    request.reviewed_by = reviewer
    request.reviewed_at = timezone.now()
    request.review_comment = comment
    request.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_comment", "updated_at"])

    log_action(AuditAction.ABSENCE_REASON_APPROVE, user=reviewer, entity=request)

    from apps.notifications.services import notify_absence_request_reviewed

    transaction.on_commit(lambda: notify_absence_request_reviewed(request))
    return request


@transaction.atomic
def reject_absence_request(request: AbsenceRequest, *, reviewer, comment: str = "") -> AbsenceRequest:
    if request.status != AbsenceRequestStatus.PENDING:
        raise ConflictError("Ariza allaqachon ko'rib chiqilgan.", code="ALREADY_REVIEWED")

    request.status = AbsenceRequestStatus.REJECTED
    request.reviewed_by = reviewer
    request.reviewed_at = timezone.now()
    request.review_comment = comment
    request.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_comment", "updated_at"])

    log_action(AuditAction.ABSENCE_REASON_REJECT, user=reviewer, entity=request)

    from apps.notifications.services import notify_absence_request_reviewed

    transaction.on_commit(lambda: notify_absence_request_reviewed(request))
    return request
