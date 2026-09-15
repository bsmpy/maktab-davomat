from __future__ import annotations

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone

from apps.common.models import TimeStampedModel, UUIDModel
from apps.schools.constants import Weekday

from .constants import AbsenceRequestStatus, AttendanceSource, AttendanceStatus

MAX_LESSON_NUMBER = 12


class Schedule(UUIDModel, TimeStampedModel):
    """Recurring timetable entry: "7-A has Maths, 3rd lesson, every Tuesday"."""

    academic_year = models.ForeignKey(
        "schools.AcademicYear", on_delete=models.CASCADE, related_name="schedules"
    )
    class_group = models.ForeignKey(
        "schools.ClassGroup", on_delete=models.CASCADE, related_name="schedules"
    )
    subject = models.ForeignKey(
        "schools.Subject", on_delete=models.PROTECT, related_name="schedules"
    )
    teacher = models.ForeignKey(
        "schools.Teacher",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="schedules",
    )
    weekday = models.PositiveSmallIntegerField("Hafta kuni", choices=Weekday.choices)
    lesson_number = models.PositiveSmallIntegerField(
        "Dars raqami", validators=[MinValueValidator(1), MaxValueValidator(MAX_LESSON_NUMBER)]
    )
    start_time = models.TimeField("Boshlanish vaqti")
    end_time = models.TimeField("Tugash vaqti")
    room = models.CharField("Xona", max_length=32, blank=True)
    valid_from = models.DateField(null=True, blank=True)
    valid_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Dars jadvali"
        verbose_name_plural = "Dars jadvallari"
        ordering = ("weekday", "lesson_number")
        constraints = [
            models.UniqueConstraint(
                fields=["academic_year", "class_group", "weekday", "lesson_number"],
                name="uniq_schedule_slot",
            ),
            models.CheckConstraint(
                check=models.Q(end_time__gt=models.F("start_time")),
                name="schedule_end_after_start",
            ),
        ]
        indexes = [models.Index(fields=["class_group", "weekday", "is_active"])]

    def __str__(self) -> str:
        return (
            f"{self.class_group.display_name} · {self.get_weekday_display()} "
            f"#{self.lesson_number} · {self.subject.name}"
        )

    def covers(self, day) -> bool:
        if self.valid_from and day < self.valid_from:
            return False
        if self.valid_to and day > self.valid_to:
            return False
        return self.is_active


class LessonQuerySet(models.QuerySet):
    def for_class_group(self, class_group_id):
        return self.filter(class_group_id=class_group_id)

    def on(self, day):
        return self.filter(date=day)

    def in_range(self, start, end):
        return self.filter(date__gte=start, date__lte=end)

    def held(self):
        return self.filter(is_canceled=False)

    def with_details(self):
        return self.select_related("subject", "teacher", "class_group", "class_group__grade")


class Lesson(UUIDModel, TimeStampedModel):
    """A concrete lesson session on a concrete date.

    Attendance always points at a lesson – never at a bare date – so a pupil's
    record can be broken down per subject and per teacher.
    """

    academic_year = models.ForeignKey(
        "schools.AcademicYear", on_delete=models.CASCADE, related_name="lessons"
    )
    schedule = models.ForeignKey(
        Schedule, on_delete=models.SET_NULL, null=True, blank=True, related_name="lessons"
    )
    class_group = models.ForeignKey(
        "schools.ClassGroup", on_delete=models.CASCADE, related_name="lessons"
    )
    subject = models.ForeignKey("schools.Subject", on_delete=models.PROTECT, related_name="lessons")
    teacher = models.ForeignKey(
        "schools.Teacher", on_delete=models.SET_NULL, null=True, blank=True, related_name="lessons"
    )
    date = models.DateField("Sana", db_index=True)
    lesson_number = models.PositiveSmallIntegerField(
        "Dars raqami", validators=[MinValueValidator(1), MaxValueValidator(MAX_LESSON_NUMBER)]
    )
    start_time = models.TimeField("Boshlanish vaqti")
    end_time = models.TimeField("Tugash vaqti")
    room = models.CharField("Xona", max_length=32, blank=True)
    topic = models.CharField("Mavzu", max_length=255, blank=True)
    is_canceled = models.BooleanField("Bekor qilingan", default=False)

    objects = LessonQuerySet.as_manager()

    class Meta:
        verbose_name = "Dars"
        verbose_name_plural = "Darslar"
        ordering = ("date", "lesson_number")
        constraints = [
            models.UniqueConstraint(
                fields=["class_group", "date", "lesson_number"], name="uniq_lesson_slot_per_day"
            ),
            models.CheckConstraint(
                check=models.Q(end_time__gt=models.F("start_time")),
                name="lesson_end_after_start",
            ),
        ]
        indexes = [
            models.Index(fields=["class_group", "date"]),
            models.Index(fields=["date", "is_canceled"]),
            models.Index(fields=["teacher", "date"]),
        ]

    def __str__(self) -> str:
        return f"{self.date} #{self.lesson_number} {self.subject.name} ({self.class_group.display_name})"

    @property
    def weekday(self) -> int:
        return self.date.isoweekday()


