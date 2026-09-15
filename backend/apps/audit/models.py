from __future__ import annotations

from django.db import models

from apps.common.models import TimeStampedModel, UUIDModel

from .constants import AuditAction


class AuditLog(UUIDModel, TimeStampedModel):
    """Append-only record of security-relevant actions.

    Payload dictionaries are scrubbed by ``apps.audit.services.sanitize`` before
    they are stored: passwords, OTP codes, JWTs and JSHSHIR never land here.
    """

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    # Kept even when the user row is removed, so the trail survives.
    username = models.CharField(max_length=50, blank=True)
    action = models.CharField(max_length=40, choices=AuditAction.choices, db_index=True)
    entity_type = models.CharField(max_length=80, blank=True, db_index=True)
    entity_id = models.CharField(max_length=64, blank=True, db_index=True)
    old_data = models.JSONField(null=True, blank=True)
    new_data = models.JSONField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    success = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Audit yozuvi"
        verbose_name_plural = "Audit yozuvlari"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["action", "-created_at"]),
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["entity_type", "entity_id"]),
        ]

    def __str__(self) -> str:
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.action} {self.username or 'anonymous'}"
