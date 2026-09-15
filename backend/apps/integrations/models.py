from __future__ import annotations

import json
from datetime import timedelta

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from apps.common.crypto import decrypt, encrypt
from apps.common.models import SoftDeleteModel, TimeStampedModel, UUIDModel

from .constants import (
    EventDirection,
    IntegrationKind,
    IntegrationStatus,
    PresenceSource,
    SyncState,
    TerminalDirection,
    TerminalVendor,
    VerifyMode,
)


class SecretsMixin(models.Model):
    """Stores a JSON blob of credentials as Fernet ciphertext.

    Credentials never appear in a serializer, an admin form, a log line or an
    audit payload — only ``masked_secrets()`` is ever exposed.
    """

    secrets_encrypted = models.TextField(blank=True, editable=False)

    class Meta:
        abstract = True

    @property
    def secrets(self) -> dict:
        if not self.secrets_encrypted:
            return {}
        raw = decrypt(self.secrets_encrypted)
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except ValueError:  # pragma: no cover - corrupted ciphertext
            return {}

    def set_secrets(self, values: dict) -> None:
        """Replace the whole secret blob."""
        self.secrets_encrypted = encrypt(json.dumps(values)) if values else ""

    def update_secrets(self, values: dict) -> None:
        """Merge in new values; a ``None`` clears a key, a missing key keeps it."""
        current = self.secrets
        for key, value in values.items():
            if value is None:
                current.pop(key, None)
            elif value != "":
                current[key] = value
        self.set_secrets(current)

    def secret(self, key: str, default: str = "") -> str:
        return self.secrets.get(key, default)

    def masked_secrets(self) -> dict[str, str]:
        """``{"token": "••••••1234"}`` — enough to confirm which value is set."""
        return {key: mask_secret(str(value)) for key, value in self.secrets.items()}


def mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 4:
        return "•" * len(value)
    return "•" * 6 + value[-4:]


class Integration(UUIDModel, TimeStampedModel, SecretsMixin):
    """One configurable integration (Telegram, SMS, Face ID, Terminals).

    Non-secret options live in ``config``; tokens and passwords live in the
    encrypted blob. A row with ``school=NULL`` is the platform-wide default that
    a school-specific row can override.
    """

    school = models.ForeignKey(
        "schools.School",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="integrations",
        help_text="Bo'sh bo'lsa — barcha maktablar uchun umumiy sozlama.",
    )
    kind = models.CharField("Turi", max_length=32, choices=IntegrationKind.choices)
    is_enabled = models.BooleanField("Yoqilgan", default=False)
    config = models.JSONField("Sozlamalar", default=dict, blank=True)

    status = models.CharField(
        max_length=16, choices=IntegrationStatus.choices, default=IntegrationStatus.UNKNOWN
    )
    last_checked_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=500, blank=True)

    updated_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_integrations",
    )

    class Meta:
        verbose_name = "Integratsiya"
        verbose_name_plural = "Integratsiyalar"
        ordering = ("kind",)
        constraints = [
            models.UniqueConstraint(
                fields=["kind"],
                condition=models.Q(school__isnull=True),
                name="uniq_global_integration_per_kind",
            ),
            models.UniqueConstraint(
                fields=["school", "kind"],
                condition=models.Q(school__isnull=False),
                name="uniq_integration_per_school_kind",
            ),
        ]

    def __str__(self) -> str:
        scope = self.school.short_name if self.school_id else "Global"
        return f"{self.get_kind_display()} ({scope})"

    def mark_checked(self, *, ok: bool, error: str = "") -> None:
        self.status = IntegrationStatus.OK if ok else IntegrationStatus.ERROR
        self.last_checked_at = timezone.now()
        self.last_error = error[:500]
        self.save(update_fields=["status", "last_checked_at", "last_error", "updated_at"])

    @property
    def effective_status(self) -> str:
        return self.status if self.is_enabled else IntegrationStatus.DISABLED


