from __future__ import annotations

from django.contrib.postgres.fields import ArrayField
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models.functions import Lower

from apps.common.crypto import encrypt, hash_value, mask_jshshir, normalize_jshshir
from apps.common.models import SoftDeleteModel, TimeStampedModel, UUIDModel
from apps.common.passport import mask_passport_id
from apps.common.text import normalize_name

from .constants import GRADE_MAX, GRADE_MIN, Weekday


class School(UUIDModel, TimeStampedModel, SoftDeleteModel):
    name = models.CharField("Nomi", max_length=255)
    short_name = models.CharField("Qisqa nomi", max_length=64, blank=True)
    region = models.CharField("Viloyat", max_length=120, blank=True)
    district = models.CharField("Tuman", max_length=120, blank=True)
    address = models.CharField("Manzil", max_length=255, blank=True)
    phone = models.CharField("Telefon", max_length=20, blank=True)
    logo = models.ImageField(
        "Logotip", upload_to="schools/logos/", null=True, blank=True
    )
    # ISO weekdays that are school days by default (Mon=1 ... Sun=7).
    working_weekdays = ArrayField(
        models.PositiveSmallIntegerField(choices=Weekday.choices),
        default=list,
        blank=True,
        verbose_name="Ish kunlari",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Maktab"
        verbose_name_plural = "Maktablar"
        ordering = ("name",)

    def __str__(self) -> str:
        return self.short_name or self.name

    def save(self, *args, **kwargs):
        if not self.working_weekdays:
            self.working_weekdays = [1, 2, 3, 4, 5, 6]
        super().save(*args, **kwargs)

    def is_working_weekday(self, iso_weekday: int) -> bool:
        return iso_weekday in (self.working_weekdays or [1, 2, 3, 4, 5, 6])


class AcademicYear(UUIDModel, TimeStampedModel):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="academic_years")
    name = models.CharField("Nomi", max_length=32, help_text="Masalan: 2026-2027")
    start_date = models.DateField("Boshlanish sanasi")
    end_date = models.DateField("Tugash sanasi")
    is_current = models.BooleanField("Joriy", default=False, db_index=True)

    class Meta:
        verbose_name = "O'quv yili"
        verbose_name_plural = "O'quv yillari"
        ordering = ("-start_date",)
        constraints = [
            models.UniqueConstraint(fields=["school", "name"], name="uniq_academic_year_per_school"),
            models.UniqueConstraint(
                fields=["school"],
                condition=models.Q(is_current=True),
                name="uniq_current_academic_year_per_school",
            ),
            models.CheckConstraint(
                check=models.Q(end_date__gt=models.F("start_date")),
                name="academic_year_end_after_start",
            ),
        ]

    def __str__(self) -> str:
        return self.name

    def contains(self, value) -> bool:
        return self.start_date <= value <= self.end_date


