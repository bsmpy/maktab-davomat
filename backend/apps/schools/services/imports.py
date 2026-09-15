"""Excel import of pupils and guardians.

Two-phase by design: the whole workbook is validated first and the caller can
run it with ``dry_run=True`` to preview exactly what would change. Nothing is
written unless every structural check passes, and rows that match an existing
person are *updated*, never duplicated.

Matching keys
-------------
* pupil    – (school, class group, normalised full name) or ``student_code``
* guardian – (school, JSHSHIR hash); the JSHSHIR is hashed on the way in and
             never stored or logged in the clear
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import IO

from django.db import transaction

from apps.common.crypto import hash_value, normalize_jshshir
from apps.common.phone import InvalidPhoneNumber, normalize_phone
from apps.common.text import normalize_name, transliterate
from apps.guardians.constants import Relation
from apps.guardians.models import Guardian, GuardianStudent
from apps.students.models import Gender, Student

from ..models import ClassGroup

REQUIRED_COLUMNS = (
    "student_first_name",
    "student_last_name",
    "grade",
    "class_group",
    "guardian_first_name",
    "guardian_last_name",
    "guardian_jshshir",
    "guardian_phone",
    "guardian_relation",
)
OPTIONAL_COLUMNS = (
    "student_middle_name",
    "student_code",
    "student_birth_date",
    "student_gender",
    "guardian_middle_name",
    "guardian_is_primary",
)


@dataclass
class RowError:
    row: int
    column: str
    message: str

    def to_dict(self) -> dict:
        return {"row": self.row, "column": self.column, "message": self.message}


@dataclass
class ImportReport:
    dry_run: bool = True
    total_rows: int = 0
    students_created: int = 0
    students_updated: int = 0
    guardians_created: int = 0
    guardians_updated: int = 0
    links_created: int = 0
    links_skipped: int = 0
    errors: list[RowError] = field(default_factory=list)
    preview: list[dict] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict:
        return {
            "dry_run": self.dry_run,
            "ok": self.ok,
            "total_rows": self.total_rows,
            "students_created": self.students_created,
            "students_updated": self.students_updated,
            "guardians_created": self.guardians_created,
            "guardians_updated": self.guardians_updated,
            "links_created": self.links_created,
            "links_skipped": self.links_skipped,
            "errors": [error.to_dict() for error in self.errors],
            "preview": self.preview[:50],
        }


class ImportError_(Exception):
    pass


def _cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, (dt.date, dt.datetime)):
        return value.isoformat()[:10]
    return str(value).strip()


def _read_rows(stream: IO[bytes]) -> tuple[list[str], list[tuple[int, dict]]]:
    from openpyxl import load_workbook

    workbook = load_workbook(stream, read_only=True, data_only=True)
    sheet = workbook.active
    rows = sheet.iter_rows(values_only=True)

    try:
        header_row = next(rows)
    except StopIteration:
        raise ImportError_("Fayl bo'sh.") from None

    headers = [(_cell(cell) or "").lower().replace(" ", "_") for cell in header_row]
    missing = [column for column in REQUIRED_COLUMNS if column not in headers]
    if missing:
        raise ImportError_(f"Quyidagi ustunlar yetishmayapti: {', '.join(missing)}")

    parsed: list[tuple[int, dict]] = []
    for index, raw in enumerate(rows, start=2):
        record = {header: _cell(value) for header, value in zip(headers, raw, strict=False) if header}
        if not any(record.get(column) for column in REQUIRED_COLUMNS):
            continue  # blank spacer row
        parsed.append((index, record))
    workbook.close()
    return headers, parsed


_RELATION_ALIASES = {
    "father": Relation.FATHER,
    "ota": Relation.FATHER,
    "otasi": Relation.FATHER,
    "mother": Relation.MOTHER,
    "ona": Relation.MOTHER,
    "onasi": Relation.MOTHER,
    "guardian": Relation.GUARDIAN,
    "vasiy": Relation.GUARDIAN,
    "vasiysi": Relation.GUARDIAN,
    "other": Relation.OTHER,
    "boshqa": Relation.OTHER,
}


def _parse_relation(value: str) -> str | None:
    key = (value or "").strip().lower()
    if key.upper() in Relation.values:
        return key.upper()
    return _RELATION_ALIASES.get(key)


def _parse_date(value: str) -> dt.date | None:
    value = (value or "").strip()
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
        try:
            return dt.datetime.strptime(value[:10], fmt).date()
        except ValueError:
            continue
    return None


def _validate_row(row_number: int, record: dict, class_groups: dict) -> tuple[dict | None, list[RowError]]:
    errors: list[RowError] = []

    grade_raw = record.get("grade", "")
    group_raw = (record.get("class_group", "") or "").strip().upper()
    try:
        grade_level = int(float(grade_raw))
    except (TypeError, ValueError):
        errors.append(RowError(row_number, "grade", f"Sinf raqami noto'g'ri: '{grade_raw}'"))
        grade_level = None

    class_group = class_groups.get((grade_level, group_raw)) if grade_level else None
    if grade_level and class_group is None:
        errors.append(
            RowError(row_number, "class_group", f"{grade_level}-{group_raw} sinfi topilmadi.")
        )

    if not record.get("student_first_name") or not record.get("student_last_name"):
        errors.append(RowError(row_number, "student_name", "O'quvchining ism-familiyasi bo'sh."))

    jshshir = None
    try:
        jshshir = normalize_jshshir(record.get("guardian_jshshir", ""))
    except ValueError:
        errors.append(
            RowError(row_number, "guardian_jshshir", "JSHSHIR 14 ta raqamdan iborat bo'lishi kerak.")
        )

    phone = None
    try:
        phone = normalize_phone(record.get("guardian_phone", ""))
    except InvalidPhoneNumber as exc:
        errors.append(RowError(row_number, "guardian_phone", str(exc)))

    relation = _parse_relation(record.get("guardian_relation", ""))
    if relation is None:
        errors.append(
            RowError(
                row_number,
                "guardian_relation",
                "Qarindoshlik turi noto'g'ri (FATHER/MOTHER/GUARDIAN/OTHER).",
            )
        )

    gender = (record.get("student_gender", "") or "").strip().upper()
    if gender and gender not in Gender.values:
        gender = ""

    if errors:
        return None, errors

    return (
        {
            "class_group": class_group,
            "student": {
                "first_name": normalize_name(record["student_first_name"]),
                "last_name": normalize_name(record["student_last_name"]),
                "middle_name": normalize_name(record.get("student_middle_name", "")),
                "student_code": (record.get("student_code", "") or "").strip(),
                "birth_date": _parse_date(record.get("student_birth_date", "")),
                "gender": gender,
            },
            "guardian": {
                "first_name": normalize_name(record["guardian_first_name"]),
                "last_name": normalize_name(record["guardian_last_name"]),
                "middle_name": normalize_name(record.get("guardian_middle_name", "")),
                "jshshir": jshshir,
                "phone": phone,
            },
            "relation": relation,
            "is_primary": (record.get("guardian_is_primary", "") or "").strip().lower()
            in {"1", "true", "yes", "ha"},
        },
        [],
    )


def import_workbook(stream: IO[bytes], *, school, academic_year, dry_run: bool = True) -> ImportReport:
    report = ImportReport(dry_run=dry_run)

    _headers, rows = _read_rows(stream)
    report.total_rows = len(rows)

    class_groups = {
        (group.grade.level, group.name): group
        for group in ClassGroup.objects.filter(
            school=school, academic_year=academic_year, is_active=True
        ).select_related("grade")
    }

    prepared: list[tuple[int, dict]] = []
    for row_number, record in rows:
        parsed, errors = _validate_row(row_number, record, class_groups)
        if errors:
            report.errors.extend(errors)
            continue
        prepared.append((row_number, parsed))

    # Detect duplicate (student, guardian) pairs inside the file itself.
    seen_pairs: set[tuple[str, str]] = set()
    for row_number, parsed in prepared:
        key = (
            transliterate(
                f"{parsed['student']['last_name']}{parsed['student']['first_name']}"
                f"{parsed['class_group'].id}"
            ),
            parsed["guardian"]["jshshir"],
        )
        if key in seen_pairs:
            report.errors.append(
                RowError(row_number, "duplicate", "Faylda takrorlangan o'quvchi/ota-ona juftligi.")
            )
        seen_pairs.add(key)

    if report.errors and dry_run is False:
        # Refuse a partial import: fix the file, then re-run.
        return report

    with transaction.atomic():
        for row_number, parsed in prepared:
            student, student_created = _upsert_student(school, parsed)
            guardian, guardian_created = _upsert_guardian(school, parsed)
            link_created = _upsert_link(guardian, student, parsed)

            report.students_created += int(student_created)
            report.students_updated += int(not student_created)
            report.guardians_created += int(guardian_created)
            report.guardians_updated += int(not guardian_created)
            report.links_created += int(link_created)
            report.links_skipped += int(not link_created)

            report.preview.append(
                {
                    "row": row_number,
                    "student": f"{parsed['student']['last_name']} {parsed['student']['first_name']}",
                    "class_group": parsed["class_group"].display_name,
                    "guardian": f"{parsed['guardian']['last_name']} {parsed['guardian']['first_name']}",
                    "relation": parsed["relation"],
                    "student_action": "created" if student_created else "updated",
                    "guardian_action": "created" if guardian_created else "updated",
                    "link_action": "created" if link_created else "exists",
                }
            )

        if dry_run:
            transaction.set_rollback(True)

    return report


def _upsert_student(school, parsed) -> tuple[Student, bool]:
    data = parsed["student"]
    class_group = parsed["class_group"]

    student = None
    if data["student_code"]:
        student = Student.all_objects.filter(
            school=school, student_code__iexact=data["student_code"]
        ).first()
    if student is None:
        student = Student.all_objects.filter(
            school=school,
            class_group=class_group,
            search_name=transliterate(
                " ".join(
                    part
                    for part in (data["last_name"], data["first_name"], data["middle_name"])
                    if part
                )
            ),
        ).first()

    created = student is None
    if created:
        student = Student(school=school, class_group=class_group)
    for attribute, value in data.items():
        if value or created:
            setattr(student, attribute, value)
    student.class_group = class_group
    student.school = school
    student.is_active = True
    student.deleted_at = None
    student.save()
    return student, created


def _upsert_guardian(school, parsed) -> tuple[Guardian, bool]:
    data = parsed["guardian"]
    digest = hash_value(data["jshshir"])
    guardian = Guardian.all_objects.filter(school=school, jshshir_hash=digest).first()

    created = guardian is None
    if created:
        guardian = Guardian(school=school)
    guardian.first_name = data["first_name"]
    guardian.last_name = data["last_name"]
    guardian.middle_name = data["middle_name"]
    guardian.phone = data["phone"]
    guardian.is_active = True
    guardian.deleted_at = None
    guardian.set_jshshir(data["jshshir"])
    guardian.save()
    return guardian, created


def _upsert_link(guardian, student, parsed) -> bool:
    is_primary = parsed["is_primary"]
    if is_primary and GuardianStudent.objects.filter(
        student=student, is_primary=True
    ).exclude(guardian=guardian).exists():
        is_primary = False  # the uniqueness constraint allows only one

    _link, created = GuardianStudent.objects.get_or_create(
        guardian=guardian,
        student=student,
        defaults={"relation": parsed["relation"], "is_primary": is_primary},
    )
    return created
