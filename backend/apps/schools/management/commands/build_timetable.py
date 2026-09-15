"""Строит недельное расписание на всю школу: 6 уроков в день, две смены.

Часы берутся из учебного плана ниже, учитель — из связи «фан → o'qituvchi»
в реестре, а сама раскладка считается в
:mod:`apps.attendance.services.timetable_builder`, который гарантирует, что
ни один учитель не стоит в двух местах одновременно.

Звонки:

* 1-смена (1–4, 10–11-синфлар) — 08:00–13:00
* 2-смена (5–9-синфлар)        — 13:10–18:10

Урок 45 минут, перемена 5, после третьего урока 10. Смены не пересекаются во
времени, поэтому один учитель может вести в обеих, и накладка считается внутри
смены, а не по номеру звонка.

    manage.py build_timetable --replace
"""
from __future__ import annotations

from datetime import time

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.attendance.models import Schedule
from apps.attendance.services.timetable_builder import (
    Course,
    GroupPlan,
    TimetableError,
    audit,
    build,
)
from apps.schools.models import AcademicYear, ClassGroup, School, Subject

#: Учебный план: часов в неделю. Сумма по классу = 6 уроков × учебных дней.
PLAN: dict[int, dict[str, int]] = {
    1: {"Ona tili": 7, "Adabiy o'qish": 4, "Matematika": 5, "Atrofimizdagi olam": 2,
        "Tarbiya": 1, "Texnologiya": 2, "Tasviriy san'at": 2, "Musiqa": 2,
        "Jismoniy tarbiya": 3, "Ingliz tili": 2},
    2: {"Ona tili": 6, "Adabiy o'qish": 4, "Matematika": 5, "Atrofimizdagi olam": 2,
        "Rus tili": 2, "Tarbiya": 1, "Texnologiya": 2, "Tasviriy san'at": 2,
        "Musiqa": 2, "Jismoniy tarbiya": 3, "Ingliz tili": 1},
    3: {"Ona tili": 6, "Adabiy o'qish": 4, "Matematika": 5, "Tabiatshunoslik": 2,
        "Rus tili": 2, "Tarbiya": 1, "Texnologiya": 2, "Tasviriy san'at": 2,
        "Musiqa": 2, "Jismoniy tarbiya": 3, "Ingliz tili": 1},
    5: {"Ona tili": 4, "Adabiyot": 3, "Matematika": 6, "Ingliz tili": 3, "Rus tili": 3,
        "O'zbekiston tarixi": 2, "Geografiya": 2, "Biologiya": 2,
        "Informatika va axborot texnologiyalari": 2, "Musiqa madaniyati": 2,
        "Jismoniy tarbiya": 3, "Texnologiya": 3, "Tarbiya": 1},
    6: {"Ona tili": 3, "Adabiyot": 3, "Matematika": 5, "Ingliz tili": 3, "Rus tili": 2,
        "O'zbekiston tarixi": 2, "Jahon tarixi": 2, "Geografiya": 2, "Biologiya": 2,
        "Fizika": 2, "Informatika va axborot texnologiyalari": 2,
        "Musiqa madaniyati": 1, "Jismoniy tarbiya": 3, "Texnologiya": 3, "Tarbiya": 1},
    7: {"Ona tili": 2, "Adabiyot": 3, "Algebra": 3, "Geometriya": 2, "Ingliz tili": 3,
        "Rus tili": 2, "O'zbekiston tarixi": 2, "Jahon tarixi": 2, "Geografiya": 2,
        "Biologiya": 2, "Fizika": 2, "Kimyo": 2,
        "Informatika va axborot texnologiyalari": 2, "Musiqa madaniyati": 1,
        "Jismoniy tarbiya": 3, "Texnologiya": 2, "Tarbiya": 1},
    8: {"Ona tili": 2, "Adabiyot": 3, "Algebra": 3, "Geometriya": 2, "Ingliz tili": 3,
        "Rus tili": 2, "O'zbekiston tarixi": 2, "Jahon tarixi": 2, "Geografiya": 2,
        "Biologiya": 2, "Fizika": 3, "Kimyo": 2,
        "Informatika va axborot texnologiyalari": 2, "Jismoniy tarbiya": 3,
        "Texnologiya": 2, "Tarbiya": 1},
    10: {"Ona tili": 2, "Adabiyot": 3, "Algebra": 3, "Geometriya": 2, "Ingliz tili": 3,
         "Rus tili": 2, "O'zbekiston tarixi": 2, "Jahon tarixi": 2, "Geografiya": 2,
         "Biologiya": 2, "Fizika": 2, "Kimyo": 2,
         "Informatika va axborot texnologiyalari": 2, "Jismoniy tarbiya": 3,
         "Chaqiriqqa qadar boshlang'ich tayyorgarlik": 2,
         "Iqtisodiy bilim asoslari": 1, "Tarbiya": 1},
    11: {"Ona tili": 2, "Adabiyot": 3, "Algebra": 3, "Geometriya": 2, "Ingliz tili": 3,
         "Rus tili": 2, "O'zbekiston tarixi": 2, "Jahon tarixi": 2, "Geografiya": 1,
         "Biologiya": 2, "Fizika": 2, "Astronomiya": 1, "Kimyo": 2,
         "Informatika va axborot texnologiyalari": 2, "Jismoniy tarbiya": 3,
         "Chaqiriqqa qadar boshlang'ich tayyorgarlik": 2,
         "Iqtisodiy bilim asoslari": 1, "Tarbiya": 1},
}
PLAN[4] = dict(PLAN[3])
PLAN[9] = dict(PLAN[8])

