from django.db import models


class AttendanceStatus(models.TextChoices):
    PRESENT = "PRESENT", "Keldi"
    ABSENT = "ABSENT", "Kelmadi"
    LATE = "LATE", "Kechikdi"
    EXCUSED = "EXCUSED", "Sababli"


#: Statuses that count as the pupil having attended the lesson.
ATTENDED_STATUSES = (AttendanceStatus.PRESENT, AttendanceStatus.LATE)
#: Statuses that count as a missed lesson.
MISSED_STATUSES = (AttendanceStatus.ABSENT, AttendanceStatus.EXCUSED)

#: Calendar day colour codes consumed by the frontend calendar.
DAY_STATE_PRESENT = "PRESENT"
DAY_STATE_ABSENT = "ABSENT"
DAY_STATE_LATE = "LATE"
DAY_STATE_EXCUSED = "EXCUSED"
DAY_STATE_NO_LESSONS = "NO_LESSONS"
#: A school day that has not produced a turnstile pass yet (today, before the
#: pupil arrives). Distinct from ABSENT, which is a day that is already over.
DAY_STATE_NO_DATA = "NO_DATA"
DAY_STATE_HOLIDAY = "HOLIDAY"
DAY_STATE_WEEKEND = "WEEKEND"
DAY_STATE_FUTURE = "FUTURE"


class AttendanceSource(models.TextChoices):
    """Where a mark came from.

    The turnstile rule engine only ever overwrites its own rows, so a teacher's
    correction is never silently undone by the next sync.
    """

    MANUAL = "MANUAL", "Qo'lda"
    TERMINAL = "TERMINAL", "Turniket"
    IMPORT = "IMPORT", "Import"


class AbsenceRequestStatus(models.TextChoices):
    PENDING = "PENDING", "Ko'rib chiqilmoqda"
    APPROVED = "APPROVED", "Tasdiqlandi"
    REJECTED = "REJECTED", "Rad etildi"