class Grade(UUIDModel, TimeStampedModel, SoftDeleteModel):
    """A parallel (1..11). Class groups hang off it, so nothing is hardcoded."""

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="grades")
    level = models.PositiveSmallIntegerField(
        "Sinf",
        validators=[MinValueValidator(GRADE_MIN), MaxValueValidator(GRADE_MAX)],
    )

    class Meta:
        verbose_name = "Sinf (parallel)"
        verbose_name_plural = "Sinflar (parallellar)"
        ordering = ("level",)
        constraints = [
            models.UniqueConstraint(
                fields=["school", "level"],
                condition=models.Q(deleted_at__isnull=True),
                name="uniq_grade_per_school",
            ),
            models.CheckConstraint(
                check=models.Q(level__gte=GRADE_MIN, level__lte=GRADE_MAX),
                name="grade_level_in_range",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.level}-sinf"

    @property
    def label(self) -> str:
        return f"{self.level}-sinf"

    @property
    def display_name(self) -> str:
        return str(self.level)


class ClassGroup(UUIDModel, TimeStampedModel, SoftDeleteModel):
    """A concrete class such as ``7-A`` inside one academic year."""

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="class_groups")
    academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.PROTECT, related_name="class_groups"
    )
    grade = models.ForeignKey(Grade, on_delete=models.PROTECT, related_name="class_groups")
    name = models.CharField("Guruh", max_length=8, help_text="Masalan: A, B, D")
    homeroom_teacher = models.ForeignKey(
        "schools.Teacher",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="homeroom_class_groups",
        verbose_name="Sinf rahbari",
    )
    room = models.CharField("Xona", max_length=32, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Sinf guruhi"
        verbose_name_plural = "Sinf guruhlari"
        ordering = ("grade__level", "name")
        constraints = [
            models.UniqueConstraint(
                Lower("name"),
                "academic_year",
                "grade",
                condition=models.Q(deleted_at__isnull=True),
                name="uniq_class_group_per_grade_year",
            ),
        ]
        indexes = [models.Index(fields=["school", "is_active"])]

    def __str__(self) -> str:
        return self.display_name

    def save(self, *args, **kwargs):
        self.name = (self.name or "").strip().upper()
        if self.grade_id and not self.school_id:
            self.school_id = self.grade.school_id
        super().save(*args, **kwargs)

    @property
    def display_name(self) -> str:
        """``7-A`` – the label rendered everywhere in the UI."""
        return f"{self.grade.level}-{self.name}"


class Subject(UUIDModel, TimeStampedModel, SoftDeleteModel):
    """A subject as it is taught to one class group — "Matematika" in 1-A.

    The same name recurs across the register, so the class group is what tells
    two rows apart; everything the user sees says ``Matematika 1-A``.
    """

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="subjects")
    class_group = models.ForeignKey(
        ClassGroup,
        on_delete=models.CASCADE,
        related_name="subjects",
        null=True,
        blank=True,
        verbose_name="Sinf guruhi",
    )
    name = models.CharField("Nomi", max_length=120)
    short_name = models.CharField("Qisqa nomi", max_length=32, blank=True)
    color = models.CharField("Rang", max_length=9, blank=True, help_text="#RRGGBB")
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Fan"
        verbose_name_plural = "Fanlar"
        ordering = ("class_group__grade__level", "class_group__name", "name")
        constraints = [
            # Both are scoped to the living rows: deleting "Matematika 1-A"
            # must not make that name unusable for good.
            models.UniqueConstraint(
                Lower("name"),
                "class_group",
                condition=models.Q(deleted_at__isnull=True),
                name="uniq_subject_name_per_class_group",
            ),
            # Rows kept from before class groups existed, and any school-wide
            # subject: Postgres treats NULLs as distinct, so they need their own.
            models.UniqueConstraint(
                Lower("name"),
                "school",
                condition=models.Q(deleted_at__isnull=True, class_group__isnull=True),
                name="uniq_subject_name_per_school",
            ),
        ]

    def __str__(self) -> str:
        return self.display_name

    @property
    def display_name(self) -> str:
        """``Matematika 1-A`` – the label rendered everywhere in the UI."""
        if self.class_group_id is None:
            return self.name
        return f"{self.name} {self.class_group.display_name}"


class StaffGender(models.TextChoices):
    """Adults, so the wording differs from the pupils' one."""

    MALE = "MALE", "Erkak"
    FEMALE = "FEMALE", "Ayol"