#: Русские классы держат те же предметы под русскими названиями.
SUBJECT_RU = {
    "Ona tili": "Родной язык", "Adabiy o'qish": "Литературное чтение",
    "Adabiyot": "Литература", "Matematika": "Математика", "Algebra": "Алгебра",
    "Geometriya": "Геометрия", "Atrofimizdagi olam": "Окружающий мир",
    "Tabiatshunoslik": "Естествознание", "Tarbiya": "Воспитание",
    "Texnologiya": "Технология", "Tasviriy san'at": "Изобразительное искусство",
    "Musiqa": "Музыка", "Musiqa madaniyati": "Музыкальная культура",
    "Jismoniy tarbiya": "Физическая культура", "Ingliz tili": "Английский язык",
    "Rus tili": "Русский язык", "Biologiya": "Биология", "Geografiya": "География",
    "Informatika va axborot texnologiyalari": "Информатика и ИТ",
    "O'zbekiston tarixi": "История Узбекистана", "Jahon tarixi": "Всемирная история",
    "Fizika": "Физика", "Kimyo": "Химия", "Astronomiya": "Астрономия",
    "Chaqiriqqa qadar boshlang'ich tayyorgarlik": "Допризывная подготовка",
    "Iqtisodiy bilim asoslari": "Основы экономических знаний",
}

#: Первая смена — младшие и выпускные; вторая — середина школы.
SHIFT_1_GRADES = {1, 2, 3, 4, 10, 11}
#: 1–4 учатся пять дней, остальные шесть.
DAYS_1_4 = (1, 2, 3, 4, 5)
DAYS_5_11 = (1, 2, 3, 4, 5, 6)

LESSON_MINUTES = 45
#: Начало каждого урока смены. Перемена 5 минут, после третьего — 10.
BELLS = {
    1: [time(8, 0), time(8, 50), time(9, 40), time(10, 35), time(11, 25), time(12, 15)],
    2: [time(13, 10), time(14, 0), time(14, 50), time(15, 45), time(16, 35), time(17, 25)],
}