class Terminal(UUIDModel, TimeStampedModel, SoftDeleteModel, SecretsMixin):
    """A physical access-control device (Hikvision DS-K1T341CMF and friends).

    The ISAPI password is kept in the encrypted secrets blob, never in a column
    a query or a log could surface.
    """

    school = models.ForeignKey(
        "schools.School", on_delete=models.CASCADE, related_name="terminals"
    )
    name = models.CharField("Nomi", max_length=120, help_text="Masalan: Asosiy kirish")
    vendor = models.CharField(
        "Ishlab chiqaruvchi",
        max_length=32,
        choices=TerminalVendor.choices,
        default=TerminalVendor.HIKVISION,
    )
    model = models.CharField("Model", max_length=64, default="DS-K1T341CMF")
    serial_number = models.CharField("Seriya raqami", max_length=64, blank=True)

    host = models.CharField("IP manzil / host", max_length=255)
    port = models.PositiveIntegerField(
        "Port", default=80, validators=[MinValueValidator(1), MaxValueValidator(65535)]
    )
    use_https = models.BooleanField("HTTPS", default=False)
    username = models.CharField("ISAPI login", max_length=64, default="admin")

    direction = models.CharField(
        "Yo'nalish",
        max_length=8,
        choices=TerminalDirection.choices,
        default=TerminalDirection.BOTH,
        help_text="Qurilma faqat kirishni, faqat chiqishni yoki ikkalasini yozadimi.",
    )
    location = models.CharField("Joylashuvi", max_length=150, blank=True)
    is_active = models.BooleanField("Faol", default=True)

    # Push ingestion: the device posts events to
    # /api/v1/terminals/events/<ingest_token>/ — the token is the only thing
    # that authorises the call, so it is long and rotatable.
    ingest_token = models.CharField(max_length=64, unique=True, editable=False, db_index=True)

    # Pull ingestion bookkeeping.
    last_event_at = models.DateTimeField(null=True, blank=True)
    last_polled_at = models.DateTimeField(null=True, blank=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    firmware = models.CharField(max_length=64, blank=True)
    status = models.CharField(
        max_length=16, choices=IntegrationStatus.choices, default=IntegrationStatus.UNKNOWN
    )
    last_error = models.CharField(max_length=500, blank=True)

    class Meta:
        verbose_name = "Terminal"
        verbose_name_plural = "Terminallar"
        ordering = ("school", "name")
        constraints = [
            models.UniqueConstraint(
                fields=["school", "host", "port"],
                condition=models.Q(deleted_at__isnull=True),
                name="uniq_terminal_endpoint_per_school",
            ),
        ]
        indexes = [models.Index(fields=["school", "is_active"])]

    def __str__(self) -> str:
        return f"{self.name} ({self.host})"

    def save(self, *args, **kwargs):
        if not self.ingest_token:
            import secrets as _secrets

            self.ingest_token = _secrets.token_urlsafe(32)
        super().save(*args, **kwargs)

    @property
    def base_url(self) -> str:
        scheme = "https" if self.use_https else "http"
        return f"{scheme}://{self.host}:{self.port}"

    @property
    def password(self) -> str:
        return self.secret("password")

    def set_password(self, value: str) -> None:
        self.update_secrets({"password": value})

    def rotate_ingest_token(self) -> str:
        import secrets as _secrets

        self.ingest_token = _secrets.token_urlsafe(32)
        self.save(update_fields=["ingest_token", "updated_at"])
        return self.ingest_token

    def mark_online(self, *, firmware: str = "", serial: str = "") -> None:
        self.status = IntegrationStatus.OK
        self.last_seen_at = timezone.now()
        self.last_error = ""
        if firmware:
            self.firmware = firmware[:64]
        if serial and not self.serial_number:
            self.serial_number = serial[:64]
        self.save(
            update_fields=[
                "status", "last_seen_at", "last_error", "firmware", "serial_number", "updated_at",
            ]
        )

    def mark_offline(self, error: str) -> None:
        self.status = IntegrationStatus.ERROR
        self.last_error = error[:500]
        self.save(update_fields=["status", "last_error", "updated_at"])


class TerminalPerson(UUIDModel, TimeStampedModel):
    """Maps a pupil to the person record enrolled on the devices.

    ``person_code`` is the device-side ``employeeNo``; it is what arrives on
    every access event and is how an event is resolved back to a pupil.
    """

    school = models.ForeignKey(
        "schools.School", on_delete=models.CASCADE, related_name="terminal_people"
    )
    student = models.OneToOneField(
        "students.Student",
        on_delete=models.CASCADE,
        related_name="terminal_person",
        null=True,
        blank=True,
    )
    #: Staff pass through the same gate and are enrolled the same way. Exactly
    #: one of student/teacher/staff is set on any row.
    teacher = models.OneToOneField(
        "schools.Teacher",
        on_delete=models.CASCADE,
        related_name="terminal_person",
        null=True,
        blank=True,
    )
    #: The rest of the employees — the office, the kitchen, security. They walk
    #: through the same turnstile as everybody else, and their own cabinet is
    #: built on these passes, so they get a device identity too.
    staff = models.OneToOneField(
        "schools.StaffMember",
        on_delete=models.CASCADE,
        related_name="terminal_person",
        null=True,
        blank=True,
    )
    person_code = models.CharField("Qurilmadagi kod", max_length=64, db_index=True)
    card_no = models.CharField("Karta raqami", max_length=64, blank=True)

    has_face = models.BooleanField("Yuz yuklangan", default=False)
    face_synced_at = models.DateTimeField(null=True, blank=True)
    sync_state = models.CharField(
        max_length=16, choices=SyncState.choices, default=SyncState.PENDING
    )
    sync_error = models.CharField(max_length=500, blank=True)
    synced_terminals = models.ManyToManyField(
        Terminal, blank=True, related_name="enrolled_people"
    )

    class Meta:
        verbose_name = "Terminal foydalanuvchisi"
        verbose_name_plural = "Terminal foydalanuvchilari"
        ordering = ("person_code",)
        constraints = [
            models.UniqueConstraint(
                fields=["school", "person_code"], name="uniq_person_code_per_school"
            ),
            models.CheckConstraint(
                check=(
                    models.Q(student__isnull=False, teacher__isnull=True, staff__isnull=True)
                    | models.Q(student__isnull=True, teacher__isnull=False, staff__isnull=True)
                    | models.Q(student__isnull=True, teacher__isnull=True, staff__isnull=False)
                ),
                name="terminal_person_is_one_person",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.person_code} → {self.holder.full_name}"

    @property
    def holder(self):
        """The pupil or the member of staff this device identity belongs to."""
        return self.student or self.teacher or self.staff


class TerminalEvent(UUIDModel, TimeStampedModel):
    """A raw pass through a turnstile.

    Kept verbatim so attendance can always be recomputed from source, and made
    idempotent by ``(terminal, external_id)`` — the same event arriving twice
    (push *and* poll, or a retry) can never be double-counted.
    """

    terminal = models.ForeignKey(Terminal, on_delete=models.CASCADE, related_name="events")
    external_id = models.CharField(
        "Qurilmadagi ID", max_length=128, db_index=True,
        help_text="serialNo + vaqt asosidagi barqaror identifikator.",
    )
    occurred_at = models.DateTimeField("Vaqti", db_index=True)
    date = models.DateField("Sana", db_index=True, editable=False)

    direction = models.CharField(
        max_length=8, choices=EventDirection.choices, default=EventDirection.UNKNOWN
    )
    verify_mode = models.CharField(
        max_length=16, choices=VerifyMode.choices, default=VerifyMode.OTHER
    )
    person_code = models.CharField(max_length=64, blank=True, db_index=True)
    person_name = models.CharField(max_length=150, blank=True)
    student = models.ForeignKey(
        "students.Student",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="terminal_events",
    )
    #: Staff pass through the same gate. At most one of student/teacher/staff
    #: is set; all three stay null for a code nobody in the register owns.
    teacher = models.ForeignKey(
        "schools.Teacher",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="terminal_events",
    )
    staff = models.ForeignKey(
        "schools.StaffMember",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="terminal_events",
    )
    picture_url = models.URLField(blank=True)
    raw = models.JSONField(default=dict, blank=True)

    processed = models.BooleanField(default=False, db_index=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    process_error = models.CharField(max_length=500, blank=True)

    class Meta:
        verbose_name = "Terminal hodisasi"
        verbose_name_plural = "Terminal hodisalari"
        ordering = ("-occurred_at",)
        constraints = [
            models.UniqueConstraint(
                fields=["terminal", "external_id"], name="uniq_terminal_event"
            ),
        ]
        indexes = [
            models.Index(fields=["student", "date"]),
            models.Index(fields=["teacher", "date"]),
            models.Index(fields=["staff", "date"]),
            models.Index(fields=["date", "processed"]),
            models.Index(fields=["terminal", "-occurred_at"]),
        ]

    def __str__(self) -> str:
        if self.student_id:
            who = self.student.full_name
        elif self.teacher_id:
            who = self.teacher.full_name
        elif self.staff_id:
            who = self.staff.full_name
        else:
            who = self.person_code
        return f"{who} · {self.occurred_at:%Y-%m-%d %H:%M} · {self.get_direction_display()}"

    def save(self, *args, **kwargs):
        self.date = timezone.localtime(self.occurred_at).date()
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            kwargs["update_fields"] = list(set(update_fields) | {"date"})
        super().save(*args, **kwargs)


class DailyPresence(UUIDModel, TimeStampedModel):
    """Derived arrival/departure for one pupil on one day.

    This is the turnstile's answer to "keldimi va qachon"; per-lesson
    ``Attendance`` rows are generated from it by the attendance rule engine.
    """

    student = models.ForeignKey(
        "students.Student", on_delete=models.CASCADE, related_name="daily_presence"
    )
    date = models.DateField(db_index=True)

    first_in_at = models.DateTimeField("Birinchi kirish", null=True, blank=True)
    last_out_at = models.DateTimeField("Oxirgi chiqish", null=True, blank=True)
    entries_count = models.PositiveSmallIntegerField(default=0)
    exits_count = models.PositiveSmallIntegerField(default=0)

    source = models.CharField(
        max_length=16, choices=PresenceSource.choices, default=PresenceSource.TERMINAL
    )
    #: Minutes late relative to the start of the school day, 0 when on time.
    late_minutes = models.PositiveSmallIntegerField(default=0)
    left_early = models.BooleanField(default=False)

    #: Minutes actually spent inside the building, summed over every visit.
    inside_minutes = models.PositiveIntegerField("Maktabda (daqiqa)", default=0)
    #: Minutes spent outside between leaving and coming back the same day.
    outside_minutes = models.PositiveIntegerField("Tashqarida (daqiqa)", default=0)
    #: ``[{"in": iso, "out": iso|null, "minutes": int}]`` — one entry per visit.
    sessions = models.JSONField(default=list, blank=True)
    #: True while the pupil is inside: the last entry has no matching exit yet.
    is_inside = models.BooleanField("Hozir maktabda", default=False)
    #: Arrived after ``arrival_cutoff_time``. The pass is kept and shown, but
    #: the day does not count as attended — turning up at 16:20 is not a school
    #: day, and silently counting it as one would flatter the figures.
    arrived_too_late = models.BooleanField("Juda kech keldi", default=False)

    class Meta:
        verbose_name = "Kunlik davomat (turniket)"
        verbose_name_plural = "Kunlik davomat (turniket)"
        ordering = ("-date",)
        constraints = [
            models.UniqueConstraint(fields=["student", "date"], name="uniq_daily_presence"),
        ]
        indexes = [models.Index(fields=["date"]), models.Index(fields=["student", "-date"])]

    def __str__(self) -> str:
        return f"{self.student.full_name} · {self.date}"

    @property
    def was_present(self) -> bool:
        return self.first_in_at is not None

    @property
    def duration(self) -> timedelta | None:
        if self.first_in_at and self.last_out_at and self.last_out_at > self.first_in_at:
            return self.last_out_at - self.first_in_at
        return None

    @property
    def duration_minutes(self) -> int:
        """Time between the first entry and the last exit (gaps included)."""
        span = self.duration
        return int(span.total_seconds() // 60) if span else 0

    @property
    def last_in_at(self):
        """Start of the most recent visit."""
        for visit in reversed(self.sessions or []):
            if visit.get("in"):
                return visit["in"]
        return self.first_in_at.isoformat() if self.first_in_at else None

    @property
    def first_out_at(self):
        """End of the first visit — the first time they left the building."""
        for visit in self.sessions or []:
            if visit.get("out"):
                return visit["out"]
        return None
