from django.db import models


class NotificationType(models.TextChoices):
    SCHOOL_ENTRY = "SCHOOL_ENTRY", "Maktabga kirdi"
    SCHOOL_EXIT = "SCHOOL_EXIT", "Maktabdan chiqdi"
    ATTENDANCE_ABSENT = "ATTENDANCE_ABSENT", "Darsga kelmadi"
    ATTENDANCE_LATE = "ATTENDANCE_LATE", "Darsga kechikdi"
    ABSENCE_REASON_APPROVED = "ABSENCE_REASON_APPROVED", "Sabab tasdiqlandi"
    ABSENCE_REASON_REJECTED = "ABSENCE_REASON_REJECTED", "Sabab rad etildi"
    ABSENCE_REASON_SUBMITTED = "ABSENCE_REASON_SUBMITTED", "Sabab yuborildi"
    DAILY_SUMMARY = "DAILY_SUMMARY", "Kunlik hisobot"
    ANNOUNCEMENT = "ANNOUNCEMENT", "E'lon"
    SYSTEM = "SYSTEM", "Tizim xabari"


class NotificationChannel(models.TextChoices):
    IN_APP = "IN_APP", "Ilova ichida"
    TELEGRAM = "TELEGRAM", "Telegram"
    SMS = "SMS", "SMS"


class DeliveryStatus(models.TextChoices):
    PENDING = "PENDING", "Navbatda"
    SENT = "SENT", "Yuborildi"
    FAILED = "FAILED", "Xatolik"
    SKIPPED = "SKIPPED", "O'tkazib yuborildi"