class PersonRecord(models.Model):
    """The shared half of an adult's record: who they are and their documents.

    A teacher and a staff member are the same kind of row — the same name,
    passport, JSHSHIR, birth date, gender, phone and email, entered on the same
    form and validated the same way. What differs is what they do: a teacher
    has subjects, a staff member has a position. Keeping the common half here
    means the JSHSHIR's three-way storage is written once rather than copied.

    Abstract, so each concrete model still owns its own table, its own unique
    constraints and its own photo directory.
    """

    first_name = models.CharField("Ism", max_length=100)
    last_name = models.CharField("Familiya", max_length=100)
    middle_name = models.CharField("Otasining ismi", max_length=100, blank=True)
    #: Two uppercase Latin letters + seven digits, e.g. ``AA1234567``.
    passport_id = models.CharField("Passport ID", max_length=9, blank=True)
    # JSHSHIR is personal data: kept the same way as a guardian's — a peppered
    # hash for lookups, Fernet ciphertext for the rare privileged read, and the
    # last four digits so a human can recognise the row.
    jshshir_hash = models.CharField(max_length=64, blank=True, db_index=True, editable=False)
    jshshir_encrypted = models.TextField(blank=True, editable=False)
    jshshir_last4 = models.CharField(max_length=4, blank=True, editable=False)
    birth_date = models.DateField("Tug'ilgan sana", null=True, blank=True)
    gender = models.CharField(
        "Jinsi", max_length=10, choices=StaffGender.choices, blank=True
    )
    phone = models.CharField("Telefon", max_length=20, blank=True)
    email = models.EmailField("Email", max_length=254, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        abstract = True

    def __str__(self) -> str:
        return self.full_name

    def save(self, *args, **kwargs):
        self.first_name = normalize_name(self.first_name)
        self.last_name = normalize_name(self.last_name)
        self.middle_name = normalize_name(self.middle_name)
        super().save(*args, **kwargs)

    @property
    def full_name(self) -> str:
        return " ".join(part for part in (self.last_name, self.first_name) if part)

    @property
    def short_display(self) -> str:
        initial = f"{self.first_name[0]}." if self.first_name else ""
        return f"{self.last_name} {initial}".strip()

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
        return mask_jshshir(self.jshshir_last4) if self.jshshir_last4 else ""

    @property
    def masked_passport_id(self) -> str:
        return mask_passport_id(self.passport_id)

    def set_jshshir(self, raw: str) -> None:
        """Store the three representations, or clear all of them when blank."""
        if not (raw or "").strip():
            self.jshshir_hash = ""
            self.jshshir_encrypted = ""
            self.jshshir_last4 = ""
            return
        value = normalize_jshshir(raw)
        self.jshshir_hash = hash_value(value)
        self.jshshir_encrypted = encrypt(value)
        self.jshshir_last4 = value[-4:]


class Teacher(UUIDModel, TimeStampedModel, SoftDeleteModel, PersonRecord):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="teachers")
    user = models.OneToOneField(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="teacher_profile",
    )
    photo = models.ImageField(
        "Rasm", upload_to="teachers/photos/%Y/%m/", null=True, blank=True
    )
    subjects = models.ManyToManyField(Subject, related_name="teachers", blank=True)

    class Meta:
        verbose_name = "O'qituvchi"
        verbose_name_plural = "O'qituvchilar"
        ordering = ("last_name", "first_name")
        constraints = [
            # Blank is allowed and must stay repeatable, so only real documents
            # are held unique — and only among the rows that are still alive.
            models.UniqueConstraint(
                fields=["school", "passport_id"],
                condition=models.Q(deleted_at__isnull=True) & ~models.Q(passport_id=""),
                name="uniq_teacher_passport_per_school",
            ),
            models.UniqueConstraint(
                fields=["school", "jshshir_hash"],
                condition=models.Q(deleted_at__isnull=True) & ~models.Q(jshshir_hash=""),
                name="uniq_teacher_jshshir_per_school",
            ),
        ]
        indexes = [models.Index(fields=["school", "is_active"])]


class Position(UUIDModel, TimeStampedModel, SoftDeleteModel):
    """A job title, written once in each of the three interface languages.

    A staff member is a person plus what they do, and what they do is picked
    from this list rather than typed into a free-text box — so "Hisobchi",
    "Бухгалтер" and "Accountant" stay the same position, and the register can
    be counted by role.

    There is nothing to a position but its name: no permissions hang off it, no
    behaviour changes. That is deliberate — it is a label for people, not an
    access level. Access lives in ``accounts.Role``.
    """

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="positions")
    title_uz = models.CharField("Nomi (o'zbekcha)", max_length=120)
    title_ru = models.CharField("Nomi (ruscha)", max_length=120, blank=True)
    title_en = models.CharField("Nomi (inglizcha)", max_length=120, blank=True)

    class Meta:
        verbose_name = "Lavozim"
        verbose_name_plural = "Lavozimlar"
        ordering = (Lower("title_uz"),)
        constraints = [
            # Only among the rows that are still alive: a deleted "Hisobchi"
            # must not hold the name for ever.
            models.UniqueConstraint(
                Lower("title_uz"),
                "school",
                condition=models.Q(deleted_at__isnull=True),
                name="uniq_position_title_per_school",
            ),
        ]

    def __str__(self) -> str:
        return self.title_uz

    def title_for(self, language: str) -> str:
        """The title in one language, falling back to the Uzbek original.

        A position added before Russian was filled in should read as its Uzbek
        name on a Russian screen, not as an empty cell.
        """
        return getattr(self, f"title_{language}", "") or self.title_uz

    @property
    def titles(self) -> dict[str, str]:
        return {"uz": self.title_uz, "ru": self.title_ru, "en": self.title_en}


