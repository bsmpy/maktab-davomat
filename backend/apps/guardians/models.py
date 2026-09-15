from __future__ import annotations

from django.db import models
from django.utils import timezone

from apps.common.crypto import encrypt, hash_value, mask_jshshir, mask_phone, normalize_jshshir
from apps.common.models import (
    SoftDeleteModel,
    SoftDeleteQuerySet,
    TimeStampedModel,
    UUIDModel,
)
from apps.common.phone import normalize_phone
from apps.common.text import normalize_name, transliterate

from .constants import Relation


class GuardianQuerySet(SoftDeleteQuerySet):
    """Soft-delete semantics, same as ``StudentQuerySet``."""

    def active(self):
        return self.filter(is_active=True, deleted_at__isnull=True)

    def claimed(self):
        """Guardians that already own a login."""
        return self.filter(user__isnull=False)


class GuardianManager(models.Manager.from_queryset(GuardianQuerySet)):
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)

    def find_by_jshshir(self, raw_jshshir: str):
        """Constant-shape lookup by peppered hash – the plaintext is never queried."""
        return self.get_queryset().filter(jshshir_hash=hash_value(normalize_jshshir(raw_jshshir)))


class Guardian(UUIDModel, TimeStampedModel, SoftDeleteModel):
    """A parent/guardian as recorded by the school *before* they register.

    Registration matches an applicant against this registry; the phone number
    used for OTP always comes from here, never from user input.
    """

    school = models.ForeignKey("schools.School", on_delete=models.PROTECT, related_name="guardians")
    user = models.OneToOneField(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="guardian_profile",
        verbose_name="Akkaunt",
    )

    first_name = models.CharField("Ism", max_length=100)
    last_name = models.CharField("Familiya", max_length=100)
    middle_name = models.CharField("Otasining ismi", max_length=100, blank=True)
    search_name = models.CharField(max_length=320, blank=True, editable=False, db_index=True)

    phone = models.CharField(
        "Telefon", max_length=20, db_index=True, help_text="E.164, masalan +998901234567"
    )
    extra_phone = models.CharField("Qo'shimcha telefon", max_length=20, blank=True)

    # Sensitive identifier, stored hashed (for lookup) + encrypted (for admins).
    jshshir_hash = models.CharField(max_length=64, db_index=True, editable=False)
    jshshir_encrypted = models.TextField(editable=False)
    jshshir_last4 = models.CharField(max_length=4, editable=False)

    is_active = models.BooleanField("Faol", default=True)

    students = models.ManyToManyField(
        "students.Student",
        through="guardians.GuardianStudent",
        related_name="guardians",
        blank=True,
    )

    objects = GuardianManager()
    all_objects = models.Manager.from_queryset(GuardianQuerySet)()

    class Meta:
        verbose_name = "Ota-ona / vasiy"
        verbose_name_plural = "Ota-onalar va vasiylar"
        ordering = ("last_name", "first_name")
        constraints = [
            models.UniqueConstraint(
                fields=["school", "jshshir_hash"],
                condition=models.Q(deleted_at__isnull=True),
                name="uniq_guardian_jshshir_per_school",
            ),
        ]
        indexes = [models.Index(fields=["school", "is_active"])]

    def __str__(self) -> str:
        return self.full_name

    def save(self, *args, **kwargs):
        self.first_name = normalize_name(self.first_name)
        self.last_name = normalize_name(self.last_name)
        self.middle_name = normalize_name(self.middle_name)
        self.search_name = transliterate(f"{self.last_name} {self.first_name} {self.middle_name}")
        if self.phone:
            self.phone = normalize_phone(self.phone)
        if self.extra_phone:
            self.extra_phone = normalize_phone(self.extra_phone)
        super().save(*args, **kwargs)

    @property
    def full_name(self) -> str:
        return " ".join(
            part for part in (self.last_name, self.first_name, self.middle_name) if part
        )

    @property
    def jshshir(self) -> str:
        """The number itself, decrypted.

        The cabinet shows it in full to the people who administer the register
        and to its owner. It stays encrypted at rest and out of every anonymous
        surface, but anyone who can read these endpoints can read the number —
        the ciphertext protects the database, not the API.
        """
        from apps.common.crypto import decrypt

        return decrypt(self.jshshir_encrypted) or ""

    @property
    def masked_jshshir(self) -> str:
        return mask_jshshir(self.jshshir_last4)

    @property
    def masked_phone(self) -> str:
        return mask_phone(self.phone)

    @property
    def has_account(self) -> bool:
        return self.user_id is not None

    def set_jshshir(self, raw: str) -> None:
        value = normalize_jshshir(raw)
        self.jshshir_hash = hash_value(value)
        self.jshshir_encrypted = encrypt(value)
        self.jshshir_last4 = value[-4:]

    def matches_jshshir(self, raw: str) -> bool:
        try:
            return self.jshshir_hash == hash_value(normalize_jshshir(raw))
        except ValueError:
            return False


class GuardianStudent(UUIDModel, TimeStampedModel):
    """Many-to-many link table.

    One guardian may have several children and one child may have several
    guardians, so the relationship carries its own attributes (kinship,
    primary contact flag, verification state).
    """

    guardian = models.ForeignKey(
        Guardian, on_delete=models.CASCADE, related_name="student_links"
    )
    student = models.ForeignKey(
        "students.Student", on_delete=models.CASCADE, related_name="guardian_links"
    )
    relation = models.CharField("Qarindoshligi", max_length=20, choices=Relation.choices)
    is_primary = models.BooleanField("Asosiy vakil", default=False)
    verified = models.BooleanField("Tasdiqlangan", default=False, db_index=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    # Whether this link should raise Telegram/push notifications.
    notifications_enabled = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Ota-ona — o'quvchi bog'lanishi"
        verbose_name_plural = "Ota-ona — o'quvchi bog'lanishlari"
        ordering = ("-is_primary", "student__last_name")
        constraints = [
            models.UniqueConstraint(
                fields=["guardian", "student"], name="uniq_guardian_student_link"
            ),
            models.UniqueConstraint(
                fields=["student"],
                condition=models.Q(is_primary=True),
                name="uniq_primary_guardian_per_student",
            ),
        ]
        indexes = [
            models.Index(fields=["student", "verified"]),
            models.Index(fields=["guardian", "verified"]),
        ]

    def __str__(self) -> str:
        return f"{self.guardian.full_name} → {self.student.full_name} ({self.get_relation_display()})"

    def mark_verified(self) -> None:
        if not self.verified:
            self.verified = True
            self.verified_at = timezone.now()
            self.save(update_fields=["verified", "verified_at", "updated_at"])