class AttendanceReason(UUIDModel, TimeStampedModel):
    """Catalogue of absence reasons (Kasallik, Oilaviy sabab, Safar, Boshqa)."""

    school = models.ForeignKey(
        "schools.School",
        on_delete=models.CASCADE,
        related_name="attendance_reasons",
        null=True,
        blank=True,
        help_text="Bo'sh bo'lsa — barcha maktablar uchun umumiy sabab.",
    )
    code = models.CharField("Kod", max_length=32)
    name = models.CharField("Nomi", max_length=120)
    requires_comment = models.BooleanField("Izoh majburiy", default=False)
    requires_document = models.BooleanField("Hujjat talab qilinadi", default=False)
    order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Sabab turi"
        verbose_name_plural = "Sabab turlari"
        ordering = ("order", "name")
        constraints = [
            models.UniqueConstraint(
                Lower("code"), "school", name="uniq_attendance_reason_code_per_school"
            ),
        ]

    def __str__(self) -> str:
        return self.name


class AbsenceRequest(UUIDModel, TimeStampedModel):
    """A parent-submitted explanation for a missed day ("Sabab bildirish")."""

    student = models.ForeignKey(
        "students.Student", on_delete=models.CASCADE, related_name="absence_requests"
    )
    date = models.DateField("Sana", db_index=True)
    reason = models.ForeignKey(
        AttendanceReason, on_delete=models.PROTECT, related_name="absence_requests"
    )
    comment = models.TextField("Izoh", blank=True)
    lessons = models.ManyToManyField(
        Lesson,
        blank=True,
        related_name="absence_requests",
        help_text="Bo'sh bo'lsa — kun bo'yi barcha darslar.",
    )

    status = models.CharField(
        "Holati",
        max_length=20,
        choices=AbsenceRequestStatus.choices,
        default=AbsenceRequestStatus.PENDING,
        db_index=True,
    )
    submitted_by = models.ForeignKey(
        "accounts.User", on_delete=models.PROTECT, related_name="submitted_absence_requests"
    )
    submitted_at = models.DateTimeField(default=timezone.now)
    reviewed_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_absence_requests",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_comment = models.TextField("Ko'rib chiquvchi izohi", blank=True)

    class Meta:
        verbose_name = "Sabab arizasi"
        verbose_name_plural = "Sabab arizalari"
        ordering = ("-date", "-submitted_at")
        constraints = [
            # A parent cannot spam several open requests for the same day.
            models.UniqueConstraint(
                fields=["student", "date"],
                condition=models.Q(status=AbsenceRequestStatus.PENDING),
                name="uniq_pending_absence_request_per_day",
            ),
        ]
        indexes = [models.Index(fields=["student", "date", "status"])]

    def __str__(self) -> str:
        return f"{self.student.full_name} · {self.date} · {self.get_status_display()}"


