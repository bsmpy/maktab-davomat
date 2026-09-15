"""Excel import: validation, preview, duplicate handling."""
from __future__ import annotations

import io

import pytest
from openpyxl import Workbook

from apps.guardians.models import Guardian, GuardianStudent
from apps.schools.services.imports import ImportError_, import_workbook
from apps.students.models import Student

pytestmark = pytest.mark.django_db

HEADERS = [
    "student_first_name",
    "student_last_name",
    "student_middle_name",
    "grade",
    "class_group",
    "guardian_first_name",
    "guardian_last_name",
    "guardian_middle_name",
    "guardian_jshshir",
    "guardian_phone",
    "guardian_relation",
]


def workbook(rows, headers=None) -> io.BytesIO:
    book = Workbook()
    sheet = book.active
    sheet.append(headers or HEADERS)
    for row in rows:
        sheet.append(row)
    stream = io.BytesIO()
    book.save(stream)
    stream.seek(0)
    return stream


def row(**overrides):
    data = {
        "student_first_name": "Jasur",
        "student_last_name": "Tursunov",
        "student_middle_name": "Anvarovich",
        "grade": 7,
        "class_group": "A",
        "guardian_first_name": "Anvar",
        "guardian_last_name": "Tursunov",
        "guardian_middle_name": "Sobirovich",
        "guardian_jshshir": "32222333344445",
        "guardian_phone": "+998901112233",
        "guardian_relation": "FATHER",
    }
    data.update(overrides)
    return [data[key] for key in HEADERS]


def test_missing_columns_are_reported(school, academic_year):
    with pytest.raises(ImportError_, match="yetishmayapti"):
        import_workbook(workbook([], headers=["student_first_name"]), school=school, academic_year=academic_year)


def test_dry_run_changes_nothing(school, academic_year, class_groups):
    report = import_workbook(
        workbook([row()]), school=school, academic_year=academic_year, dry_run=True
    )
    assert report.ok
    assert report.students_created == 1
    assert report.guardians_created == 1
    assert report.links_created == 1
    assert report.preview[0]["class_group"] == "7-A"
    # Nothing was persisted.
    assert Student.objects.count() == 0
    assert Guardian.objects.count() == 0


def test_commit_creates_everything(school, academic_year, class_groups):
    report = import_workbook(
        workbook([row()]), school=school, academic_year=academic_year, dry_run=False
    )
    assert report.ok
    student = Student.objects.get()
    guardian = Guardian.objects.get()
    assert student.class_group.display_name == "7-A"
    assert guardian.phone == "+998901112233"
    assert guardian.masked_jshshir == "**********4445"
    assert GuardianStudent.objects.count() == 1
    # Imported links start unverified: registration is what confirms them.
    assert GuardianStudent.objects.get().verified is False


def test_rerunning_the_same_file_does_not_duplicate(school, academic_year, class_groups):
    for _ in range(2):
        import_workbook(
            workbook([row()]), school=school, academic_year=academic_year, dry_run=False
        )
    assert Student.objects.count() == 1
    assert Guardian.objects.count() == 1
    assert GuardianStudent.objects.count() == 1


def test_a_second_guardian_is_linked_to_the_same_child(school, academic_year, class_groups):
    rows = [
        row(),
        row(
            guardian_first_name="Nodira",
            guardian_last_name="Tursunova",
            guardian_jshshir="42222333344446",
            guardian_phone="+998901112244",
            guardian_relation="MOTHER",
        ),
    ]
    import_workbook(workbook(rows), school=school, academic_year=academic_year, dry_run=False)
    assert Student.objects.count() == 1
    assert Guardian.objects.count() == 2
    assert GuardianStudent.objects.count() == 2


@pytest.mark.parametrize(
    ("override", "column"),
    [
        ({"guardian_jshshir": "123"}, "guardian_jshshir"),
        ({"guardian_phone": "12345"}, "guardian_phone"),
        ({"guardian_relation": "UNCLE"}, "guardian_relation"),
        ({"class_group": "Z"}, "class_group"),
        ({"grade": "abc"}, "grade"),
        ({"student_first_name": ""}, "student_name"),
    ],
)
def test_invalid_rows_are_reported_with_their_column(
    school, academic_year, class_groups, override, column
):
    report = import_workbook(
        workbook([row(**override)]), school=school, academic_year=academic_year, dry_run=True
    )
    assert not report.ok
    assert any(error.column == column for error in report.errors), report.errors
    assert report.errors[0].row == 2


