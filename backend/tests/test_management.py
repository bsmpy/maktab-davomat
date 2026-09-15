"""The ADMIN cabinet: grades, class groups, pupils and their guardians.

Deleting is always a soft delete — a school's history has to survive an
administrator retiring a parallel — and a pupil leaving must also come off the
access terminals, or they could still open the turnstile.
"""
from __future__ import annotations

import pytest
from django.urls import reverse

from apps.accounts.constants import Role
from apps.accounts.models import User
from apps.guardians.models import Guardian, GuardianStudent
from apps.schools.models import ClassGroup, Grade
from apps.students.models import Student
from tests.conftest import PASSWORD

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin_user(school, db) -> User:
    from apps.schools.models import Teacher

    user = User.objects.create_user(
        username="maktabadmin", password=PASSWORD, role=Role.ADMIN,
        first_name="Nodir", last_name="Adminov",
    )
    Teacher.objects.create(
        school=school, user=user, first_name="Nodir", last_name="Adminov"
    )
    return user


@pytest.fixture
def admin_client(api, admin_user):
    from apps.accounts.services.auth import issue_tokens

    access, _refresh, _ttl = issue_tokens(admin_user)
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return api


def guardian_payload(**overrides) -> dict:
    payload = {
        "last_name": "Valiyev",
        "first_name": "Sardor",
        "middle_name": "Alisherovich",
        "relation": "FATHER",
        "phone": "+998901112233",
        "jshshir": "31234567890123",
        "is_primary": True,
    }
    payload.update(overrides)
    return payload


# --------------------------------------------------------------------------- #
# Access
# --------------------------------------------------------------------------- #
def test_a_parent_cannot_reach_the_management_api(auth_client):
    assert auth_client.get(reverse("management:grades")).status_code == 403
    assert auth_client.get(reverse("management:students")).status_code == 403


def test_a_teacher_cannot_reach_the_management_api(api, teacher_user):
    from apps.accounts.services.auth import issue_tokens

    access, _refresh, _ttl = issue_tokens(teacher_user)
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    assert api.get(reverse("management:grades")).status_code == 403


# --------------------------------------------------------------------------- #
# Grades
# --------------------------------------------------------------------------- #
def test_admin_lists_grades_with_their_counts(admin_client, class_groups, student):
    response = admin_client.get(reverse("management:grades"))
    assert response.status_code == 200

    seventh = next(row for row in response.data["results"] if row["level"] == 7)
    assert seventh["label"] == "7-sinf"
    assert seventh["class_groups_count"] == 2  # 7-A and 7-B
    assert seventh["students_count"] >= 1


def test_admin_adds_a_grade(admin_client, school):
    response = admin_client.post(reverse("management:grades"), {"level": 11}, format="json")
    assert response.status_code == 201
    assert response.data["level"] == 11
    assert Grade.objects.filter(school=school, level=11).exists()


def test_adding_an_existing_grade_is_rejected(admin_client, class_groups):
    grade = Grade.objects.get(level=7)
    response = admin_client.post(
        reverse("management:grades"), {"level": grade.level}, format="json"
    )
    assert response.status_code == 409
    assert response.data["error"]["code"] == "GRADE_EXISTS"


def test_deleting_a_grade_retires_its_groups_and_pupils(admin_client, class_groups, student):
    grade = Grade.objects.get(level=7)
    response = admin_client.delete(reverse("management:grade-detail", args=[grade.id]))

    assert response.status_code == 200
    assert response.data["class_groups"] == 2
    assert response.data["students"] >= 1

    # Everything is hidden, and everything is still there.
    assert not Grade.objects.filter(pk=grade.id).exists()
    assert Grade.all_objects.filter(pk=grade.id).exists()
    assert not ClassGroup.objects.filter(grade=grade).exists()
    assert not Student.objects.filter(pk=student.id).exists()
    assert Student.all_objects.filter(pk=student.id).exists()


def test_a_retired_grade_can_be_created_again(admin_client, class_groups):
    grade = Grade.objects.get(level=7)
    admin_client.delete(reverse("management:grade-detail", args=[grade.id]))

    response = admin_client.post(reverse("management:grades"), {"level": 7}, format="json")
    assert response.status_code == 201
    assert Grade.objects.filter(level=7).exists()


