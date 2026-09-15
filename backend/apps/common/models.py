"""Cross-cutting models.

Mostly the reusable abstract bases — timestamps, UUID primary keys and soft
delete. ``AppearanceSettings`` at the foot is the one concrete model: it belongs
to the installation rather than to any one domain.
"""
from __future__ import annotations

import uuid

from django.db import models
from django.utils import timezone


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class UUIDModel(models.Model):
    """Public-facing entities use UUIDs so integer ids cannot be enumerated."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class SoftDeleteQuerySet(models.QuerySet):
    def alive(self):
        return self.filter(deleted_at__isnull=True)

    def dead(self):
        return self.filter(deleted_at__isnull=False)

    def delete(self):
        """Bulk soft delete. Use ``hard_delete()`` to really remove rows."""
        return self.update(deleted_at=timezone.now())

    def hard_delete(self):
        return super().delete()

    def restore(self):
        return self.update(deleted_at=None)


class SoftDeleteManager(models.Manager.from_queryset(SoftDeleteQuerySet)):
    """Default manager hiding soft-deleted rows."""

    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)


class AllObjectsManager(models.Manager.from_queryset(SoftDeleteQuerySet)):
    pass


class SoftDeleteModel(models.Model):
    """Historical data (students, guardians, classes) is never hard deleted.

    ``objects`` hides deleted rows; ``all_objects`` sees everything, which is
    what admin/audit tooling and the migration-safe FK targets need.
    """

    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)

    objects = SoftDeleteManager()
    all_objects = AllObjectsManager()

    class Meta:
        abstract = True

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def delete(self, using=None, keep_parents=False):  # noqa: D102 - soft delete
        self.deleted_at = timezone.now()
        self.save(using=using, update_fields=["deleted_at", "updated_at"])
        return (1, {self._meta.label: 1})

    def hard_delete(self, using=None, keep_parents=False):
        return super().delete(using=using, keep_parents=keep_parents)

    def restore(self):
        self.deleted_at = None
        self.save(update_fields=["deleted_at", "updated_at"])


class AppearanceSettings(models.Model):
    """Interface options that apply to everyone, held in one row.

    These were a per-browser preference in ``localStorage``, on the reasoning
    that how the screen looks is the choice of the person in front of it. That
    is no longer what is wanted: turning the extra palettes or the drifting
    particles off has to reach **every** signed-in person, not only the
    administrator who flipped the switch. So the switches say what the
    installation *offers*, and they live here.

    What stays personal is the palette someone then picks out of what is on
    offer — that is still their own browser's business.

    A single row on purpose: there is one installation, and the whole point is
    that the answer is the same for everybody. ``load()`` is the only way to
    reach it and creates it on first use, so there is no fixture to remember
    and no migration that has to insert data.
    """

    #: The only primary key this table ever holds.
    SINGLETON_PK = 1

    # No ``default`` on the key on purpose. With one, Django takes its "new
    # object with a generated pk" shortcut and goes straight to an INSERT, so a
    # second instance collides with the row instead of replacing it. Without one
    # it tries the UPDATE first and inserts only when nothing was there — which
    # is what a single-row table wants.
    id = models.PositiveSmallIntegerField(primary_key=True, editable=False)
    multi_theme = models.BooleanField(
        default=True,
        help_text="All five palettes on offer, or only light and dark.",
    )
    particles = models.BooleanField(
        default=True,
        help_text="The drifting motes over the interface.",
    )
    # Deliberately no ``created_at``: this row is created once and updated
    # forever after, and an ``auto_now_add`` column on a singleton is a trap —
    # saving a freshly constructed instance writes NULL over the stored value.
    updated_at = models.DateTimeField(auto_now=True)
    #: Who flipped a switch last. The audit trail is the record; this is the
    #: convenience copy on the row itself.
    updated_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        verbose_name = "appearance settings"
        verbose_name_plural = "appearance settings"

    def __str__(self) -> str:
        return "Appearance settings"

    def save(self, *args, **kwargs):
        """Pin the key, so a second row cannot be written by accident.

        Whoever constructs an instance — a serializer, a shell, a fixture —
        saves over the one row rather than beside it.
        """
        self.pk = self.SINGLETON_PK
        super().save(*args, **kwargs)

    @classmethod
    def load(cls) -> AppearanceSettings:
        """The row, created with the defaults the first time it is asked for."""
        settings_row, _ = cls.objects.get_or_create(pk=cls.SINGLETON_PK)
        return settings_row