def test_duplicate_rows_inside_the_file_are_flagged(school, academic_year, class_groups):
    report = import_workbook(
        workbook([row(), row()]), school=school, academic_year=academic_year, dry_run=True
    )
    assert any(error.column == "duplicate" for error in report.errors)


def test_commit_is_refused_when_the_file_has_errors(school, academic_year, class_groups):
    report = import_workbook(
        workbook([row(), row(guardian_phone="nope")]),
        school=school,
        academic_year=academic_year,
        dry_run=False,
    )
    assert not report.ok
    assert Student.objects.count() == 0


def test_relation_aliases_are_accepted(school, academic_year, class_groups):
    report = import_workbook(
        workbook([row(guardian_relation="ota")]),
        school=school,
        academic_year=academic_year,
        dry_run=False,
    )
    assert report.ok
    assert GuardianStudent.objects.get().relation == "FATHER"


def test_local_phone_formats_are_normalised(school, academic_year, class_groups):
    import_workbook(
        workbook([row(guardian_phone="90 111 22 33")]),
        school=school,
        academic_year=academic_year,
        dry_run=False,
    )
    assert Guardian.objects.get().phone == "+998901112233"


# --------------------------------------------------------------------------- #
# Import API — the cabinet screen that replaced the Django admin one
# --------------------------------------------------------------------------- #
@pytest.fixture
def import_client(api, school, db):
    """A DEVELOPER, since the import writes the whole register."""
    from django.urls import reverse  # noqa: F401 - used by the tests below

    from apps.accounts.constants import Role
    from apps.accounts.models import User
    from apps.accounts.services.auth import issue_tokens

    user = User.objects.create_user(
        username="root.admin", password="Admin!Parol2026", role=Role.DEVELOPER,
        first_name="Root", last_name="Admin", is_staff=True, is_superuser=True,
    )
    access, _refresh, _ttl = issue_tokens(user)
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return api


def upload(rows=None, *, name="import.xlsx"):
    from django.core.files.uploadedfile import SimpleUploadedFile

    return SimpleUploadedFile(
        name,
        workbook(rows if rows is not None else [row()]).getvalue(),
        content_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
    )


def test_the_api_offers_a_blank_template(import_client):
    from django.urls import reverse

    response = import_client.get(reverse("management:import-template"))
    assert response.status_code == 200
    assert "spreadsheetml" in response["Content-Type"]
    assert response["Content-Disposition"].endswith('filename="namuna.xlsx"')


def test_a_preview_does_not_write(import_client, school, academic_year, class_groups):
    from django.urls import reverse

    response = import_client.post(
        reverse("management:import"),
        {"school": str(school.id), "academic_year": str(academic_year.id), "file": upload()},
        format="multipart",
    )
    assert response.status_code == 200
    assert response.data["dry_run"] is True
    assert response.data["ok"] is True
    assert response.data["students_created"] == 1
    # Previewed, not written.
    assert Student.objects.count() == 0


def test_commit_writes_and_is_audited(import_client, school, academic_year, class_groups):
    from django.urls import reverse

    from apps.audit.constants import AuditAction
    from apps.audit.models import AuditLog

    response = import_client.post(
        reverse("management:import"),
        {
            "school": str(school.id),
            "academic_year": str(academic_year.id),
            "file": upload(),
            "commit": "true",
        },
        format="multipart",
    )
    assert response.status_code == 200
    assert response.data["dry_run"] is False
    assert Student.objects.count() == 1
    assert AuditLog.objects.filter(action=AuditAction.IMPORT_STUDENTS).exists()


def test_a_non_xlsx_upload_is_rejected(import_client, school, academic_year):
    from django.core.files.uploadedfile import SimpleUploadedFile
    from django.urls import reverse

    response = import_client.post(
        reverse("management:import"),
        {
            "school": str(school.id),
            "academic_year": str(academic_year.id),
            "file": SimpleUploadedFile("students.csv", b"a,b,c", content_type="text/csv"),
        },
        format="multipart",
    )
    assert response.status_code == 409
    assert response.data["error"]["code"] == "INVALID_FILE"


def test_a_parent_cannot_import(auth_client, school, academic_year):
    from django.urls import reverse

    response = auth_client.post(
        reverse("management:import"),
        {"school": str(school.id), "file": upload()},
        format="multipart",
    )
    assert response.status_code == 403


def test_generated_template_round_trips(school, academic_year, class_groups):
    """The blank template we hand out must be accepted by the importer."""
    import io

    from apps.schools.services.template import build_template

    report = import_workbook(
        io.BytesIO(build_template()), school=school, academic_year=academic_year, dry_run=True
    )
    assert report.ok, report.errors
    assert report.total_rows == 1