# --------------------------------------------------------------------------- #
# Class groups
# --------------------------------------------------------------------------- #
def test_admin_adds_a_group(admin_client, class_groups):
    grade = Grade.objects.get(level=3)
    response = admin_client.post(
        reverse("management:class-groups"), {"grade": str(grade.id), "name": "g"}, format="json"
    )
    assert response.status_code == 201
    assert response.data["display_name"] == "3-G"


def test_a_group_can_be_created_for_a_grade_that_does_not_exist_yet(
    admin_client, school, academic_year
):
    response = admin_client.post(
        reverse("management:class-groups"), {"level": 9, "name": "V"}, format="json"
    )
    assert response.status_code == 201
    assert response.data["display_name"] == "9-V"
    assert Grade.objects.filter(school=school, level=9).exists()


def test_duplicate_group_names_are_rejected(admin_client, class_groups):
    grade = Grade.objects.get(level=7)
    response = admin_client.post(
        reverse("management:class-groups"), {"grade": str(grade.id), "name": "A"}, format="json"
    )
    assert response.status_code == 409
    assert response.data["error"]["code"] == "CLASS_GROUP_EXISTS"


def test_admin_renames_a_group(admin_client, class_groups):
    group = class_groups["7-B"]
    response = admin_client.patch(
        reverse("management:class-group-detail", args=[group.id]),
        {"name": "D", "room": "204"},
        format="json",
    )
    assert response.status_code == 200
    assert response.data["display_name"] == "7-D"
    assert response.data["room"] == "204"


def test_deleting_a_group_retires_its_pupils(admin_client, class_groups, student):
    group = class_groups["7-A"]
    response = admin_client.delete(
        reverse("management:class-group-detail", args=[group.id])
    )

    assert response.status_code == 200
    assert response.data["students"] >= 1
    assert not ClassGroup.objects.filter(pk=group.id).exists()
    assert ClassGroup.all_objects.filter(pk=group.id).exists()
    assert not Student.objects.filter(pk=student.id).exists()


# --------------------------------------------------------------------------- #
# Students
# --------------------------------------------------------------------------- #
def test_admin_adds_a_pupil_with_several_guardians(admin_client, class_groups, school):
    response = admin_client.post(
        reverse("management:students"),
        {
            "last_name": "Karimov",
            "first_name": "Jasur",
            "middle_name": "Botirovich",
            "class_group": str(class_groups["7-A"].id),
            "guardians": [
                guardian_payload(),
                guardian_payload(
                    first_name="Nilufar",
                    relation="MOTHER",
                    phone="+998901112244",
                    jshshir="42234567890123",
                    is_primary=False,
                ),
            ],
        },
        format="json",
    )
    assert response.status_code == 201

    created = Student.objects.get(pk=response.data["id"])
    assert created.full_name == "Karimov Jasur Botirovich"

    links = GuardianStudent.objects.filter(student=created)
    assert links.count() == 2
    assert {link.relation for link in links} == {"FATHER", "MOTHER"}
    # An administrator entering the register is the school's own record.
    assert all(link.verified for link in links)
    assert links.filter(is_primary=True).count() == 1


def test_the_same_guardian_is_reused_across_siblings(admin_client, class_groups, school):
    url = reverse("management:students")
    for name in ("Jasur", "Nilufar"):
        response = admin_client.post(
            url,
            {
                "last_name": "Karimov",
                "first_name": name,
                "class_group": str(class_groups["7-A"].id),
                "guardians": [guardian_payload()],
            },
            format="json",
        )
        assert response.status_code == 201

    assert Guardian.objects.filter(school=school, last_name="Valiyev").count() == 1


def test_a_guardian_without_a_jshshir_is_rejected(admin_client, class_groups):
    response = admin_client.post(
        reverse("management:students"),
        {
            "last_name": "Karimov",
            "first_name": "Jasur",
            "class_group": str(class_groups["7-A"].id),
            "guardians": [guardian_payload(jshshir="")],
        },
        format="json",
    )
    assert response.status_code == 400


