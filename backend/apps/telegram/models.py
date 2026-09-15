from __future__ import annotations

from django.db import models
from django.utils import timezone

from apps.common.models import TimeStampedModel, UUIDModel


class TelegramAccount(UUIDModel, TimeStampedModel):
    """A Telegram chat bound to one account.

    A Telegram id alone is never treated as proof of identity: the row is only
    created after a one-time link token issued from the authenticated web UI
    has been redeemed.
    """

    user = models.OneToOneField(
        "accounts.User", on_delete=models.CASCADE, related_name="telegram_account"
    )
    telegram_id = models.BigIntegerField("Telegram ID", unique=True, db_index=True)
    telegram_username = models.CharField(max_length=64, blank=True)
    first_name = models.CharField(max_length=128, blank=True)
    last_name = models.CharField(max_length=128, blank=True)
    language_code = models.CharField(max_length=8, blank=True, default="uz")

    # Which child the bot currently talks about for this chat.
    active_student = models.ForeignKey(
        "students.Student",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="telegram_sessions",
    )
    notifications_enabled = models.BooleanField("Bildirishnomalar yoqilgan", default=True)
    is_active = models.BooleanField(default=True)
    linked_at = models.DateTimeField(default=timezone.now)
    last_interaction_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Telegram akkaunt"
        verbose_name_plural = "Telegram akkauntlar"
        ordering = ("-linked_at",)

    def __str__(self) -> str:
        return f"{self.user.username} ↔ {self.telegram_id}"

    def touch(self) -> None:
        self.last_interaction_at = timezone.now()
        self.save(update_fields=["last_interaction_at", "updated_at"])


class TelegramLinkToken(UUIDModel, TimeStampedModel):
    """Single-use, short-lived token that binds a Telegram chat to an account.

    Both the human-readable code and the deep-link token are stored hashed, so
    a database read cannot be replayed into an account takeover.
    """

    user = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="telegram_link_tokens"
    )
    code_hash = models.CharField(max_length=64, db_index=True, editable=False)
    token_hash = models.CharField(max_length=64, db_index=True, editable=False)
    expires_at = models.DateTimeField(db_index=True)
    used_at = models.DateTimeField(null=True, blank=True)
    used_by_telegram_id = models.BigIntegerField(null=True, blank=True)

    class Meta:
        verbose_name = "Telegram ulanish kodi"
        verbose_name_plural = "Telegram ulanish kodlari"
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["user", "-created_at"])]

    def __str__(self) -> str:
        return f"link-token for {self.user.username}"

    @property
    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at

    @property
    def is_used(self) -> bool:
        return self.used_at is not None

    @property
    def is_valid(self) -> bool:
        return not self.is_used and not self.is_expired