class StaffMember(UUIDModel, TimeStampedModel, SoftDeleteModel, PersonRecord):
    """A school employee who is not a teacher: the office, the kitchen, security.

    Entered on the same form as a teacher — same name, documents and contacts,
    validated by the same fields — with a position instead of subjects.
    """

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="staff_members")
    user = models.OneToOneField(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="staff_profile",
    )
    # Optional on purpose: a person is entered first and labelled afterwards.
    # Forcing a position at the moment of creation meant the register could not
    # hold somebody until the office had decided what to call them.
    # ``SET_NULL`` rather than ``PROTECT``: a position that is removed leaves
    # the people behind, unlabelled, rather than taking them with it.
    position = models.ForeignKey(
        Position,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="staff_members",
        verbose_name="Lavozim",
    )
    photo = models.ImageField(
        "Rasm", upload_to="staff/photos/%Y/%m/", null=True, blank=True
    )

    class Meta:
        verbose_name = "Xodim"
        verbose_name_plural = "Xodimlar"
        ordering = ("last_name", "first_name")
        constraints = [
            # Same rule as a teacher's: blank documents stay repeatable, real
            # ones are unique among the living rows of one school.
            models.UniqueConstraint(
                fields=["school", "passport_id"],
                condition=models.Q(deleted_at__isnull=True) & ~models.Q(passport_id=""),
                name="uniq_staff_passport_per_school",
            ),
            models.UniqueConstraint(
                fields=["school", "jshshir_hash"],
                condition=models.Q(deleted_at__isnull=True) & ~models.Q(jshshir_hash=""),
                name="uniq_staff_jshshir_per_school",
            ),
        ]
        indexes = [models.Index(fields=["school", "is_active"])]


class CuratorAssignment(UUIDModel, TimeStampedModel):
    """A curator put in charge of one class group — "Ali Valiyev → 7-A".

    The row is what a CURATOR's whole cabinet is built on: their groups, the
    pupils in them, those pupils' attendance and nothing else. One person may
    hold several groups, and a group may have several curators — neither is
    forbidden by anything in the school, so neither is forbidden here.

    It points at the *account*, not at the staff row: a curator is somebody who
    signs in and looks at a class, and plenty of them are teachers whose staff
    record lives in the other table.
    """

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="curator_assignments",
        verbose_name="Kurator",
    )
    class_group = models.ForeignKey(
        ClassGroup,
        on_delete=models.CASCADE,
        related_name="curator_assignments",
        verbose_name="Sinf guruhi",
    )
    assigned_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="curator_assignments_made",
        verbose_name="Kim biriktirgan",
    )

    class Meta:
        verbose_name = "Kurator biriktiruvi"
        verbose_name_plural = "Kurator biriktiruvlari"
        ordering = ("class_group__grade__level", "class_group__name")
        constraints = [
            models.UniqueConstraint(
                fields=["user", "class_group"], name="uniq_curator_per_class_group"
            ),
        ]
        indexes = [models.Index(fields=["user"])]

    def __str__(self) -> str:
        return f"{self.user.full_name} → {self.class_group.display_name}"


class Holiday(UUIDModel, TimeStampedModel):
    """Non-teaching days and (rarely) working weekends."""

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="holidays")
    academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.CASCADE, related_name="holidays"
    )
    date = models.DateField("Sana", db_index=True)
    name = models.CharField("Nomi", max_length=150)
    # True for a make-up Saturday that replaces a holiday.
    is_working_day = models.BooleanField("Ish kuni", default=False)

    class Meta:
        verbose_name = "Bayram / dam olish kuni"
        verbose_name_plural = "Bayram va dam olish kunlari"
        ordering = ("date",)
        constraints = [
            models.UniqueConstraint(fields=["school", "date"], name="uniq_holiday_per_school_date"),
        ]

    def __str__(self) -> str:
        return f"{self.date} — {self.name}"
