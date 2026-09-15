"""Exporting the register as a workbook.

The import side already speaks .xlsx, so an administrator who can load the
register from a spreadsheet can take it back out the same way — for a backup,
for the ministry's forms, or to hand to somebody who does not have an account.

Nothing here invents data: every column is a field the register already holds.
"""
from __future__ import annotations

import io

from django.utils import timezone

#: Written into every sheet's first row.
STUDENT_COLUMNS = [
    "Familiya",
    "Ism",
    "Otasining ismi",
    "Sinf",
    "Tug'ilgan sana",
    "Jinsi",
    "O'quvchi kodi",
    "JSHSHIR",
    "Yaqinlari",
]

TEACHER_COLUMNS = [
    "Familiya",
    "Ism",
    "Otasining ismi",
    "Passport ID",
    "JSHSHIR",
    "Tug'ilgan sana",
    "Jinsi",
    "Telefon",
    "Email",
    "Login",
    "Fanlari",
]

GUARDIAN_COLUMNS = ["Familiya", "Ism", "Otasining ismi", "Telefon", "JSHSHIR", "Farzandlari"]


def _sheet(workbook, title: str, columns: list[str]):
    from openpyxl.styles import Font

    sheet = workbook.create_sheet(title=title)
    sheet.append(columns)
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    sheet.freeze_panes = "A2"
    return sheet


def _autosize(sheet) -> None:
    for column in sheet.columns:
        width = max((len(str(cell.value or "")) for cell in column), default=10)
        sheet.column_dimensions[column[0].column_letter].width = min(max(width + 2, 12), 42)


def build_register(school) -> bytes:
    """The whole register of one school: pupils, staff and guardians."""
    from openpyxl import Workbook

    from apps.guardians.models import Guardian
    from apps.students.models import Student

    from ..models import Teacher

    workbook = Workbook()
    workbook.remove(workbook.active)

    students = _sheet(workbook, "O'quvchilar", STUDENT_COLUMNS)
    for student in (
        Student.objects.active()
        .filter(school=school)
        .select_related("class_group", "class_group__grade")
        .prefetch_related("guardian_links__guardian")
        .order_by("class_group__grade__level", "class_group__name", "last_name")
    ):
        students.append(
            [
                student.last_name,
                student.first_name,
                student.middle_name,
                student.class_group.display_name,
                student.birth_date.isoformat() if student.birth_date else "",
                student.get_gender_display(),
                student.student_code,
                student.jshshir,
                ", ".join(
                    link.guardian.full_name for link in student.guardian_links.all()
                ),
            ]
        )
    _autosize(students)

    teachers = _sheet(workbook, "O'qituvchilar", TEACHER_COLUMNS)
    for teacher in (
        Teacher.objects.filter(school=school)
        .select_related("user")
        .prefetch_related("subjects__class_group__grade")
        .order_by("last_name", "first_name")
    ):
        teachers.append(
            [
                teacher.last_name,
                teacher.first_name,
                teacher.middle_name,
                teacher.passport_id,
                teacher.jshshir,
                teacher.birth_date.isoformat() if teacher.birth_date else "",
                teacher.get_gender_display(),
                teacher.phone,
                teacher.email,
                teacher.user.username if teacher.user_id else "",
                ", ".join(subject.display_name for subject in teacher.subjects.all()),
            ]
        )
    _autosize(teachers)

    guardians = _sheet(workbook, "Yaqinlar", GUARDIAN_COLUMNS)
    for guardian in (
        Guardian.objects.filter(school=school)
        .prefetch_related("student_links__student")
        .order_by("last_name", "first_name")
    ):
        guardians.append(
            [
                guardian.last_name,
                guardian.first_name,
                guardian.middle_name,
                guardian.phone,
                guardian.jshshir,
                ", ".join(link.student.full_name for link in guardian.student_links.all()),
            ]
        )
    _autosize(guardians)

    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def export_filename(school) -> str:
    stamp = timezone.localdate().isoformat()
    return f"reyestr-{stamp}.xlsx"
