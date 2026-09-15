"""Generates the blank Excel workbook schools fill in for the import."""
from __future__ import annotations

from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .imports import OPTIONAL_COLUMNS, REQUIRED_COLUMNS

EXAMPLE_ROW = {
    "student_first_name": "Azizbek",
    "student_last_name": "Valiyev",
    "student_middle_name": "Alisherovich",
    "student_code": "S1001",
    "student_birth_date": "2013-04-12",
    "student_gender": "MALE",
    "grade": 7,
    "class_group": "A",
    "guardian_first_name": "Alisher",
    "guardian_last_name": "Valiyev",
    "guardian_middle_name": "Anvarovich",
    "guardian_jshshir": "31234567890123",
    "guardian_phone": "+998901234567",
    "guardian_relation": "FATHER",
    "guardian_is_primary": "1",
}

COLUMNS = list(REQUIRED_COLUMNS) + list(OPTIONAL_COLUMNS)


def build_template() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Import"

    header_fill = PatternFill("solid", fgColor="1C3A6E")
    header_font = Font(color="FFFFFF", bold=True)

    sheet.append(COLUMNS)
    for index, column in enumerate(COLUMNS, start=1):
        cell = sheet.cell(row=1, column=index)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")
        sheet.column_dimensions[get_column_letter(index)].width = max(len(column) + 4, 16)

    sheet.append([EXAMPLE_ROW.get(column, "") for column in COLUMNS])
    sheet.freeze_panes = "A2"

    notes = workbook.create_sheet("Izoh")
    notes.column_dimensions["A"].width = 28
    notes.column_dimensions["B"].width = 80
    notes.append(["Ustun", "Tavsif"])
    notes["A1"].font = Font(bold=True)
    notes["B1"].font = Font(bold=True)
    for column, description in (
        ("student_first_name", "O'quvchining ismi (majburiy)"),
        ("student_last_name", "O'quvchining familiyasi (majburiy)"),
        ("student_middle_name", "Otasining ismi"),
        ("student_code", "Jurnal raqami. Bo'lsa — takrorlanishni aniqlashda ishlatiladi."),
        ("student_birth_date", "YYYY-MM-DD yoki DD.MM.YYYY"),
        ("student_gender", "MALE yoki FEMALE"),
        ("grade", "Sinf raqami: 1 dan 11 gacha (majburiy)"),
        ("class_group", "Guruh harfi: A, B, D … (majburiy)"),
        ("guardian_first_name", "Ota-onaning ismi (majburiy)"),
        ("guardian_last_name", "Ota-onaning familiyasi (majburiy)"),
        ("guardian_middle_name", "Ota-onaning otasining ismi"),
        ("guardian_jshshir", "14 ta raqam (majburiy). Shifrlangan holda saqlanadi."),
        ("guardian_phone", "+998XXXXXXXXX (majburiy). OTP shu raqamga yuboriladi."),
        ("guardian_relation", "FATHER / MOTHER / GUARDIAN / OTHER (majburiy)"),
        ("guardian_is_primary", "1 — asosiy vakil. Har bir o'quvchida bittadan."),
    ):
        notes.append([column, description])

    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
