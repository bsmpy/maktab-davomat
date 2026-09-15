"""Populate a fully working demo dataset.

    python manage.py seed_demo

Creates a school, grades 1-11, class groups, subjects, teachers, a timetable,
pupils, guardians (with hashed JSHSHIR), lessons, attendance history,
notifications and ready-to-use logins — enough to exercise every screen.

``--history-days`` controls how far back attendance is generated. It also moves
the academic year's start date, so a freshly seeded database has meaningful
monthly and yearly charts on day one.
"""
from __future__ import annotations

import random
from datetime import date, datetime, time, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.constants import Role
from apps.accounts.models import User
from apps.accounts.services.username import create_user_with_username
from apps.attendance.models import Attendance, AttendanceReason, Lesson, Schedule
from apps.attendance.services.periods import today
from apps.attendance.services.scheduling import generate_lessons
from apps.audit.constants import AuditAction
from apps.audit.services import suppressed as audit_suppressed
from apps.guardians.constants import Relation
from apps.guardians.models import Guardian, GuardianStudent
from apps.notifications.constants import NotificationType
from apps.notifications.services import create_notification
from apps.schools.models import (
    AcademicYear,
    ClassGroup,
    Grade,
    Holiday,
    School,
    Subject,
    Teacher,
)
from apps.students.models import Gender, Student

DEMO_PASSWORD = "Demo!2026parol"

MALE_NAMES = [
    "Azizbek", "Sardor", "Jasur", "Bekzod", "Otabek", "Shohruh", "Diyor", "Aziz",
    "Islom", "Doniyor", "Rustam", "Ulug'bek", "Javohir", "Sanjar", "Nodir",
    "Alisher", "Farrux", "Temur", "Bobur", "Sherzod",
]
FEMALE_NAMES = [
    "Madina", "Zilola", "Nilufar", "Gulnora", "Sevinch", "Dilnoza", "Malika",
    "Shahzoda", "Ozoda", "Kamola", "Nigora", "Feruza", "Munisa", "Sabina",
    "Mohira", "Robiya", "Zarina", "Charos",
]
SURNAMES = [
    "Valiyev", "Karimov", "Rahimov", "Yusupov", "Tursunov", "Ergashev", "Nazarov",
    "Qodirov", "Sultonov", "Ibragimov", "Salimov", "Aliyev", "Hasanov", "G'ulomov",
    "Xolmatov", "Bekmurodov", "Mirzayev", "Sodiqov", "Umarov", "Jo'rayev",
]
PATRONYMICS = [
    "Anvarovich", "Baxtiyorovich", "Sanjarovich", "Ulug'bekovich", "Farhodovich",
]

SUBJECTS = [
    ("Matematika", "Mat", "#2563eb"),
    ("Ona tili", "Ona t.", "#0891b2"),
    ("Adabiyot", "Adab.", "#7c3aed"),
    ("Ingliz tili", "Ing.", "#059669"),
    ("Rus tili", "Rus t.", "#dc2626"),
    ("Fizika", "Fiz.", "#ea580c"),
    ("Kimyo", "Kim.", "#65a30d"),
    ("Biologiya", "Bio.", "#0d9488"),
    ("Tarix", "Tar.", "#b45309"),
    ("Geografiya", "Geo.", "#4f46e5"),
    ("Informatika", "Inf.", "#db2777"),
    ("Jismoniy tarbiya", "Jis.", "#475569"),
]

LESSON_TIMES = [
    (time(8, 30), time(9, 15)),
    (time(9, 25), time(10, 10)),
    (time(10, 20), time(11, 5)),
    (time(11, 25), time(12, 10)),
    (time(12, 20), time(13, 5)),
    (time(13, 15), time(14, 0)),
]

REASONS = [
    ("KASALLIK", "Kasallik", False, True, 1),
    ("OILAVIY", "Oilaviy sabab", False, False, 2),
    ("SAFAR", "Safar", False, False, 3),
    ("BOSHQA", "Boshqa", True, False, 4),
]