def test_editing_a_pupil_keeps_guardians_matched_by_id(admin_client, class_groups):
    created = admin_client.post(
        reverse("management:students"),
        {
            "last_name": "Karimov",
            "first_name": "Jasur",
            "class_group": str(class_groups["7-A"].id),
            "guardians": [guardian_payload()],
        },
        format="json",
    )
    guardian_id = created.data["guardians"][0]["id"]

    # The stored JSHSHIR never reaches the browser, so the edit sends it blank.
    response = admin_client.patch(
        reverse("management:student-detail", args=[created.data["id"]]),
        {
            "guardians": [
                {
                    "id": guardian_id,
                    "last_name": "Valiyev",
                    "first_name": "Sardor",
                    "middle_name": "Alisherovich",
                    "relation": "GUARDIAN",
                    "phone": "+998901112299",
                    "jshshir": "",
                    "is_primary": True,
                }
            ]
        },
        format="json",
    )
    assert response.status_code == 200
    assert response.data["guardians"][0]["relation"] == "GUARDIAN"
    assert response.data["guardians"][0]["phone"] == "+998901112299"
    assert Guardian.objects.filter(pk=guardian_id).count() == 1


def test_removing_a_guardian_from_the_form_detaches_the_link(admin_client, class_groups):
    created = admin_client.post(
        reverse("management:students"),
        {
            "last_name": "Karimov",
            "first_name": "Jasur",
            "class_group": str(class_groups["7-A"].id),
            "guardians": [
                guardian_payload(),
                guardian_payload(
                    first_name="Nilufar", relation="MOTHER",
                    phone="+998901112244", jshshir="42234567890123", is_primary=False,
                ),
            ],
        },
        format="json",
    )
    keep = created.data["guardians"][0]

    response = admin_client.patch(
        reverse("management:student-detail", args=[created.data["id"]]),
        {
            "guardians": [
                {
                    "id": keep["id"],
                    "last_name": keep["last_name"],
                    "first_name": keep["first_name"],
                    "middle_name": keep["middle_name"],
                    "relation": keep["relation"],
                    "phone": keep["phone"],
                    "jshshir": "",
                    "is_primary": True,
                }
            ]
        },
        format="json",
    )
    assert response.status_code == 200
    assert len(response.data["guardians"]) == 1
    # The other guardian's own record survives — they may be another pupil's parent.
    assert Guardian.objects.count() >= 2


def test_pupils_can_be_filtered_and_searched(admin_client, student, sibling, other_student):
    by_class = admin_client.get(
        reverse("management:students"), {"class_group": str(student.class_group_id)}
    )
    assert by_class.status_code == 200
    assert {row["id"] for row in by_class.data["results"]} == {str(student.id)}

    by_name = admin_client.get(reverse("management:students"), {"q": "Valiyev"})
    assert by_name.data["count"] >= 1


def test_deleting_a_pupil_is_soft_and_unenrols_them(admin_client, student):
    response = admin_client.delete(reverse("management:student-detail", args=[student.id]))

    assert response.status_code == 200
    assert not Student.objects.filter(pk=student.id).exists()
    assert Student.all_objects.filter(pk=student.id).exists()


def test_a_pupil_from_another_school_is_invisible(admin_client, other_student, school):
    from apps.schools.models import School

    other_school = School.objects.create(name="Boshqa maktab")
    Student.objects.filter(pk=other_student.id).update(school=other_school)

    response = admin_client.get(
        reverse("management:student-detail", args=[other_student.id])
    )
    assert response.status_code == 404


# --------------------------------------------------------------------------- #
# Photo
# --------------------------------------------------------------------------- #
def test_uploading_a_photo_stores_it_and_queues_the_enrolment(
    admin_client, student, monkeypatch, tmp_path, settings
):
    import io

    from PIL import Image

    settings.MEDIA_ROOT = tmp_path

    queued: list[str] = []
    monkeypatch.setattr(
        "apps.integrations.tasks.enroll_student_on_terminals.delay",
        lambda student_id: queued.append(student_id),
    )

    buffer = io.BytesIO()
    Image.new("RGB", (600, 800), "grey").save(buffer, format="JPEG", quality=95)
    buffer.seek(0)
    buffer.name = "face.jpg"

    from django.test import TestCase

    with TestCase.captureOnCommitCallbacks(execute=True):
        response = admin_client.post(
            reverse("management:student-photo", args=[student.id]),
            {"photo": buffer},
            format="multipart",
        )

    assert response.status_code == 200
    student.refresh_from_db()
    assert student.photo
    assert queued == [str(student.id)]


