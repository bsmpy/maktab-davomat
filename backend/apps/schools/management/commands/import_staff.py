"""Заводит штат школы из подготовленного JSON: учителей, сотрудников, кураторов.

Разовая команда для наполнения реестра. Идемпотентна по паспорту: человек,
который уже есть в базе, пропускается, поэтому повторный запуск ничего не
дублирует и им же можно дозаливать список.

Кураторство здесь не отдельная должность: роль ``CURATOR`` выдаётся тому же
учителю, который ведёт этот класс, и рядом ставится ``CuratorAssignment`` и
``ClassGroup.homeroom_teacher`` — чтобы «Kuratorlar» и «Sinf rahbari» в
кабинете показывали одного и того же человека.

    manage.py import_staff --file people.json --photo ../face.jpg
"""
from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts import rbac
from apps.accounts.constants import Role
from apps.accounts.models import User
from apps.accounts.services.provisioning import generate_temporary_password
from apps.accounts.services.username import generate_username
from apps.schools.models import (
    ClassGroup,
    CuratorAssignment,
    Position,
    School,
    StaffGender,
    StaffMember,
    Subject,
    Teacher,
)

#: Русские классы (B) держат те же предметы под русскими названиями.
SUBJECT_RU = {
    "Ona tili": "Родной язык",
    "Adabiy o'qish": "Литературное чтение",
    "Adabiyot": "Литература",
    "Matematika": "Математика",
    "Algebra": "Алгебра",
    "Geometriya": "Геометрия",
    "Atrofimizdagi olam": "Окружающий мир",
    "Tabiatshunoslik": "Естествознание",
    "Tarbiya": "Воспитание",
    "Texnologiya": "Технология",
    "Tasviriy san'at": "Изобразительное искусство",
    "Musiqa": "Музыка",
    "Musiqa madaniyati": "Музыкальная культура",
    "Jismoniy tarbiya": "Физическая культура",
    "Ingliz tili": "Английский язык",
    "Rus tili": "Русский язык",
    "Biologiya": "Биология",
    "Geografiya": "География",
    "Informatika va axborot texnologiyalari": "Информатика и ИТ",
    "O'zbekiston tarixi": "История Узбекистана",
    "Jahon tarixi": "Всемирная история",
    "Fizika": "Физика",
    "Kimyo": "Химия",
    "Astronomiya": "Астрономия",
    "Chaqiriqqa qadar boshlang'ich tayyorgarlik": "Допризывная подготовка",
    "Iqtisodiy bilim asoslari": "Основы экономических знаний",
}

#: Один файл на всех: запись хранит путь, а не свою копию картинки.
SHARED_PHOTO = "shared/face.jpg"