class Command(BaseCommand):
    help = "Ishlaydigan demo ma'lumotlarni yaratadi."

    def add_arguments(self, parser):
        parser.add_argument("--history-days", type=int, default=210)
        parser.add_argument("--students-per-class", type=int, default=10)
        parser.add_argument("--seed", type=int, default=20260908)
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Avval mavjud demo ma'lumotlarni o'chiradi.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        random.seed(options["seed"])
        self.rng = random.Random(options["seed"])

        if options["flush"]:
            self._flush()

        reference = today()
        start_date = reference - timedelta(days=options["history_days"])
        end_date = date(reference.year + 1, 5, 31)

        school = self._create_school()
        academic_year = self._create_academic_year(school, start_date, end_date)
        self._create_holidays(school, academic_year, start_date, end_date)
        grades = self._create_grades(school)
        subjects = self._create_subjects(school)
        teachers = self._create_teachers(school, subjects)
        class_groups = self._create_class_groups(school, academic_year, grades, teachers)
        self._create_reasons(school)
        self._create_schedules(academic_year, class_groups, subjects, teachers)

        students = self._create_students(school, class_groups, options["students_per_class"])
        demo_accounts = self._create_guardians(school, class_groups, students)

        self.stdout.write("Darslar yaratilmoqda...")
        created = generate_lessons(
            academic_year=academic_year, start=start_date, end=min(reference, end_date)
        )
        self.stdout.write(f"  {created} ta dars")

        self.stdout.write("Turniket yozuvlari yaratilmoqda...")
        days = self._create_presence(school, students, start_date, reference)
        self.stdout.write(f"  {days} ta kunlik kirish-chiqish yozuvi")

        self._create_teacher_accounts(teachers[:3])
        staff_accounts = self._create_staff_accounts()
        self._create_notifications(demo_accounts)

        self._report(demo_accounts, staff_accounts)

    # ------------------------------------------------------------------ #
    def _flush(self):
        self.stdout.write(self.style.WARNING("Demo ma'lumotlar o'chirilmoqda..."))
        # Attendance deletes are audited row by row (see apps/attendance/signals).
        # That is right for a real deletion but pointless — and very slow — when
        # wiping a demo dataset, so per-row auditing is suppressed and a single
        # summary entry is written instead.
        with audit_suppressed(
            {"command": "seed_demo --flush"}, action=AuditAction.ATTENDANCE_DELETE
        ):
            Attendance.objects.all().delete()

        from apps.integrations.models import DailyPresence, TerminalEvent, TerminalPerson

        TerminalEvent.objects.all().delete()
        DailyPresence.objects.all().delete()
        TerminalPerson.objects.all().delete()

        Lesson.objects.all().delete()
        Schedule.objects.all().delete()
        GuardianStudent.objects.all().delete()

        # Soft-delete models must be *hard* deleted here: their .delete() only
        # stamps deleted_at, which would leave the rows in place and trip the
        # PROTECT foreign keys further down (ClassGroup → Grade, Student → School).
        # Order matters — children before the parents they protect.
        Guardian.all_objects.all().hard_delete()
        Student.all_objects.all().hard_delete()
        ClassGroup.all_objects.all().hard_delete()
        Grade.objects.all().delete()
        Teacher.all_objects.all().hard_delete()
        Subject.all_objects.all().hard_delete()
        Holiday.objects.all().delete()
        AcademicYear.objects.all().delete()
        School.all_objects.all().hard_delete()
        User.objects.exclude(is_superuser=True).delete()

    def _create_school(self) -> School:
        school, _ = School.objects.get_or_create(
            name="Toshkent shahar 42-son umumiy o'rta ta'lim maktabi",
            defaults={
                "short_name": "42-maktab",
                "region": "Toshkent shahri",
                "district": "Yunusobod tumani",
                "address": "Yunusobod tumani, Amir Temur ko'chasi 108",
                "phone": "+998712001042",
                "working_weekdays": [1, 2, 3, 4, 5, 6],
            },
        )
        return school

    def _create_academic_year(self, school, start_date, end_date) -> AcademicYear:
        name = f"{start_date.year}-{end_date.year}"[:32]
        AcademicYear.objects.filter(school=school).update(is_current=False)
        academic_year, _ = AcademicYear.objects.get_or_create(
            school=school,
            name=name,
            defaults={"start_date": start_date, "end_date": end_date},
        )
        academic_year.start_date = start_date
        academic_year.end_date = end_date
        academic_year.is_current = True
        academic_year.save()
        return academic_year

    def _create_holidays(self, school, academic_year, start_date, end_date):
        """Summer break plus a few public holidays, so lessons skip them."""
        holidays: list[Holiday] = []
        for year in {start_date.year, end_date.year}:
            summer_start = date(year, 6, 10)
            summer_end = date(year, 8, 31)
            cursor = max(summer_start, start_date)
            while cursor <= min(summer_end, end_date):
                holidays.append(
                    Holiday(school=school, academic_year=academic_year, date=cursor, name="Yozgi ta'til")
                )
                cursor += timedelta(days=1)
            for month, day, title in (
                (1, 1, "Yangi yil"),
                (3, 8, "Xotin-qizlar kuni"),
                (3, 21, "Navro'z"),
                (5, 9, "Xotira va qadrlash kuni"),
                (9, 1, "Mustaqillik kuni"),
                (10, 1, "O'qituvchilar kuni"),
                (12, 8, "Konstitutsiya kuni"),
            ):
                holiday_date = date(year, month, day)
                if start_date <= holiday_date <= end_date:
                    holidays.append(
                        Holiday(
                            school=school,
                            academic_year=academic_year,
                            date=holiday_date,
                            name=title,
                        )
                    )
        Holiday.objects.bulk_create(holidays, ignore_conflicts=True, batch_size=500)

    def _create_grades(self, school) -> dict[int, Grade]:
        return {
            level: Grade.objects.get_or_create(school=school, level=level)[0]
            for level in range(1, 12)
        }

    def _create_subjects(self, school) -> list[Subject]:
        subjects = []
        for name, short_name, color in SUBJECTS:
            subject, _ = Subject.objects.get_or_create(
                school=school, name=name, defaults={"short_name": short_name, "color": color}
            )
            subjects.append(subject)
        return subjects

    def _create_teachers(self, school, subjects) -> list[Teacher]:
        teachers = []
        for index in range(18):
            first_name = MALE_NAMES[index % len(MALE_NAMES)] if index % 2 else FEMALE_NAMES[index % len(FEMALE_NAMES)]
            last_name = SURNAMES[(index * 3) % len(SURNAMES)]
            teacher, created = Teacher.objects.get_or_create(
                school=school,
                first_name=first_name,
                last_name=last_name,
                defaults={
                    "middle_name": PATRONYMICS[index % len(PATRONYMICS)],
                    "phone": f"+9989{self.rng.randint(10000000, 99999999)}",
                },
            )
            if created:
                teacher.subjects.set(
                    [subjects[index % len(subjects)], subjects[(index + 4) % len(subjects)]]
                )
            teachers.append(teacher)
        return teachers

    def _create_class_groups(self, school, academic_year, grades, teachers) -> list[ClassGroup]:
        groups = []
        index = 0
        for level in range(1, 12):
            names = ["A", "B"] + (["D"] if level in (1, 7) else [])
            for name in names:
                group, _ = ClassGroup.objects.get_or_create(
                    academic_year=academic_year,
                    grade=grades[level],
                    name=name,
                    defaults={
                        "school": school,
                        "homeroom_teacher": teachers[index % len(teachers)],
                        "room": f"{level}{index % 5 + 1:02d}",
                    },
                )
                groups.append(group)
                index += 1
        return groups

    def _create_reasons(self, school):
        for code, name, requires_comment, requires_document, order in REASONS:
            AttendanceReason.objects.get_or_create(
                school=school,
                code=code,
                defaults={
                    "name": name,
                    "requires_comment": requires_comment,
                    "requires_document": requires_document,
                    "order": order,
                },
            )

    def _create_schedules(self, academic_year, class_groups, subjects, teachers):
        existing = set(
            Schedule.objects.filter(academic_year=academic_year).values_list(
                "class_group_id", "weekday", "lesson_number"
            )
        )
        to_create = []
        for group_index, group in enumerate(class_groups):
            lessons_per_day = 4 if group.grade.level <= 4 else 6
            for weekday in range(1, 7):  # Monday..Saturday
                for lesson_number in range(1, lessons_per_day + 1):
                    if (group.id, weekday, lesson_number) in existing:
                        continue
                    subject = subjects[(group_index + weekday * 2 + lesson_number) % len(subjects)]
                    teacher = teachers[(group_index + lesson_number * 3 + weekday) % len(teachers)]
                    start, end = LESSON_TIMES[lesson_number - 1]
                    to_create.append(
                        Schedule(
                            academic_year=academic_year,
                            class_group=group,
                            subject=subject,
                            teacher=teacher,
                            weekday=weekday,
                            lesson_number=lesson_number,
                            start_time=start,
                            end_time=end,
                            room=group.room,
                        )
                    )
        Schedule.objects.bulk_create(to_create, batch_size=500, ignore_conflicts=True)

    def _create_students(self, school, class_groups, per_class) -> list[Student]:
        students = []
        code = 1000
        for group in class_groups:
            if group.students.exists():
                students.extend(group.students.all())
                continue
            for index in range(per_class):
                is_male = index % 2 == 0
                first_name = (
                    self.rng.choice(MALE_NAMES) if is_male else self.rng.choice(FEMALE_NAMES)
                )
                last_name = self.rng.choice(SURNAMES)
                code += 1
                birth_year = date.today().year - (group.grade.level + 6)
                student = Student(
                    school=school,
                    class_group=group,
                    first_name=first_name,
                    last_name=last_name,
                    middle_name=self.rng.choice(PATRONYMICS),
                    gender=Gender.MALE if is_male else Gender.FEMALE,
                    student_code=f"S{code}",
                    birth_date=date(birth_year, self.rng.randint(1, 12), self.rng.randint(1, 28)),
                    enrolled_on=date(date.today().year - group.grade.level + 1, 9, 1),
                )
                student.save()
                students.append(student)
        return students

    def _create_guardians(self, school, class_groups, students) -> dict:
        """Build the showcase families plus one guardian per remaining pupil."""
        by_label = {group.display_name: group for group in class_groups}
        demo: dict = {"families": []}

        # --- family 1: three children, spec §11 --------------------------- #
        children = []
        for label, first_name, gender in (
            ("7-A", "Azizbek", Gender.MALE),
            ("3-B", "Madina", Gender.FEMALE),
            ("1-A", "Sardor", Gender.MALE),
        ):
            group = by_label[label]
            student, _ = Student.objects.get_or_create(
                school=school,
                class_group=group,
                first_name=first_name,
                last_name="Valiyev" if gender == Gender.MALE else "Valiyeva",
                defaults={
                    "middle_name": "Alisherovich" if gender == Gender.MALE else "Alisherovna",
                    "gender": gender,
                    "student_code": f"D{label.replace('-', '')}{first_name[:2].upper()}",
                    "birth_date": date(
                        date.today().year - (group.grade.level + 6), 4, 12
                    ),
                },
            )
            children.append(student)
            if student not in students:
                students.append(student)

        father = self._make_guardian(
            school,
            first_name="Alisher",
            last_name="Valiyev",
            middle_name="Anvarovich",
            phone="+998901234567",
            jshshir="31234567890123",
        )
        mother = self._make_guardian(
            school,
            first_name="Nodira",
            last_name="Valiyeva",
            middle_name="Rustamovna",
            phone="+998901234568",
            jshshir="41234567890124",
        )
        for index, child in enumerate(children):
            self._link(father, child, Relation.FATHER, is_primary=index == 0)
            self._link(mother, child, Relation.MOTHER, is_primary=False)

        father_user = self._ensure_account(father)
        demo["families"].append(
            {
                "guardian": father,
                "user": father_user,
                "children": children,
                "registered": True,
            }
        )

        # --- family 2: left UNREGISTERED so the sign-up flow is testable --- #
        unregistered_child = by_label["5-A"].students.first()
        if unregistered_child is None:
            unregistered_child = children[0]
        unregistered = self._make_guardian(
            school,
            first_name="Dilshod",
            last_name="Karimov",
            middle_name="Sobirovich",
            phone="+998935558899",
            jshshir="31111222233334",
        )
        self._link(unregistered, unregistered_child, Relation.FATHER, is_primary=True)
        demo["families"].append(
            {
                "guardian": unregistered,
                "user": None,
                "children": [unregistered_child],
                "registered": False,
                "jshshir": "31111222233334",
            }
        )

        # --- one guardian for everybody else ------------------------------ #
        linked_ids = {child.id for child in children} | {unregistered_child.id}
        bulk_links = []
        counter = 50000000
        for student in students:
            if student.id in linked_ids:
                continue
            counter += 1
            guardian = self._make_guardian(
                school,
                first_name=self.rng.choice(MALE_NAMES),
                last_name=student.last_name,
                middle_name=self.rng.choice(PATRONYMICS),
                phone=f"+9989{self.rng.randint(10000000, 99999999)}",
                jshshir=f"3{counter:013d}"[:14],
            )
            bulk_links.append(
                GuardianStudent(
                    guardian=guardian,
                    student=student,
                    relation=Relation.FATHER,
                    is_primary=True,
                    verified=False,
                )
            )
        GuardianStudent.objects.bulk_create(bulk_links, batch_size=500, ignore_conflicts=True)
        return demo

    def _make_guardian(self, school, *, first_name, last_name, middle_name, phone, jshshir):
        from apps.common.crypto import hash_value

        guardian = Guardian.all_objects.filter(
            school=school, jshshir_hash=hash_value(jshshir)
        ).first()
        if guardian is not None:
            return guardian
        guardian = Guardian(
            school=school,
            first_name=first_name,
            last_name=last_name,
            middle_name=middle_name,
            phone=phone,
        )
        guardian.set_jshshir(jshshir)
        guardian.save()
        return guardian

    def _link(self, guardian, student, relation, *, is_primary):
        if is_primary and GuardianStudent.objects.filter(
            student=student, is_primary=True
        ).exclude(guardian=guardian).exists():
            is_primary = False
        GuardianStudent.objects.get_or_create(
            guardian=guardian,
            student=student,
            defaults={
                "relation": relation,
                "is_primary": is_primary,
                "verified": True,
                "verified_at": timezone.now(),
            },
        )

    def _ensure_account(self, guardian) -> User:
        if guardian.user_id:
            return guardian.user
        user = create_user_with_username(
            first_name=guardian.first_name,
            last_name=guardian.last_name,
            middle_name=guardian.middle_name,
            phone=guardian.phone,
            phone_verified_at=timezone.now(),
            role=Role.PARENT,
            password=DEMO_PASSWORD,
        )
        guardian.user = user
        guardian.save(update_fields=["user", "updated_at"])
        GuardianStudent.objects.filter(guardian=guardian).update(
            verified=True, verified_at=timezone.now()
        )
        return user

    def _create_teacher_accounts(self, teachers) -> list[User]:
        accounts = []
        for teacher in teachers:
            if teacher.user_id:
                accounts.append(teacher.user)
                continue
            user = create_user_with_username(
                first_name=teacher.first_name,
                last_name=teacher.last_name,
                middle_name=teacher.middle_name,
                role=Role.TEACHER,
                password=DEMO_PASSWORD,
            )
            teacher.user = user
            teacher.save(update_fields=["user", "updated_at"])
            accounts.append(user)
        self.teacher_accounts = accounts
        return accounts

    def _create_staff_accounts(self) -> dict[str, User]:
        """One account per privileged role, so the role split is testable.

        ``admin`` is the bootstrap DEVELOPER: unscoped, and the only role that
        may change integration credentials.
        """
        accounts: dict[str, User] = {}

        developer = User.objects.filter(username="admin").first()
        if developer is None:
            developer = User.objects.create_superuser(
                username="admin",
                password=DEMO_PASSWORD,
                first_name="Tizim",
                last_name="Dasturchi",
            )
        # An older seed may have created this account before DEVELOPER existed.
        if developer.role != Role.DEVELOPER:
            developer.role = Role.DEVELOPER
            developer.save(update_fields=["role", "updated_at"])
        accounts["DEVELOPER"] = developer

        for username, role, first, last, staff in (
            ("superadmin", Role.SUPER_ADMIN, "Bosh", "Administrator", True),
            ("maktabadmin", Role.ADMIN, "Maktab", "Administratori", True),
        ):
            user = User.objects.filter(username=username).first()
            if user is None:
                user = User.objects.create_user(
                    username=username,
                    password=DEMO_PASSWORD,
                    first_name=first,
                    last_name=last,
                    role=role,
                    is_staff=staff,
                )
            accounts[role] = user

        return accounts

    def _create_presence(self, school, students, start_date, end_date) -> int:
        """Generate turnstile passes and the presence rows derived from them.

        Attendance is measured at the gate, so the demo dataset is built the
        same way the real one is: raw passes first, then one ``DailyPresence``
        per pupil per day. Both are written in bulk — deriving 50 000 days one
        transaction at a time would take minutes.
        """
        from apps.integrations.constants import (
            EventDirection,
            PresenceSource,
            TerminalDirection,
            VerifyMode,
        )
        from apps.integrations.models import (
            DailyPresence,
            Terminal,
            TerminalEvent,
            TerminalPerson,
        )

        terminal, _created = Terminal.objects.get_or_create(
            school=school,
            name="Demo turniket",
            defaults={
                "host": "192.168.10.50",
                "direction": TerminalDirection.BOTH,
                "location": "Asosiy kirish",
                # Deliberately inactive: beat must not poll an address that is
                # not there. Real devices are added in Sozlamalar.
                "is_active": False,
            },
        )

        people = {}
        for index, student in enumerate(students, start=1):
            person, _made = TerminalPerson.objects.get_or_create(
                student=student,
                defaults={"school": school, "person_code": f"S{index:06d}"},
            )
            people[student.id] = person.person_code

        working = set(school.working_weekdays or [1, 2, 3, 4, 5, 6])
        holidays = set(
            Holiday.objects.filter(school=school, is_working_day=False).values_list(
                "date", flat=True
            )
        )
        tz = timezone.get_current_timezone()
        # A per-pupil bias makes the demo realistic: most children come in
        # almost every day, a few are frequently late or absent.
        bias = {student.id: self.rng.random() for student in students}

        events: list = []
        presence: list = []
        serial = 0
        day = start_date

        while day <= end_date:
            if day.isoweekday() not in working or day in holidays:
                day += timedelta(days=1)
                continue

            for student in students:
                roll = self.rng.random()
                # 88-94% attend, the rest simply never pass the turnstile.
                if roll > 0.88 + bias[student.id] * 0.06:
                    continue

                if self.rng.random() < 0.08:
                    arrive = time(8, self.rng.choice([40, 47, 55]))  # late
                else:
                    arrive = time(8, self.rng.choice([10, 15, 20, 24, 28]))
                leave = time(13, self.rng.choice([30, 40, 50]))

                first_in = timezone.make_aware(datetime.combine(day, arrive), tz)
                last_out = timezone.make_aware(datetime.combine(day, leave), tz)

                stamps = [(first_in, EventDirection.IN)]
                visits = []
                # Roughly one pupil in six steps out for lunch and comes back.
                if self.rng.random() < 0.17:
                    out = timezone.make_aware(datetime.combine(day, time(11, 0)), tz)
                    back = out + timedelta(minutes=self.rng.choice([20, 30, 40]))
                    stamps += [(out, EventDirection.OUT), (back, EventDirection.IN)]
                    visits.append((first_in, out))
                    visits.append((back, last_out))
                else:
                    visits.append((first_in, last_out))
                stamps.append((last_out, EventDirection.OUT))

                for moment, direction in stamps:
                    serial += 1
                    events.append(
                        TerminalEvent(
                            terminal=terminal,
                            external_id=f"seed:{serial}",
                            occurred_at=moment,
                            date=day,
                            direction=direction,
                            verify_mode=VerifyMode.FACE,
                            person_code=people[student.id],
                            person_name=student.display_name,
                            student=student,
                            processed=True,
                            processed_at=moment,
                        )
                    )

                inside = sum(
                    int((out - into).total_seconds() // 60) for into, out in visits
                )
                outside = sum(
                    int((following[0] - previous[1]).total_seconds() // 60)
                    for previous, following in zip(visits, visits[1:], strict=False)
                )
                overdue = (first_in - timezone.make_aware(
                    datetime.combine(day, time(8, 30)), tz
                )).total_seconds() / 60
                presence.append(
                    DailyPresence(
                        student=student,
                        date=day,
                        first_in_at=first_in,
                        last_out_at=last_out,
                        entries_count=sum(
                            1 for _, direction in stamps if direction == EventDirection.IN
                        ),
                        exits_count=sum(
                            1 for _, direction in stamps if direction == EventDirection.OUT
                        ),
                        source=PresenceSource.TERMINAL,
                        late_minutes=min(int(overdue), 600) if overdue > 5 else 0,
                        left_early=False,
                        inside_minutes=inside,
                        outside_minutes=outside,
                        sessions=[
                            {
                                "in": into.isoformat(),
                                "out": out.isoformat(),
                                "minutes": int((out - into).total_seconds() // 60),
                            }
                            for into, out in visits
                        ],
                        is_inside=False,
                    )
                )

            if len(events) >= 8000:
                TerminalEvent.objects.bulk_create(
                    events, batch_size=2000, ignore_conflicts=True
                )
                DailyPresence.objects.bulk_create(
                    presence, batch_size=2000, ignore_conflicts=True
                )
                events, presence = [], []

            day += timedelta(days=1)

        if events:
            TerminalEvent.objects.bulk_create(events, batch_size=2000, ignore_conflicts=True)
        if presence:
            DailyPresence.objects.bulk_create(presence, batch_size=2000, ignore_conflicts=True)

        return DailyPresence.objects.filter(
            date__gte=start_date, date__lte=end_date
        ).count()

    def _create_notifications(self, demo_accounts):
        for family in demo_accounts["families"]:
            user = family["user"]
            if user is None:
                continue
            for index, student in enumerate(family["children"][:2]):
                create_notification(
                    user=user,
                    notification_type=NotificationType.ANNOUNCEMENT,
                    title="Ota-onalar yig'ilishi",
                    message=(
                        f"{student.class_group.display_name} sinfida ota-onalar "
                        "yig'ilishi 15-sentabr kuni soat 17:00 da bo'lib o'tadi."
                    ),
                    student=student,
                    dedupe_key=f"seed:announcement:{student.id}:{index}",
                )

    def _report(self, demo_accounts, staff_accounts):
        style = self.style
        self.stdout.write("")
        self.stdout.write(style.SUCCESS("=" * 68))
        self.stdout.write(style.SUCCESS("  DEMO MA'LUMOTLAR TAYYOR"))
        self.stdout.write(style.SUCCESS("=" * 68))
        self.stdout.write(f"  Maktablar:      {School.objects.count()}")
        self.stdout.write(f"  Sinf guruhlari: {ClassGroup.objects.count()}")
        self.stdout.write(f"  O'quvchilar:    {Student.objects.count()}")
        self.stdout.write(f"  Ota-onalar:     {Guardian.objects.count()}")
        self.stdout.write(f"  Darslar:        {Lesson.objects.count()}")
        self.stdout.write(f"  Davomat:        {Attendance.objects.count()}")
        self.stdout.write("")
        self.stdout.write(style.WARNING(f"  Umumiy demo parol: {DEMO_PASSWORD}"))
        self.stdout.write("")

        for family in demo_accounts["families"]:
            guardian = family["guardian"]
            children = ", ".join(
                f"{child.display_name} ({child.class_group.display_name})"
                for child in family["children"]
            )
            if family["registered"]:
                self.stdout.write(style.SUCCESS(f"  OTA-ONA (login mavjud): {family['user'].username}"))
                self.stdout.write(f"      F.I.Sh.:   {guardian.full_name}")
                self.stdout.write(f"      Telefon:   {guardian.phone}")
                self.stdout.write(f"      Farzandlar:{children}")
            else:
                self.stdout.write(style.SUCCESS("  RO'YXATDAN O'TISHNI SINASH UCHUN (akkaunt yo'q):"))
                self.stdout.write(f"      O'quvchi:  {children}")
                self.stdout.write("      Qarindosh: OTASI (FATHER)")
                self.stdout.write(f"      JSHSHIR:   {family['jshshir']}")
                self.stdout.write(f"      Telefon:   {guardian.phone} (oxirgi 4 raqam: {guardian.phone[-4:]})")
            self.stdout.write("")

        for user in getattr(self, "teacher_accounts", [])[:3]:
            self.stdout.write(style.SUCCESS(f"  O'QITUVCHI (TEACHER): {user.username}"))
        self.stdout.write("")
        for role, label in (
            ("ADMIN", "ADMIN        (maktab boshqaruvi)"),
            ("SUPER_ADMIN", "SUPER_ADMIN  (integratsiyalarni ko'radi)"),
            ("DEVELOPER", "DEVELOPER    (to'liq huquq, /admin/ va sozlamalar)"),
        ):
            user = staff_accounts.get(role)
            if user:
                self.stdout.write(style.SUCCESS(f"  {label}: {user.username}"))
        self.stdout.write("")
        self.stdout.write(
            "  OTP kodlari SMS_PROVIDER=console rejimida backend konsoliga chiqadi\n"
            "  (OTP_EXPOSE_IN_RESPONSE=True bo'lsa API javobida ham ko'rinadi)."
        )
        self.stdout.write(style.SUCCESS("=" * 68))