class AttendanceQuerySet(models.QuerySet):
    def for_student(self, student_id):
        return self.filter(student_id=student_id)

    def in_range(self, start, end):
        return self.filter(date__gte=start, date__lte=end)

    def with_details(self):
        return self.select_related(
            "lesson", "lesson__subject", "lesson__teacher", "reason", "marked_by"
        )

    def counted(self):
        """Rows on lessons that actually took place."""
        return self.filter(lesson__is_canceled=False)


class Attendance(UUIDModel, TimeStampedModel):
    """One pupil's status for one lesson.

    ``date`` is denormalised from the lesson: every aggregation filters on it,
    and copying it here removes a join from the hottest queries.
    """

    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name="attendances")
    student = models.ForeignKey(
        "students.Student", on_delete=models.CASCADE, related_name="attendances"
    )
    date = models.DateField(db_index=True, editable=False)

    status = models.CharField(
        "Holati", max_length=20, choices=AttendanceStatus.choices, db_index=True
    )
    late_minutes = models.PositiveSmallIntegerField(
        "Kechikish (daqiqa)", default=0, validators=[MaxValueValidator(600)]
    )
    reason = models.ForeignKey(
        AttendanceReason,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attendances",
    )
    absence_request = models.ForeignKey(
        AbsenceRequest,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attendances",
    )
    comment = models.CharField("Izoh", max_length=255, blank=True)
    source = models.CharField(
        "Manba",
        max_length=16,
        choices=AttendanceSource.choices,
        default=AttendanceSource.MANUAL,
        db_index=True,
    )

    marked_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="marked_attendances",
    )
    marked_at = models.DateTimeField(default=timezone.now)

    objects = AttendanceQuerySet.as_manager()

    class Meta:
        verbose_name = "Davomat yozuvi"
        verbose_name_plural = "Davomat yozuvlari"
        ordering = ("-date", "lesson__lesson_number")
        constraints = [
            models.UniqueConstraint(
                fields=["student", "lesson"], name="uniq_attendance_per_student_lesson"
            ),
            models.CheckConstraint(
                check=models.Q(status=AttendanceStatus.LATE) | models.Q(late_minutes=0),
                name="late_minutes_only_when_late",
            ),
        ]
        indexes = [
            models.Index(fields=["student", "date"]),
            models.Index(fields=["student", "date", "status"]),
            models.Index(fields=["date", "status"]),
            models.Index(fields=["lesson", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.student.full_name} · {self.date} · {self.get_status_display()}"

    def save(self, *args, **kwargs):
        if self.lesson_id and (not self.date or "lesson" in (kwargs.get("update_fields") or [])):
            self.date = self.lesson.date
        if not self.date:
            self.date = self.lesson.date
        if self.status != AttendanceStatus.LATE:
            self.late_minutes = 0
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            kwargs["update_fields"] = list(set(update_fields) | {"date", "late_minutes"})
        super().save(*args, **kwargs)

    @property
    def is_attended(self) -> bool:
        return self.status in (AttendanceStatus.PRESENT, AttendanceStatus.LATE)

    @property
    def is_machine_generated(self) -> bool:
        return self.source == AttendanceSource.TERMINAL


class AttendanceHistory(UUIDModel, TimeStampedModel):
    """Immutable trail of every edit made to an attendance record."""

    attendance = models.ForeignKey(
        Attendance, on_delete=models.CASCADE, related_name="history"
    )
    changed_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attendance_changes",
    )
    old_status = models.CharField(max_length=20, choices=AttendanceStatus.choices, blank=True)
    new_status = models.CharField(max_length=20, choices=AttendanceStatus.choices)
    old_late_minutes = models.PositiveSmallIntegerField(default=0)
    new_late_minutes = models.PositiveSmallIntegerField(default=0)
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "Davomat o'zgarishi"
        verbose_name_plural = "Davomat o'zgarishlari"
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["attendance", "-created_at"])]

    def __str__(self) -> str:
        return f"{self.attendance_id}: {self.old_status or '—'} → {self.new_status}"