def _end_of(start: time) -> time:
    minute = start.hour * 60 + start.minute + LESSON_MINUTES
    return time(minute // 60, minute % 60)


class Command(BaseCommand):
    help = "Строит недельное расписание для всех групп без накладок по учителям."

    def add_arguments(self, parser):
        parser.add_argument(
            "--replace", action="store_true",
            help="Снести прежнее расписание этого учебного года и построить заново.",
        )
        parser.add_argument("--seed", type=int, default=7)
        parser.add_argument("--dry-run", action="store_true")

    # --------------------------------------------------------------------- #
    def handle(self, *args, **options):
        school = School.objects.filter(is_active=True).first()
        if school is None:
            raise CommandError("В базе нет школы.")
        year = (
            AcademicYear.objects.filter(school=school, is_current=True).first()
            or AcademicYear.objects.filter(school=school).order_by("-start_date").first()
        )
        if year is None:
            raise CommandError("Нет учебного года.")

        plans, owners = self._collect(school)
        self.stdout.write(
            f"{school.name} · {year.name} · групп {len(plans)} · "
            f"уроков в неделю {sum(p.total_hours for p in plans)}"
        )

        try:
            placements = build(plans, seed=options["seed"])
        except TimetableError as error:
            raise CommandError(str(error)) from None

        problems = audit(plans, placements)
        if problems:
            for name, rows in problems.items():
                self.stderr.write(f"{name}: {rows[:4]}")
            raise CommandError("Расписание не прошло проверку, ничего не записано.")
        self.stdout.write(self.style.SUCCESS(f"Проверка пройдена: {len(placements)} уроков"))

        with transaction.atomic():
            self._write(placements, plans, owners, year, options["replace"])
            if options["dry_run"]:
                transaction.set_rollback(True)
                self.stdout.write(self.style.WARNING("dry-run: ничего не сохранено"))
        self._report(placements, plans)

    # --------------------------------------------------------------------- #
    def _collect(self, school) -> tuple[list[GroupPlan], dict]:
        """Собрать план по группам: предмет, его учитель и часы из плана."""
        plans: list[GroupPlan] = []
        owners: dict[tuple[str, str], object] = {}

        groups = (
            ClassGroup.objects.filter(school=school, is_active=True)
            .select_related("grade")
            .order_by("grade__level", "name")
        )
        for group in groups:
            level = group.grade.level
            if level not in PLAN:
                raise CommandError(f"Нет учебного плана для {level} класса.")
            russian = group.name == "B"

            courses = []
            for subject_uz, hours in PLAN[level].items():
                name = SUBJECT_RU.get(subject_uz, subject_uz) if russian else subject_uz
                subject = (
                    Subject.objects.filter(class_group=group, name=name)
                    .prefetch_related("teachers")
                    .first()
                )
                if subject is None:
                    raise CommandError(f"{group.display_name}: нет предмета «{name}»")
                teacher = subject.teachers.first()
                if teacher is None:
                    raise CommandError(
                        f"{group.display_name}: у «{name}» нет учителя — "
                        "сначала заведите преподавателя"
                    )
                key = str(subject.id)
                courses.append(Course(subject=key, teacher=str(teacher.id), hours=hours))
                owners[(group.display_name, key)] = (subject, teacher, group)

            plans.append(GroupPlan(
                group=group.display_name,
                shift=1 if level in SHIFT_1_GRADES else 2,
                days=DAYS_1_4 if level <= 4 else DAYS_5_11,
                courses=tuple(courses),
            ))
        return plans, owners

    def _write(self, placements, plans, owners, year, replace: bool) -> None:
        shift_of = {plan.group: plan.shift for plan in plans}
        if replace:
            removed = Schedule.objects.filter(academic_year=year).delete()[0]
            self.stdout.write(f"Прежних записей удалено: {removed}")
        elif Schedule.objects.filter(academic_year=year).exists():
            raise CommandError(
                "Расписание на этот год уже есть. Нужен --replace, чтобы заменить."
            )

        rows = []
        for row in placements:
            subject, teacher, group = owners[(row.group, row.subject)]
            start = BELLS[shift_of[row.group]][row.slot - 1]
            rows.append(Schedule(
                academic_year=year,
                class_group=group,
                subject=subject,
                teacher=teacher,
                weekday=row.weekday,
                lesson_number=row.slot,
                start_time=start,
                end_time=_end_of(start),
                # Своя комната у каждой группы; смены делят её по времени.
                room=group.room or "",
            ))
        Schedule.objects.bulk_create(rows, batch_size=500)
        self.stdout.write(self.style.SUCCESS(f"Записано: {len(rows)} строк расписания"))

    # --------------------------------------------------------------------- #
    def _report(self, placements, plans) -> None:
        from collections import defaultdict

        shift_of = {plan.group: plan.shift for plan in plans}
        per_teacher: dict[str, int] = defaultdict(int)
        per_shift: dict[int, int] = defaultdict(int)
        for row in placements:
            per_teacher[row.teacher] += 1
            per_shift[shift_of[row.group]] += 1

        loads = sorted(per_teacher.values())
        self.stdout.write(
            f"1-смена: {per_shift[1]} уроков · 2-смена: {per_shift[2]} · "
            f"учителей задействовано {len(per_teacher)}"
        )
        self.stdout.write(
            f"Нагрузка: мин {loads[0]}, медиана {loads[len(loads) // 2]}, "
            f"макс {loads[-1]} часов в неделю"
        )
