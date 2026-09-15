from django.db import models


class Weekday(models.IntegerChoices):
    """ISO-8601 weekday numbering (Monday = 1)."""

    MONDAY = 1, "Dushanba"
    TUESDAY = 2, "Seshanba"
    WEDNESDAY = 3, "Chorshanba"
    THURSDAY = 4, "Payshanba"
    FRIDAY = 5, "Juma"
    SATURDAY = 6, "Shanba"
    SUNDAY = 7, "Yakshanba"


WEEKDAY_SHORT_UZ = {
    1: "Du",
    2: "Se",
    3: "Chor",
    4: "Pay",
    5: "Ju",
    6: "Sha",
    7: "Ya",
}

MONTH_NAMES_UZ = {
    1: "Yanvar",
    2: "Fevral",
    3: "Mart",
    4: "Aprel",
    5: "May",
    6: "Iyun",
    7: "Iyul",
    8: "Avgust",
    9: "Sentabr",
    10: "Oktabr",
    11: "Noyabr",
    12: "Dekabr",
}

GRADE_MIN = 1
GRADE_MAX = 11
