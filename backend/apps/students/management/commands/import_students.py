"""Import pupils + guardians from an Excel workbook."""
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.audit.constants import AuditAction
from apps.audit.services import log_action
from apps.schools.models import AcademicYear, School
from apps.schools.services.imports import ImportError_, import_workbook


class Command(BaseCommand):
    help = (
        "Excel fayldan o'quvchi va ota-onalarni import qiladi. "
        "Standart holatda faqat tekshiradi (preview); saqlash uchun --commit bering."
    )

    def add_arguments(self, parser):
        parser.add_argument("file", nargs="?", help=".xlsx fayl yo'li")
        parser.add_argument(
            "--make-template",
            metavar="PATH",
            help="Bo'sh namuna .xlsx faylni shu yo'lga yozadi va chiqadi.",
        )
        parser.add_argument("--school", help="Maktab nomi yoki qisqa nomi")
        parser.add_argument("--academic-year", help="O'quv yili nomi")
        parser.add_argument(
            "--commit", action="store_true", help="Haqiqatan ham bazaga yozish."
        )

    def handle(self, *args, **options):
        if options["make_template"]:
            from apps.schools.services.template import build_template

            with open(options["make_template"], "wb") as handle:
                handle.write(build_template())
            self.stdout.write(self.style.SUCCESS(f"Namuna yozildi: {options['make_template']}"))
            return

        if not options["file"]:
            raise CommandError("Fayl yo'lini bering yoki --make-template dan foydalaning.")

        school = (
            School.objects.filter(name__icontains=options["school"]).first()
            if options["school"]
            else School.objects.filter(is_active=True).first()
        )
        if school is None:
            raise CommandError("Maktab topilmadi.")

        academic_year = (
            AcademicYear.objects.filter(school=school, name=options["academic_year"]).first()
            if options["academic_year"]
            else AcademicYear.objects.filter(school=school, is_current=True).first()
        )
        if academic_year is None:
            raise CommandError("O'quv yili topilmadi.")

        try:
            with open(options["file"], "rb") as handle:
                report = import_workbook(
                    handle, school=school, academic_year=academic_year, dry_run=not options["commit"]
                )
        except ImportError_ as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(f"Jami qatorlar:        {report.total_rows}")
        self.stdout.write(f"O'quvchi yaratiladi:  {report.students_created}")
        self.stdout.write(f"O'quvchi yangilanadi: {report.students_updated}")
        self.stdout.write(f"Ota-ona yaratiladi:   {report.guardians_created}")
        self.stdout.write(f"Ota-ona yangilanadi:  {report.guardians_updated}")
        self.stdout.write(f"Yangi bog'lanishlar:  {report.links_created}")

        for error in report.errors[:50]:
            self.stderr.write(self.style.ERROR(f"  {error.row}-qator [{error.column}]: {error.message}"))
        if len(report.errors) > 50:
            self.stderr.write(f"  ... yana {len(report.errors) - 50} ta xatolik")

        if not options["commit"]:
            self.stdout.write(
                self.style.WARNING("PREVIEW rejimi — hech narsa saqlanmadi. --commit bering.")
            )
            return
        if report.errors:
            raise CommandError("Xatoliklar tufayli import bekor qilindi.")

        log_action(
            AuditAction.IMPORT_STUDENTS,
            metadata={
                "students_created": report.students_created,
                "guardians_created": report.guardians_created,
                "links_created": report.links_created,
            },
        )
        self.stdout.write(self.style.SUCCESS("Import muvaffaqiyatli yakunlandi."))
