"""Fuzzy pupil search.

The registration wizard must find "Валиев" when the register spells the name
"Valiyev": transliteration alone cannot bridge Uzbek-Latin/Russian-Cyrillic
spelling differences, so the search runs on trigram similarity, backed by a GIN
index so it stays cheap.
"""
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.operations import TrigramExtension
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("students", "0001_initial")]

    operations = [
        TrigramExtension(),
        migrations.AddIndex(
            model_name="student",
            index=GinIndex(
                fields=["search_name"],
                name="student_search_name_trgm",
                opclasses=["gin_trgm_ops"],
            ),
        ),
    ]
