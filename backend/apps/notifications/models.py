from __future__ import annotations

from django.db import models
from django.utils import timezone

from apps.common.models import TimeStampedModel, UUIDModel

from .constants import DeliveryStatus, NotificationChannel, NotificationType


class NotificationQuerySet(models.QuerySet):
    def unread(self):
        return self.filter(is_read=False)

    def for_user(self, user):
        return self.filter(user=user)

    def with_student(self):
        return self.select_related("student", "student__class_group", "student__class_group__grade")


class Notification(UUIDModel, TimeStampedModel):
    """An in-app notification. Delivery to other channels is tracked separately."""

    user = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="notifications"
    )
    student = models.ForeignKey(
        "students.Student",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications",
    )
    type = models.CharField("Turi", max_length=40, choices=NotificationType.choices, db_index=True)
    title = models.CharField("Sarlavha", max_length=200)
    message = models.TextField("Matn")
    payload = models.JSONField("Qo'shimcha ma'lumot", default=dict, blank=True)

    is_read = models.BooleanField("O'qilgan", default=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)

    # Idempotency key: the same real-world event never produces two rows.
    dedupe_key = models.CharField(max_length=200, blank=True, editable=False)

    objects = NotificationQuerySet.as_manager()

    class Meta:
        verbose_name = "Bildirishnoma"
        verbose_name_plural = "Bildirishnomalar"
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=["user", "dedupe_key"],
                condition=~models.Q(dedupe_key=""),
                name="uniq_notification_dedupe_per_user",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "is_read", "-created_at"]),
            models.Index(fields=["user", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.get_type_display()} → {self.user.username}"

    def mark_read(self) -> None:
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=["is_read", "read_at", "updated_at"])


class NotificationDelivery(UUIDModel, TimeStampedModel):
    """Per-channel delivery attempt, unique per (notification, channel).

    The unique constraint is what makes retries idempotent: a re-queued Celery
    task can never send the same Telegram message twice.
    """

    notification = models.ForeignKey(
        Notification, on_delete=models.CASCADE, related_name="deliveries"
    )
    channel = models.CharField(max_length=20, choices=NotificationChannel.choices)
    status = models.CharField(
        max_length=20, choices=DeliveryStatus.choices, default=DeliveryStatus.PENDING
    )
    sent_at = models.DateTimeField(null=True, blank=True)
    external_id = models.CharField(max_length=100, blank=True)
    error = models.CharField(max_length=255, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "Yuborish urinishi"
        verbose_name_plural = "Yuborish urinishlari"
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=["notification", "channel"], name="uniq_delivery_per_channel"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.channel}: {self.status}"
