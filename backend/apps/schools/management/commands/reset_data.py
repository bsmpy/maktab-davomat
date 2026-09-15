"""Wipe the operational data and start from an empty register.

    python manage.py reset_data --keep-user bsm --yes

Everything a school produces goes: the register (schools, grades, groups,
pupils, guardians), everything derived from it (turnstile passes, presence,
attendance history, notifications) and every account except the ones named with
``--keep-user``.

**Configuration stays.** Integration rows carry live credentials — the bot
token, SMS login, terminal passwords — and the periodic-task schedule is setup,
not data. Wiping those would take the running bot offline, which is not what
"clear the demo data" means. Pass ``--integrations`` to drop them too.

This is irreversible: take a dump first.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import User
from apps.attendance.models import (
    AbsenceRequest,
    Attendance,
    AttendanceHistory,
    AttendanceReason,
    Lesson,
    Schedule,
)
from apps.audit.constants import AuditAction
from apps.audit.models import AuditLog
from apps.audit.services import suppressed as audit_suppressed
from apps.guardians.models import Guardian, GuardianStudent
from apps.integrations.models import (
    DailyPresence,
    Integration,
    Terminal,
    TerminalEvent,
    TerminalPerson,
)
from apps.notifications.models import Notification, NotificationDelivery
from apps.schools.models import (
    AcademicYear,
    ClassGroup,
    Grade,
    Holiday,
    School,
    Subject,
    Teacher,
)
from apps.students.models import Student
from apps.telegram.models import TelegramAccount, TelegramLinkToken


class Command(BaseCommand):
    help = "Delete every school record and account, keeping only the named users."

    def add_arguments(self, parser):
        parser.add_argument(
            "--keep-user",
            action="append",
            default=[],
            metavar="USERNAME",
            help="Account to keep. Repeatable. At least one is required.",
        )
        parser.add_argument(
            "--integrations",
            action="store_true",
            help="Also delete integration rows (bot token, SMS and device credentials).",
        )
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Required. Without it nothing is deleted and a preview is printed.",
        )

    def handle(self, *args, **options):
        keep = [name.strip().lower() for name in options["keep_user"] if name.strip()]
        if not keep:
            raise CommandError(
                "Refusing to delete every account: pass --keep-user <username>."
            )

        survivors = list(User.objects.filter(username__in=keep))
        missing = set(keep) - {user.username for user in survivors}
        if missing:
            raise CommandError(f"No such account: {', '.join(sorted(missing))}")

        counts = self._counts(options["integrations"])
        self._preview(counts, survivors, options["integrations"])

        if not options["yes"]:
            self.stdout.write(
                self.style.WARNING("\nDry run — nothing deleted. Re-run with --yes.")
            )
            return

        self._wipe(keep=keep, integrations=options["integrations"])
        self.stdout.write(self.style.SUCCESS("\nDone. The register is empty."))
        self._report_remaining()

    # ------------------------------------------------------------------ #
    def _counts(self, integrations: bool) -> list[tuple[str, int]]:
        rows = [
            ("Turniket hodisalari", TerminalEvent.objects.count()),
            ("Kunlik davomat", DailyPresence.objects.count()),
            ("Terminal shaxslari", TerminalPerson.objects.count()),
            ("Davomat yozuvlari", Attendance.objects.count()),
            ("Davomat tarixi", AttendanceHistory.objects.count()),
            ("Sabab arizalari", AbsenceRequest.objects.count()),
            ("Darslar", Lesson.objects.count()),
            ("Dars jadvallari", Schedule.objects.count()),
            ("O'quvchilar", Student.all_objects.count()),
            ("Ota-onalar", Guardian.all_objects.count()),
            ("Sinf guruhlari", ClassGroup.all_objects.count()),
            ("Sinflar", Grade.all_objects.count()),
            ("Maktablar", School.all_objects.count()),
            ("Bildirishnomalar", Notification.objects.count()),
            ("Telegram akkauntlari", TelegramAccount.objects.count()),
            ("Audit yozuvlari", AuditLog.objects.count()),
        ]
        if integrations:
            rows.append(("Integratsiyalar", Integration.objects.count()))
            rows.append(("Terminallar", Terminal.all_objects.count()))
        return rows

    def _preview(self, counts, survivors, integrations: bool) -> None:
        self.stdout.write(self.style.WARNING("O'chiriladi:"))
        for label, count in counts:
            if count:
                self.stdout.write(f"  {label:<24} {count}")

        doomed = User.objects.exclude(
            username__in=[user.username for user in survivors]
        ).count()
        self.stdout.write(f"  {'Foydalanuvchilar':<24} {doomed}")

        self.stdout.write(self.style.SUCCESS("\nQoladi:"))
        for user in survivors:
            self.stdout.write(f"  {user.username} ({user.role})")
        if not integrations:
            self.stdout.write(
                "  Integratsiya sozlamalari (bot tokeni, SMS, terminal parollari)"
            )
            self.stdout.write("  Davriy vazifalar jadvali")

    # ------------------------------------------------------------------ #
    @transaction.atomic
    def _wipe(self, *, keep: list[str], integrations: bool) -> None:
        self.stdout.write("\nO'chirilmoqda...")

        # Attendance rows are audited one by one, which is right for a single
        # correction and pointless for a wipe — write one summary instead.
        with audit_suppressed(
            {"command": "reset_data"}, action=AuditAction.ATTENDANCE_DELETE
        ):
            AttendanceHistory.objects.all().delete()
            Attendance.objects.all().delete()

        # Derived from the gate, so it goes before the people it points at.
        TerminalEvent.objects.all().delete()
        DailyPresence.objects.all().delete()
        TerminalPerson.objects.all().delete()

        NotificationDelivery.objects.all().delete()
        Notification.objects.all().delete()
        TelegramLinkToken.objects.all().delete()
        TelegramAccount.objects.all().delete()

        AbsenceRequest.objects.all().delete()
        AttendanceReason.objects.all().delete()
        Lesson.objects.all().delete()
        Schedule.objects.all().delete()
        GuardianStudent.objects.all().delete()

        # Soft-delete models need a *hard* delete here: their .delete() only
        # stamps deleted_at, which would leave the rows in place and trip the
        # PROTECT foreign keys below. Children before the parents they protect.
        Guardian.all_objects.all().hard_delete()
        Student.all_objects.all().hard_delete()
        Holiday.objects.all().delete()
        ClassGroup.all_objects.all().hard_delete()
        Teacher.all_objects.all().hard_delete()
        Subject.all_objects.all().hard_delete()
        Grade.all_objects.all().hard_delete()
        AcademicYear.objects.all().delete()

        if integrations:
            Terminal.all_objects.all().hard_delete()
            Integration.objects.all().delete()

        School.all_objects.all().hard_delete()

        # Audit entries point at users; clear the trail before the accounts.
        AuditLog.objects.all().delete()
        User.objects.exclude(username__in=keep).delete()

    def _report_remaining(self) -> None:
        self.stdout.write("\nQolgan foydalanuvchilar:")
        for user in User.objects.order_by("username"):
            self.stdout.write(f"  {user.username:<20} {user.role}")
        self.stdout.write(
            f"\nMaktablar: {School.objects.count()}  "
            f"O'quvchilar: {Student.objects.count()}  "
            f"Integratsiyalar: {Integration.objects.count()}"
        )
