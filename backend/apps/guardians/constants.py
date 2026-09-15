from django.db import models


class Relation(models.TextChoices):
    FATHER = "FATHER", "Otasi"
    MOTHER = "MOTHER", "Onasi"
    GUARDIAN = "GUARDIAN", "Vasiysi"
    OTHER = "OTHER", "Boshqa"
