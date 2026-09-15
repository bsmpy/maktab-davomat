from __future__ import annotations

from django.contrib.postgres.indexes import GinIndex
from django.db import models
from django.db.models.functions import Lower

from apps.common.crypto import encrypt, hash_value, mask_jshshir, normalize_jshshir
from apps.common.models import (
    SoftDeleteModel,
    SoftDeleteQuerySet,
    TimeStampedModel,
    UUIDModel,
)
from apps.common.text import normalize_name, transliterate


class Gender(models.TextChoices):
    MALE = "MALE", "O'g'il bola"
    FEMALE = "FEMALE", "Qiz bola"


class StudentQuerySet(SoftDeleteQuerySet):
    """Inherits the soft-delete semantics: a bulk ``.delete()`` stamps
    ``deleted_at`` rather than dropping rows, so attendance history survives an
    accidental mass delete from the admin. Use ``.hard_delete()`` to really
    remove them."""

    def active(self):
        return self.filter(is_active=True, deleted_at__isnull=True)

    def for_class_group(self, class_group_id):
        return self.filter(class_group_id=class_group_id)

    def with_class(self):
        return self.select_related("class_group", "class_group__grade", "school")


class StudentManager(models.Manager.from_queryset(StudentQuerySet)):
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)


class Student(UUIDModel, TimeStampedModel, SoftDeleteModel):
    """A pupil. Never exposed in bulk through any public endpoint."""

    school = models.ForeignKey("schools.School", on_delete=models.PROTECT, related_name="students")
    class_group = models.ForeignKey(
        "schools.ClassGroup", on_delete=models.PROTECT, related_name="students"
    )

    first_name = models.CharField("Ism", max_length=100)
    last_name = models.CharField("Familiya", max_length=100)
    middle_name = models.CharField("Otasining ismi", max_length=100, blank=True)

    # Latin-folded lowercase full name; the only field the search filter touches
    # so that Cyrillic/Latin spellings both match.
    search_name = models.CharField(max_length=320, blank=True, editable=False, db_index=True)

    birth_date = models.DateField("Tug'ilgan sana", null=True, blank=True)
    gender = models.CharField("Jinsi", max_length=10, choices=Gender.choices, blank=True)

    student_code = models.CharField(
        "O'quvchi kodi",
        max_length=32,
        blank=True,
        help_text="Maktab jurnalidagi raqam. Ro'yxatdan o'tishda qo'shimcha identifikator.",
    )

    # Sensitive: stored hashed + encrypted, never returned by any serializer.
    jshshir_hash = models.CharField(max_length=64, blank=True, db_index=True, editable=False)
    jshshir_encrypted = models.TextField(blank=True, editable=False)
    jshshir_last4 = models.CharField(max_length=4, blank=True, editable=False)

    # Enrolled into the turnstile's face library; see apps/integrations.
    photo = models.ImageField(
        "Rasm", upload_to="students/photos/%Y/%m/", null=True, blank=True,
        help_text="Face ID uchun ishlatiladi. Yuz aniq va to'liq ko'rinishi kerak.",
    )

    enrolled_on = models.DateField("O'qishga qabul qilingan", null=True, blank=True)
    is_active = models.BooleanField("Faol", default=True)

    objects = StudentManager()
    all_objects = models.Manager.from_queryset(StudentQuerySet)()

    class Meta:
        verbose_name = "O'quvchi"
        verbose_name_plural = "O'quvchilar"
        ordering = ("last_name", "first_name")
        indexes = [
            models.Index(fields=["class_group", "is_active"]),
            models.Index(fields=["school", "is_active"]),
            # Trigram index backing the fuzzy registration search.
            GinIndex(
                fields=["search_name"],
                name="student_search_name_trgm",
                opclasses=["gin_trgm_ops"],
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                Lower("student_code"),
                "school",
                condition=~models.Q(student_code=""),
                name="uniq_student_code_per_school",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.full_name} ({self.class_group.display_name})"

    def save(self, *args, **kwargs):
        self.first_name = normalize_name(self.first_name)
        self.last_name = normalize_name(self.last_name)
        self.middle_name = normalize_name(self.middle_name)
        self.search_name = transliterate(
            " ".join(part for part in (self.last_name, self.first_name, self.middle_name) if part)
        )
        if self.class_group_id and not self.school_id:
            self.school_id = self.class_group.school_id
        super().save(*args, **kwargs)

    # --- naming -------------------------------------------------------- #
    @property
    def full_name(self) -> str:
        return " ".join(
            part for part in (self.last_name, self.first_name, self.middle_name) if part
        )

    @property
    def display_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def initials(self) -> str:
        first = self.first_name[:1].upper() if self.first_name else ""
        last = self.last_name[:1].upper() if self.last_name else ""
        return f"{first}{last}"

    @property
    def masked_full_name(self) -> str:
        """``Valiyev A.`` – what the public registration search returns."""
        initial = f"{self.first_name[0]}." if self.first_name else ""
        return f"{self.last_name} {initial}".strip()

    # --- sensitive data ------------------------------------------------- #
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

    def set_jshshir(self, raw: str | None) -> None:
        if not raw:
            self.jshshir_hash = ""
            self.jshshir_encrypted = ""
            self.jshshir_last4 = ""
            return
        value = normalize_jshshir(raw)
        self.jshshir_hash = hash_value(value)
        self.jshshir_encrypted = encrypt(value)
        self.jshshir_last4 = value[-4:]