class Command(BaseCommand):
    help = "Заводит учителей и сотрудников из JSON, раздаёт роли и кураторство."

    def add_arguments(self, parser):
        parser.add_argument("--file", required=True, help="JSON со списком людей")
        parser.add_argument("--photo", help="Фото, которое ставится всем")
        parser.add_argument(
            "--password",
            default="",
            help="Один временный пароль на всех. По умолчанию — свой на каждого.",
        )
        parser.add_argument(
            "--credentials", help="Куда выписать логины и пароли (CSV)"
        )
        parser.add_argument(
            "--relink",
            action="store_true",
            help="Не заводить людей, а пересобрать привязку предметов у тех, кто уже есть.",
        )
        parser.add_argument("--dry-run", action="store_true")

    # --------------------------------------------------------------------- #
    def handle(self, *args, **options):
        path = Path(options["file"])
        if not path.exists():
            raise CommandError(f"Нет файла {path}")
        data = json.loads(path.read_text(encoding="utf-8"))

        school = School.objects.filter(is_active=True).first()
        if school is None:
            raise CommandError("В базе нет школы.")

        photo_path = self._place_photo(options.get("photo"))
        self.stdout.write(f"Школа: {school.name} | фото: {photo_path or '—'}")

        if options["relink"]:
            with transaction.atomic():
                self._relink(data["teachers"])
                if options["dry_run"]:
                    transaction.set_rollback(True)
            return

        created: list[dict] = []
        with transaction.atomic():
            for row in data["teachers"]:
                created.append(self._teacher(row, school, photo_path, options))
            for row in data["staff"]:
                created.append(self._staff(row, school, photo_path, options))
            self._curators(data["teachers"])

            if options["dry_run"]:
                transaction.set_rollback(True)
                self.stdout.write(self.style.WARNING("dry-run: ничего не сохранено"))

        fresh = [row for row in created if row["password"]]
        self.stdout.write(
            self.style.SUCCESS(
                f"Учителей {len(data['teachers'])}, сотрудников {len(data['staff'])}; "
                f"новых аккаунтов {len(fresh)}, пропущено {len(created) - len(fresh)}"
            )
        )
        if fresh and options.get("credentials") and not options["dry_run"]:
            self._write_credentials(Path(options["credentials"]), fresh)

    # --------------------------------------------------------------------- #
    def _place_photo(self, source: str | None) -> str:
        """Кладёт картинку один раз; все записи ссылаются на один и тот же файл."""
        if not source:
            return ""
        origin = Path(source)
        if not origin.exists():
            raise CommandError(f"Нет фото {origin}")
        target = Path(settings.MEDIA_ROOT) / SHARED_PHOTO
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(origin, target)
        return SHARED_PHOTO

    def _account(self, row: dict, roles: list[str], password: str) -> tuple[User, str]:
        """Аккаунт кабинета. Уже существующий — возвращается как есть."""
        existing = User.objects.filter(phone=row["phone"]).first()
        if existing is not None:
            return existing, ""

        username = generate_username(row["first_name"], row["last_name"])
        user = User.objects.create_user(
            username=username,
            password=password,
            first_name=row["first_name"],
            last_name=row["last_name"],
            middle_name=row["middle_name"],
            phone=row["phone"],
            role=roles[0],
            # Первым входом человек меняет выданный пароль на свой.
            must_change_password=True,
        )
        rbac.set_roles(user, roles, keep_active=False)
        user.refresh_from_db()
        return user, password

    def _person_fields(self, row: dict) -> dict:
        return {
            "first_name": row["first_name"],
            "last_name": row["last_name"],
            "middle_name": row["middle_name"],
            "passport_id": row["passport"],
            "birth_date": row["birth_date"],
            "gender": StaffGender.FEMALE if row["gender"] == "Ayol" else StaffGender.MALE,
            "phone": row["phone"],
            "email": row["email"],
        }

    # --------------------------------------------------------------------- #
    def _teacher(self, row: dict, school, photo: str, options) -> dict:
        if Teacher.objects.filter(school=school, passport_id=row["passport"]).exists():
            return {"who": row["email"], "password": ""}

        roles = [Role.TEACHER] + ([Role.CURATOR] if row["curator"] else [])
        password = options["password"] or generate_temporary_password()
        user, issued = self._account(row, roles, password)

        teacher = Teacher(school=school, user=user, **self._person_fields(row))
        teacher.set_jshshir(row["jshshir"])
        if photo:
            teacher.photo = photo
        teacher.save()

        teacher.subjects.set(self._subjects_for(row))
        return {
            "who": f"{row['last_name']} {row['first_name']}",
            "username": user.username,
            "password": issued,
            "roles": ", ".join(roles),
            "kind": "O'qituvchi",
            "detail": row["role"],
        }

    def _subjects_for(self, row: dict) -> list[Subject]:
        """Ровно те пары «группа → предмет», которые посчитал учебный план.

        Не «все его предметы во всех его группах»: в 1–4 технологию и ИЗО ведёт
        классный руководитель, и то же самое название в 5-м классе принадлежит
        трудовику — перемножение привязало бы предмет к обоим.
        """
        wanted = []
        for group_name, subject in row.get("assign", []):
            grade_level, letter = group_name.split("-")
            name = SUBJECT_RU.get(subject, subject) if letter == "B" else subject
            found = Subject.objects.filter(
                class_group__grade__level=int(grade_level),
                class_group__name=letter,
                name=name,
            ).first()
            if found is None:
                self.stderr.write(f"  нет предмета: {name} {group_name}")
                continue
            wanted.append(found)
        return wanted

    def _staff(self, row: dict, school, photo: str, options) -> dict:
        if StaffMember.objects.filter(school=school, passport_id=row["passport"]).exists():
            return {"who": row["email"], "password": ""}

        password = options["password"] or generate_temporary_password()
        user, issued = self._account(row, [row["app_role"]], password)

        position = Position.objects.filter(school=school, title_uz=row["position"]).first()
        member = StaffMember(school=school, user=user, position=position,
                             **self._person_fields(row))
        member.set_jshshir(row["jshshir"])
        if photo:
            member.photo = photo
        member.save()
        return {
            "who": f"{row['last_name']} {row['first_name']}",
            "username": user.username,
            "password": issued,
            "roles": row["app_role"],
            "kind": "Xodim",
            "detail": row["position"],
        }

    def _relink(self, teachers: list[dict]) -> None:
        """Переставить предметы уже заведённым учителям."""
        touched = links = 0
        for row in teachers:
            teacher = Teacher.objects.filter(passport_id=row["passport"]).first()
            if teacher is None:
                continue
            subjects = self._subjects_for(row)
            teacher.subjects.set(subjects)
            touched += 1
            links += len(subjects)
        self.stdout.write(
            self.style.SUCCESS(f"Пересобрано: {touched} учителей, {links} привязок")
        )

    # --------------------------------------------------------------------- #
    def _curators(self, teachers: list[dict]) -> None:
        """Куратор — тот же учитель: связь с группой и он же классный руководитель."""
        linked = 0
        for row in teachers:
            if not row["curator"]:
                continue
            teacher = Teacher.objects.filter(passport_id=row["passport"]).first()
            if teacher is None or teacher.user_id is None:
                continue
            grade_level, letter = row["curator"].split("-")
            group = ClassGroup.objects.filter(
                grade__level=int(grade_level), name=letter
            ).first()
            if group is None:
                continue
            CuratorAssignment.objects.get_or_create(user=teacher.user, class_group=group)
            if group.homeroom_teacher_id is None:
                group.homeroom_teacher = teacher
                group.save(update_fields=["homeroom_teacher", "updated_at"])
            linked += 1
        self.stdout.write(f"Кураторов закреплено: {linked}")

    def _write_credentials(self, path: Path, rows: list[dict]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(["Kim", "F.I.", "Lavozim/Stavka", "Login", "Parol", "Rollar"])
            for row in rows:
                writer.writerow([
                    row["kind"], row["who"], row["detail"],
                    row["username"], row["password"], row["roles"],
                ])
        path.chmod(0o600)
        self.stdout.write(self.style.SUCCESS(f"Логины и пароли: {path}"))
