"""Materialise timetable entries into concrete lessons for a date range."""
from __future__ import annotations

from datetime import datetime, timedelta

from django.core.management.base import BaseCommand, CommandError

from apps.attendance.services.periods import today
from apps.attendance.services.scheduling import generate_lessons
from apps.schools.models import AcademicYear


class Command(BaseCommand):
    help = "Dars jadvalidan aniq darslarni yaratadi (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument("--from", dest="start", help="YYYY-MM-DD (default: bugun)")
        parser.add_argument("--to", dest="end", help="YYYY-MM-DD (default: +14 kun)")
        parser.add_argument("--academic-year", dest="academic_year", help="O'quv yili nomi")

    def handle(self, *args, **options):
        start = (
            datetime.strptime(options["start"], "%Y-%m-%d").date()
            if options["start"]
            else today()
        )
        end = (
            datetime.strptime(options["end"], "%Y-%m-%d").date()
            if options["end"]
            else start + timedelta(days=14)
        )
        if end < start:
            raise CommandError("--to sanasi --from dan keyin bo'lishi kerak.")

        years = AcademicYear.objects.select_related("school")
        if options["academic_year"]:
            years = years.filter(name=options["academic_year"])
        else:
            years = years.filter(is_current=True)
        if not years.exists():
            raise CommandError("Mos o'quv yili topilmadi.")

        total = 0
        for academic_year in years:
            window_start = max(start, academic_year.start_date)
            window_end = min(end, academic_year.end_date)
            if window_start > window_end:
                continue
            created = generate_lessons(
                academic_year=academic_year, start=window_start, end=window_end
            )
            total += created
            self.stdout.write(f"{academic_year.name}: {created} ta dars yaratildi.")

        self.stdout.write(self.style.SUCCESS(f"Jami {total} ta dars yaratildi."))
