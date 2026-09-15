from django.db import models


class IntegrationKind(models.TextChoices):
    """The four integrations exposed under Sozlamalar → Integratsiyalar."""

    TELEGRAM_BOT = "TELEGRAM_BOT", "Telegram bot"
    SMS_ESKIZ = "SMS_ESKIZ", "SMS (Eskiz)"
    FACE_ID = "FACE_ID", "Face ID"
    TERMINALS = "TERMINALS", "Terminallar"


class IntegrationStatus(models.TextChoices):
    UNKNOWN = "UNKNOWN", "Tekshirilmagan"
    OK = "OK", "Ishlayapti"
    ERROR = "ERROR", "Xatolik"
    DISABLED = "DISABLED", "O'chirilgan"


class TerminalDirection(models.TextChoices):
    """Which way through the turnstile a device records."""

    IN = "IN", "Kirish"
    OUT = "OUT", "Chiqish"
    BOTH = "BOTH", "Kirish va chiqish"


class TerminalVendor(models.TextChoices):
    HIKVISION = "HIKVISION", "Hikvision (ISAPI)"


class EventDirection(models.TextChoices):
    IN = "IN", "Kirdi"
    OUT = "OUT", "Chiqdi"
    UNKNOWN = "UNKNOWN", "Noma'lum"


class VerifyMode(models.TextChoices):
    FACE = "FACE", "Yuz orqali"
    CARD = "CARD", "Karta orqali"
    FINGERPRINT = "FINGERPRINT", "Barmoq izi"
    PASSWORD = "PASSWORD", "Parol"
    OTHER = "OTHER", "Boshqa"


class SyncState(models.TextChoices):
    PENDING = "PENDING", "Navbatda"
    SYNCED = "SYNCED", "Yuklangan"
    FAILED = "FAILED", "Xatolik"


class PresenceSource(models.TextChoices):
    TERMINAL = "TERMINAL", "Turniket"
    MANUAL = "MANUAL", "Qo'lda"
    MIXED = "MIXED", "Aralash"


#: Hikvision ``AcsEvent`` minor codes that mean "access granted".
#: Anything else is a denial and must not be read as an arrival.
HIKVISION_GRANTED_MINOR = {
    1,   # legal card
    38,  # fingerprint
    75,  # face
    76,  # face + card
    77,  # face + fingerprint
    38913,  # authenticated (some firmwares)
}

#: ``attendanceStatus`` strings the device reports for check-in / check-out.
HIKVISION_DIRECTION_MAP = {
    "checkIn": EventDirection.IN,
    "checkOut": EventDirection.OUT,
    "breakOut": EventDirection.OUT,
    "breakIn": EventDirection.IN,
    "overtimeIn": EventDirection.IN,
    "overtimeOut": EventDirection.OUT,
}

HIKVISION_VERIFY_MAP = {
    "face": VerifyMode.FACE,
    "cardAndFace": VerifyMode.FACE,
    "faceAndFp": VerifyMode.FACE,
    "card": VerifyMode.CARD,
    "fp": VerifyMode.FINGERPRINT,
    "fingerprint": VerifyMode.FINGERPRINT,
    "pw": VerifyMode.PASSWORD,
    "password": VerifyMode.PASSWORD,
}