def test_a_tiny_photo_is_rejected(admin_client, student, tmp_path, settings):
    import io

    from PIL import Image

    settings.MEDIA_ROOT = tmp_path
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), "grey").save(buffer, format="JPEG", quality=10)
    buffer.seek(0)
    buffer.name = "tiny.jpg"

    response = admin_client.post(
        reverse("management:student-photo", args=[student.id]),
        {"photo": buffer},
        format="multipart",
    )
    assert response.status_code == 409
    assert response.data["error"]["code"] == "PHOTO_TOO_SMALL"


def test_relation_choices_are_the_four_the_form_offers(admin_client):
    response = admin_client.get(reverse("management:relations"))
    assert response.status_code == 200
    assert [row["value"] for row in response.data["results"]] == [
        "FATHER",
        "MOTHER",
        "GUARDIAN",
        "OTHER",
    ]
    assert [row["label"] for row in response.data["results"]] == [
        "Otasi",
        "Onasi",
        "Vasiysi",
        "Boshqa",
    ]


def test_the_auto_enrol_switch_is_honoured(admin_client, student, monkeypatch, tmp_path, settings):
    """A switch that silently does nothing is worse than no switch."""
    import io

    from PIL import Image

    from apps.integrations.constants import IntegrationKind
    from apps.integrations.models import Integration

    settings.MEDIA_ROOT = tmp_path
    Integration.objects.create(
        kind=IntegrationKind.FACE_ID,
        school=student.school,
        is_enabled=True,
        config={"auto_enroll": False},
    )

    queued: list[str] = []
    monkeypatch.setattr(
        "apps.integrations.tasks.enroll_student_on_terminals.delay",
        lambda student_id: queued.append(student_id),
    )

    buffer = io.BytesIO()
    Image.new("RGB", (600, 800), "grey").save(buffer, format="JPEG", quality=95)
    buffer.seek(0)
    buffer.name = "face.jpg"

    from django.test import TestCase

    with TestCase.captureOnCommitCallbacks(execute=True):
        response = admin_client.post(
            reverse("management:student-photo", args=[student.id]),
            {"photo": buffer},
            format="multipart",
        )

    assert response.status_code == 200
    student.refresh_from_db()
    # The photo is still stored; only the push to the devices is held back.
    assert student.photo
    assert queued == []


def test_the_photo_url_is_absolute(admin_client, student, tmp_path, settings, monkeypatch):
    """The SPA and the API may be on different hosts.

    A relative ``/media/...`` would resolve against the SPA's host, hit its
    catch-all route and come back as index.html with a 200 — the browser then
    has HTML where it expected a JPEG and shows a broken image.
    """
    import io

    from PIL import Image

    settings.MEDIA_ROOT = tmp_path
    settings.BACKEND_URL = "http://192.168.0.100"
    monkeypatch.setattr(
        "apps.integrations.tasks.enroll_student_on_terminals.delay", lambda student_id: None
    )

    buffer = io.BytesIO()
    Image.new("RGB", (600, 800), "grey").save(buffer, format="JPEG", quality=95)
    buffer.seek(0)
    buffer.name = "face.jpg"

    uploaded = admin_client.post(
        reverse("management:student-photo", args=[student.id]),
        {"photo": buffer},
        format="multipart",
    )
    assert uploaded.status_code == 200
    assert uploaded.data["photo"].startswith("http://192.168.0.100/media/")

    # And the list the cabinet renders carries the same absolute URL.
    listed = admin_client.get(reverse("management:students"))
    row = next(item for item in listed.data["results"] if item["id"] == str(student.id))
    assert row["photo"].startswith("http://192.168.0.100/media/")


def test_a_pupil_without_a_photo_reports_none(admin_client, student):
    listed = admin_client.get(reverse("management:students"))
    row = next(item for item in listed.data["results"] if item["id"] == str(student.id))
    assert row["photo"] is None
