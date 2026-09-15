"""The admin console API that replaced the Django admin.

The built-in admin is switched off entirely, so everything it used to own — the
school profile, academic years, holidays, subjects, teachers and the audit
trail — has to be reachable here, behind the same role checks as the rest of
the cabinet.
"""
from __future__ import annotations

from datetime import timedelta

import pytest
from django.urls import reverse

from apps.accounts.constants import Role
from apps.accounts.models import User
from apps.accounts.services.auth import issue_tokens
from apps.schools.models import (
    AcademicYear,
    ClassGroup,
    Grade,
    Holiday,
    School,
    Subject,
    Teacher,
)
from tests.conftest import PASSWORD, TODAY

pytestmark = pytest.mark.django_db


def as_user(api, user):
    access, _refresh, _ttl = issue_tokens(user)
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return api


@pytest.fixture
def developer(db) -> User:
    return User.objects.create_user(
        username="bsm", password=PASSWORD, role=Role.DEVELOPER,
        first_name="Developer", last_name="BSM", is_staff=True, is_superuser=True,
    )


@pytest.fixture
def school_admin(school, db) -> User:
    user = User.objects.create_user(
        username="maktabadmin", password=PASSWORD, role=Role.ADMIN,
        first_name="Nodir", last_name="Adminov",
    )
    Teacher.objects.create(school=school, user=user, first_name="Nodir", last_name="Adminov")
    return user


@pytest.fixture
def dev_client(api, developer):
    return as_user(api, developer)


# --------------------------------------------------------------------------- #
# The Django admin is gone
# --------------------------------------------------------------------------- #
def test_the_django_admin_is_not_installed(client):
    """No second login surface: the built-in admin does not exist at all."""
    from django.conf import settings

    assert "django.contrib.admin" not in settings.INSTALLED_APPS
    assert client.get("/admin/").status_code == 404
    assert client.get("/admin/login/").status_code == 404


def test_the_session_login_form_is_gone(client):
    assert client.get("/admin/students/student/import/").status_code == 404


# --------------------------------------------------------------------------- #
# School profile
# --------------------------------------------------------------------------- #
def test_an_admin_reads_and_edits_their_school(api, school_admin, school, student):
    client = as_user(api, school_admin)
    listed = client.get(reverse("management:schools"))
    assert listed.status_code == 200
    assert listed.data["results"][0]["name"] == school.name
    assert listed.data["results"][0]["students_count"] == 1

    response = client.patch(
        reverse("management:school-detail", args=[school.id]),
        {"short_name": "Yangi", "working_weekdays": [1, 2, 3, 4, 5]},
        format="json",
    )
    assert response.status_code == 200
    school.refresh_from_db()
    assert school.short_name == "Yangi"
    assert school.working_weekdays == [1, 2, 3, 4, 5]


def test_only_a_developer_may_add_a_school(school_admin, developer):
    from rest_framework.test import APIClient

    payload = {"name": "Ikkinchi maktab"}

    refused = as_user(APIClient(), school_admin).post(
        reverse("management:schools"), payload, format="json"
    )
    assert refused.status_code == 409
    assert refused.data["error"]["code"] == "DEVELOPER_ONLY"

    allowed = as_user(APIClient(), developer).post(
        reverse("management:schools"), payload, format="json"
    )
    assert allowed.status_code == 201
    assert School.objects.filter(name="Ikkinchi maktab").exists()


def test_a_parent_reaches_none_of_it(auth_client):
    for name in ("schools", "academic-years", "holidays", "subjects", "teachers"):
        assert auth_client.get(reverse(f"management:{name}")).status_code == 403


# --------------------------------------------------------------------------- #
# Academic years
# --------------------------------------------------------------------------- #
def test_creating_an_academic_year(dev_client, school):
    response = dev_client.post(
        reverse("management:academic-years"),
        {
            "name": "2027-2028",
            "start_date": "2027-09-01",
            "end_date": "2028-05-31",
            "is_current": True,
        },
        format="json",
    )
    assert response.status_code == 201
    assert AcademicYear.objects.get(name="2027-2028").is_current is True


def test_only_one_year_is_current_at_a_time(dev_client, school, academic_year):
    assert academic_year.is_current is True
    dev_client.post(
        reverse("management:academic-years"),
        {
            "name": "2027-2028",
            "start_date": "2027-09-01",
            "end_date": "2028-05-31",
            "is_current": True,
        },
        format="json",
    )
    academic_year.refresh_from_db()
    assert academic_year.is_current is False
    assert AcademicYear.objects.filter(is_current=True).count() == 1


def test_a_year_that_ends_before_it_starts_is_rejected(dev_client, school):
    response = dev_client.post(
        reverse("management:academic-years"),
        {"name": "Broken", "start_date": "2027-09-01", "end_date": "2027-01-01"},
        format="json",
    )
    assert response.status_code == 400


def test_a_year_with_groups_cannot_be_deleted(dev_client, academic_year, class_groups):
    response = dev_client.delete(
        reverse("management:academic-year-detail", args=[academic_year.id])
    )
    assert response.status_code == 409
    assert response.data["error"]["code"] == "YEAR_IN_USE"
    assert AcademicYear.objects.filter(pk=academic_year.id).exists()


# --------------------------------------------------------------------------- #
# Holidays
# --------------------------------------------------------------------------- #
def test_adding_a_holiday(dev_client, school, academic_year):
    response = dev_client.post(
        reverse("management:holidays"),
        {"date": TODAY.isoformat(), "name": "Mustaqillik kuni"},
        format="json",
    )
    assert response.status_code == 201
    assert Holiday.objects.get(date=TODAY).name == "Mustaqillik kuni"


def test_a_holiday_takes_the_day_out_of_the_denominator(
    dev_client, school, academic_year, student, present_day
):
    """The point of the screen: a closed day must not count as an absence."""
    from apps.attendance.services import build_daily_presence

    before = build_daily_presence(student, TODAY)
    assert before["is_school_day"] is True

    dev_client.post(
        reverse("management:holidays"),
        {"date": TODAY.isoformat(), "name": "Bayram"},
        format="json",
    )

    after = build_daily_presence(student, TODAY)
    assert after["state"] == "HOLIDAY"
    assert after["summary"]["school_days"] == 0


def test_two_holidays_on_one_date_are_rejected(dev_client, school, academic_year):
    payload = {"date": TODAY.isoformat(), "name": "Bayram"}
    assert dev_client.post(reverse("management:holidays"), payload, format="json").status_code == 201
    duplicate = dev_client.post(reverse("management:holidays"), payload, format="json")
    assert duplicate.status_code == 409


def test_a_holiday_can_be_removed(dev_client, school, academic_year):
    created = dev_client.post(
        reverse("management:holidays"),
        {"date": (TODAY + timedelta(days=1)).isoformat(), "name": "Bayram"},
        format="json",
    )
    response = dev_client.delete(
        reverse("management:holiday-detail", args=[created.data["id"]])
    )
    assert response.status_code == 200
    assert Holiday.objects.count() == 0


# --------------------------------------------------------------------------- #
# Subjects and teachers
# --------------------------------------------------------------------------- #
def test_subject_crud(dev_client, school):
    created = dev_client.post(
        reverse("management:subjects"),
        {"name": "Matematika", "short_name": "Mat", "color": "#1C3A6E"},
        format="json",
    )
    assert created.status_code == 201

    renamed = dev_client.patch(
        reverse("management:subject-detail", args=[created.data["id"]]),
        {"short_name": "Matem"},
        format="json",
    )
    assert renamed.data["short_name"] == "Matem"

    dev_client.delete(reverse("management:subject-detail", args=[created.data["id"]]))
    # Soft deleted: gone from the list, still in the table.
    assert Subject.objects.count() == 0
    assert Subject.all_objects.count() == 1


def test_a_subject_belongs_to_one_class_group(dev_client, school, class_groups):
    """Sinf → sinf guruhi → fan nomi, shown as ``Matematika 1-A``."""
    group = class_groups["1-A"]
    created = dev_client.post(
        reverse("management:subjects"),
        {"name": "Matematika", "class_group": str(group.id)},
        format="json",
    )
    assert created.status_code == 201, created.data
    assert created.data["display_name"] == "Matematika 1-A"
    assert created.data["class_group_name"] == "1-A"
    assert created.data["grade_level"] == 1

    # The same name in another group is a different subject, not a clash.
    sibling = dev_client.post(
        reverse("management:subjects"),
        {"name": "Matematika", "class_group": str(class_groups["1-B"].id)},
        format="json",
    )
    assert sibling.status_code == 201
    assert sibling.data["display_name"] == "Matematika 1-B"

    # Twice in the same group is still a clash.
    again = dev_client.post(
        reverse("management:subjects"),
        {"name": "matematika", "class_group": str(group.id)},
        format="json",
    )
    assert again.status_code == 409
    assert again.data["error"]["code"] == "SUBJECT_EXISTS"


def test_the_subject_list_can_be_narrowed_to_one_class_group(
    dev_client, school, class_groups
):
    for name, group in (("Matematika", "1-A"), ("Fizika", "1-A"), ("Matematika", "7-A")):
        dev_client.post(
            reverse("management:subjects"),
            {"name": name, "class_group": str(class_groups[group].id)},
            format="json",
        )

    response = dev_client.get(
        reverse("management:subjects"), {"class_group": str(class_groups["1-A"].id)}
    )
    assert sorted(row["display_name"] for row in response.data["results"]) == [
        "Fizika 1-A",
        "Matematika 1-A",
    ]


def test_a_class_group_from_another_school_is_refused(dev_client, school):
    other = School.objects.create(name="Boshqa maktab")
    stranger = ClassGroup.objects.create(
        school=other,
        academic_year=AcademicYear.objects.create(
            school=other,
            name="2026-2027",
            start_date=TODAY,
            end_date=TODAY + timedelta(days=200),
        ),
        grade=Grade.objects.create(school=other, level=5),
        name="A",
    )
    # The write targets one school; a group from the other one is not in it.
    response = dev_client.post(
        reverse("management:subjects"),
        {
            "name": "Matematika",
            "school": str(school.id),
            "class_group": str(stranger.id),
        },
        format="json",
    )
    assert response.status_code == 404
    assert response.data["error"]["code"] == "CLASS_GROUP_NOT_FOUND"


def test_the_teacher_row_names_subjects_with_their_class_group(
    dev_client, school, class_groups
):
    subject_id = dev_client.post(
        reverse("management:subjects"),
        {"name": "Matematika", "class_group": str(class_groups["1-A"].id)},
        format="json",
    ).data["id"]
    teacher = dev_client.post(
        reverse("management:teachers"),
        {"first_name": "Sardor", "last_name": "Yusupov", "subjects": [subject_id]},
        format="json",
    )
    assert [row["display_name"] for row in teacher.data["subjects"]] == ["Matematika 1-A"]


def test_a_deleted_subject_name_can_be_used_again(dev_client, school):
    """Soft delete must not reserve the name forever."""
    created = dev_client.post(
        reverse("management:subjects"), {"name": "Matematika 4"}, format="json"
    )
    dev_client.delete(reverse("management:subject-detail", args=[created.data["id"]]))

    again = dev_client.post(
        reverse("management:subjects"), {"name": "Matematika 4"}, format="json"
    )
    assert again.status_code == 201
    assert again.data["id"] != created.data["id"]


def test_a_duplicate_subject_is_rejected(dev_client, school, subject):
    response = dev_client.post(
        reverse("management:subjects"), {"name": subject.name}, format="json"
    )
    assert response.status_code == 409
    assert response.data["error"]["code"] == "SUBJECT_EXISTS"


def test_teacher_crud_with_subjects(dev_client, school, subject):
    created = dev_client.post(
        reverse("management:teachers"),
        {
            "last_name": "Yusupov",
            "first_name": "Sardor",
            "phone": "+998901234567",
            "subjects": [str(subject.id)],
        },
        format="json",
    )
    assert created.status_code == 201
    assert created.data["full_name"] == "Yusupov Sardor"
    assert [row["name"] for row in created.data["subjects"]] == [subject.name]
    assert Teacher.objects.get(pk=created.data["id"]).phone == "+998901234567"

    dev_client.delete(reverse("management:teacher-detail", args=[created.data["id"]]))
    assert Teacher.objects.count() == 0
    assert Teacher.all_objects.count() == 1


def test_a_bad_phone_is_rejected(dev_client, school):
    response = dev_client.post(
        reverse("management:teachers"),
        {"last_name": "Yusupov", "first_name": "Sardor", "phone": "12345"},
        format="json",
    )
    assert response.status_code == 400


def test_a_teacher_keeps_their_full_identity(dev_client, school):
    """Every field the form collects survives the round trip."""
    created = dev_client.post(
        reverse("management:teachers"),
        {
            "first_name": "Sardor",
            "last_name": "Yusupov",
            "middle_name": "Alisher o'g'li",
            "passport_id": "aa 123 45 67",
            "jshshir": "31234567890123",
            "birth_date": "1988-04-12",
            "gender": "MALE",
            "phone": "+998(90)123-45-67",
            "email": "sardor@maktab.uz",
        },
        format="json",
    )
    assert created.status_code == 201, created.data
    # Both identifiers are normalised on the way in.
    assert created.data["passport_id"] == "AA1234567"
    assert created.data["phone"] == "+998901234567"
    assert created.data["birth_date"] == "1988-04-12"
    assert created.data["gender_label"] == "Erkak"
    assert created.data["email"] == "sardor@maktab.uz"

    teacher = Teacher.objects.get(pk=created.data["id"])
    assert teacher.jshshir_last4 == "0123"
    # The console shows the number in full to the people who administer it.
    assert created.data["jshshir"] == "31234567890123"
    assert created.data["masked_jshshir"] == "**********0123"
    assert created.data["has_jshshir"] is True


@pytest.mark.parametrize(
    "passport",
    ["A1234567", "AAA123456", "AA123456", "AA12345678", "1A234567", "aa123456x"],
)
def test_a_bad_passport_id_is_rejected(dev_client, school, passport):
    response = dev_client.post(
        reverse("management:teachers"),
        {"first_name": "Sardor", "last_name": "Yusupov", "passport_id": passport},
        format="json",
    )
    assert response.status_code == 400
    assert "passport_id" in response.data["error"]["fields"]


def test_a_short_jshshir_is_rejected(dev_client, school):
    response = dev_client.post(
        reverse("management:teachers"),
        {"first_name": "Sardor", "last_name": "Yusupov", "jshshir": "3123456789"},
        format="json",
    )
    assert response.status_code == 400
    assert "jshshir" in response.data["error"]["fields"]


def test_the_identifiers_are_optional(dev_client, school):
    """A teacher whose documents were never collected is still a valid row."""
    response = dev_client.post(
        reverse("management:teachers"),
        {"first_name": "Sardor", "last_name": "Yusupov"},
        format="json",
    )
    assert response.status_code == 201
    assert response.data["passport_id"] == ""
    assert response.data["has_jshshir"] is False
    assert response.data["masked_jshshir"] == ""


def test_two_teachers_cannot_share_a_document(dev_client, school):
    payload = {
        "first_name": "Sardor",
        "last_name": "Yusupov",
        "passport_id": "AA1234567",
        "jshshir": "31234567890123",
    }
    first = dev_client.post(reverse("management:teachers"), payload, format="json")
    assert first.status_code == 201

    same_passport = dev_client.post(
        reverse("management:teachers"),
        {"first_name": "Bobur", "last_name": "Aliyev", "passport_id": "AA1234567"},
        format="json",
    )
    assert same_passport.status_code == 409
    assert same_passport.data["error"]["code"] == "TEACHER_PASSPORT_EXISTS"

    same_jshshir = dev_client.post(
        reverse("management:teachers"),
        {"first_name": "Bobur", "last_name": "Aliyev", "jshshir": "31234567890123"},
        format="json",
    )
    assert same_jshshir.status_code == 409
    assert same_jshshir.data["error"]["code"] == "TEACHER_JSHSHIR_EXISTS"

    # Editing a teacher must not collide with their own document.
    kept = dev_client.patch(
        reverse("management:teacher-detail", args=[first.data["id"]]),
        {"passport_id": "AA1234567", "first_name": "Sardorbek"},
        format="json",
    )
    assert kept.status_code == 200


def test_editing_a_teacher_replaces_their_jshshir(dev_client, school):
    created = dev_client.post(
        reverse("management:teachers"),
        {"first_name": "Sardor", "last_name": "Yusupov", "jshshir": "31234567890123"},
        format="json",
    )
    updated = dev_client.patch(
        reverse("management:teacher-detail", args=[created.data["id"]]),
        {"jshshir": "31234567899999", "phone": "+998(93)111-22-33"},
        format="json",
    )
    assert updated.status_code == 200
    assert updated.data["masked_jshshir"] == "**********9999"
    assert updated.data["phone"] == "+998931112233"


def test_several_subjects_are_attached_in_one_call(dev_client, school):
    """One teacher carries the same subject across every year."""
    years = [
        dev_client.post(
            reverse("management:subjects"), {"name": f"Matematika {level}"}, format="json"
        ).data["id"]
        for level in range(1, 5)
    ]
    teacher = dev_client.post(
        reverse("management:teachers"),
        {"first_name": "Sardor", "last_name": "Yusupov"},
        format="json",
    )
    assert teacher.data["subjects"] == []

    attached = dev_client.patch(
        reverse("management:teacher-detail", args=[teacher.data["id"]]),
        {"subjects": years},
        format="json",
    )
    assert attached.status_code == 200
    assert [row["name"] for row in attached.data["subjects"]] == [
        "Matematika 1",
        "Matematika 2",
        "Matematika 3",
        "Matematika 4",
    ]

    # Sending a shorter list detaches the rest rather than merging.
    detached = dev_client.patch(
        reverse("management:teacher-detail", args=[teacher.data["id"]]),
        {"subjects": years[:1]},
        format="json",
    )
    assert [row["name"] for row in detached.data["subjects"]] == ["Matematika 1"]

    # Names and documents are untouched by a subjects-only edit.
    assert detached.data["full_name"] == "Yusupov Sardor"


def test_a_teacher_gets_the_login_and_password_the_form_asked_for(dev_client, school):
    response = dev_client.post(
        reverse("management:teachers"),
        {
            "first_name": "Sardor",
            "last_name": "Yusupov",
            "phone": "+998(90)123-45-67",
            "username": "s.yusupov",
            "password": "Maktab2026!",
            "password_confirm": "Maktab2026!",
        },
        format="json",
    )
    assert response.status_code == 201, response.data
    assert response.data["username"] == "s.yusupov"

    account = User.objects.get(username="s.yusupov")
    assert account.role == Role.TEACHER
    assert account.check_password("Maktab2026!")
    # The operator and the teacher typed it together, so nothing is forced.
    assert account.must_change_password is False
    assert account.phone == "+998901234567"
    # The account is not echoed back and the teacher row points at it.
    assert "password" not in response.data
    assert Teacher.objects.get(pk=response.data["id"]).user_id == account.pk

    # And they can actually sign in with it.
    login = dev_client.post(
        reverse("auth:login"),
        {"login": "s.yusupov", "password": "Maktab2026!"},
        format="json",
    )
    assert login.status_code == 200


def test_the_credentials_are_optional(dev_client, school):
    """A teacher who does not need the cabinet is still a valid row."""
    response = dev_client.post(
        reverse("management:teachers"),
        {"first_name": "Sardor", "last_name": "Yusupov"},
        format="json",
    )
    assert response.status_code == 201
    assert response.data["username"] is None


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        ({"username": "s.yusupov", "password": "Maktab2026!", "password_confirm": "x"}, "password_confirm"),
        ({"username": "s.yusupov"}, "password"),
        ({"password": "Maktab2026!", "password_confirm": "Maktab2026!"}, "username"),
    ],
)
def test_incomplete_credentials_are_rejected(dev_client, school, payload, field):
    response = dev_client.post(
        reverse("management:teachers"),
        {"first_name": "Sardor", "last_name": "Yusupov", **payload},
        format="json",
    )
    assert response.status_code == 400
    assert field in response.data["error"]["fields"]
    assert not Teacher.objects.exists()


def test_a_taken_login_is_refused_and_leaves_no_teacher(dev_client, school, school_admin):
    response = dev_client.post(
        reverse("management:teachers"),
        {
            "first_name": "Sardor",
            "last_name": "Yusupov",
            "username": school_admin.username,
            "password": "Maktab2026!",
            "password_confirm": "Maktab2026!",
        },
        format="json",
    )
    assert response.status_code == 409
    assert response.data["error"]["code"] == "USERNAME_TAKEN"
    # The whole write rolled back: no half-created teacher is left behind.
    assert not Teacher.objects.filter(last_name="Yusupov").exists()


def test_a_weak_password_is_refused(dev_client, school):
    response = dev_client.post(
        reverse("management:teachers"),
        {
            "first_name": "Sardor",
            "last_name": "Yusupov",
            "username": "s.yusupov",
            "password": "12345678",
            "password_confirm": "12345678",
        },
        format="json",
    )
    assert response.status_code == 409
    assert response.data["error"]["code"] == "WEAK_PASSWORD"
    assert not User.objects.filter(username="s.yusupov").exists()


def test_the_teacher_row_shows_their_login(api, school_admin, school):
    client = as_user(api, school_admin)
    response = client.get(reverse("management:teachers"))
    row = next(item for item in response.data["results"] if item["last_name"] == "Adminov")
    assert row["username"] == "maktabadmin"


# --------------------------------------------------------------------------- #
# Audit trail
# --------------------------------------------------------------------------- #
def test_the_audit_trail_is_readable_by_the_top_roles(dev_client, school):
    dev_client.post(
        reverse("management:academic-years"),
        {"name": "2027-2028", "start_date": "2027-09-01", "end_date": "2028-05-31"},
        format="json",
    )
    response = dev_client.get(reverse("management:audit"))
    assert response.status_code == 200
    assert response.data["count"] >= 1
    assert response.data["results"][0]["username"] == "bsm"
    # The filter dropdown is served alongside the page.
    assert any(row["value"] == "LOGIN" for row in response.data["actions"])


def test_a_school_admin_cannot_read_the_audit_trail(api, school_admin):
    client = as_user(api, school_admin)
    assert client.get(reverse("management:audit")).status_code == 403


def test_the_audit_trail_can_be_filtered(dev_client, school):
    dev_client.post(reverse("management:schools"), {"name": "Uchinchi"}, format="json")

    matching = dev_client.get(
        reverse("management:audit"), {"action": "SCHOOL_STRUCTURE_CHANGE"}
    )
    assert matching.data["count"] >= 1

    empty = dev_client.get(reverse("management:audit"), {"action": "LOGIN_FAILED"})
    assert empty.data["count"] == 0


# --------------------------------------------------------------------------- #
# Bootstrapping an empty platform
# --------------------------------------------------------------------------- #
def test_an_empty_platform_says_what_to_do_first(dev_client, db):
    """No school at all is a setup step, not a missing record.

    A bare 404 here reads as "something is broken"; the operator needs to be
    told that creating the school is the first thing to do.
    """
    assert School.objects.count() == 0

    response = dev_client.post(reverse("management:grades"), {"level": 1}, format="json")
    assert response.status_code == 409
    assert response.data["error"]["code"] == "SCHOOL_MISSING"
    assert "Maktab" in response.data["error"]["message"]


def test_asking_for_someone_elses_school_is_still_a_flat_404(dev_client, school):
    import uuid

    response = dev_client.post(
        reverse("management:grades"),
        {"level": 1, "school": str(uuid.uuid4())},
        format="json",
    )
    assert response.status_code == 404
    assert response.data["error"]["code"] == "SCHOOL_NOT_FOUND"


def test_the_whole_register_can_be_built_from_nothing(dev_client, db):
    """School → academic year → grade → group, with no fixtures at all."""
    created_school = dev_client.post(
        reverse("management:schools"), {"name": "1-son maktab"}, format="json"
    )
    assert created_school.status_code == 201

    year = dev_client.post(
        reverse("management:academic-years"),
        {
            "name": "2026-2027",
            "start_date": "2026-09-01",
            "end_date": "2027-05-31",
            "is_current": True,
        },
        format="json",
    )
    assert year.status_code == 201

    grade = dev_client.post(reverse("management:grades"), {"level": 1}, format="json")
    assert grade.status_code == 201

    group = dev_client.post(
        reverse("management:class-groups"),
        {"grade": grade.data["id"], "name": "A"},
        format="json",
    )
    assert group.status_code == 201
    assert group.data["display_name"] == "1-A"


def test_a_grade_before_an_academic_year_explains_itself(dev_client, school):
    """The school exists but the year does not: the next step, not a 500."""
    grade = dev_client.post(reverse("management:grades"), {"level": 1}, format="json")
    assert grade.status_code == 201

    group = dev_client.post(
        reverse("management:class-groups"),
        {"grade": grade.data["id"], "name": "A"},
        format="json",
    )
    assert group.status_code == 409
    assert group.data["error"]["code"] == "ACADEMIC_YEAR_MISSING"


# --------------------------------------------------------------------------- #
# The administrator's home screen, and the register export
# --------------------------------------------------------------------------- #
def test_the_overview_counts_the_register_and_the_day(
    dev_client, school, class_groups, student, teaching_teacher, class_subject
):
    response = dev_client.get(reverse("management:overview"))
    assert response.status_code == 200
    assert response.data["school"] == school.name

    register = response.data["register"]
    assert register["students"] == 1
    assert register["teachers"] >= 1
    assert register["class_groups"] == len(class_groups)
    assert register["subjects"] >= 1

    # Nobody has walked through the gate, so the day is empty but not missing.
    assert response.data["today"] == {
        "total": 1,
        "arrived": 0,
        "absent": 1,
        "inside": 0,
        "late": 0,
        "rate": 0.0,
        "avg_active_minutes": 0,
        "avg_inactive_minutes": 0,
        "avg_late_minutes": 0,
    }
    # The teachers are counted the same way and answer the same questions, so
    # the home screen can lay both halves out as one.
    assert response.data["students_today"] == response.data["today"]
    assert response.data["teachers_today"]["total"] >= 1
    assert response.data["teachers_today"]["arrived"] == 0
    assert response.data["terminals"]["total"] == 0


def test_the_overview_follows_the_turnstile(dev_client, school, student, terminal):
    from apps.integrations.models import TerminalEvent
    from apps.integrations.services.presence import rebuild_daily_presence
    from tests.conftest import at, pass_through

    event = pass_through(terminal, "S1001", at(8, 0), serial=501)
    TerminalEvent.objects.filter(pk=event.pk).update(student=student)
    rebuild_daily_presence(student, TODAY)

    today = dev_client.get(reverse("management:overview")).data["today"]
    assert today["arrived"] == 1
    assert today["absent"] == 0
    assert today["rate"] == 100.0


def test_the_export_is_a_workbook_of_the_register(
    dev_client, school, student, teaching_teacher, guardian
):
    response = dev_client.get(reverse("management:export"))
    assert response.status_code == 200
    assert response["Content-Type"].startswith(
        "application/vnd.openxmlformats-officedocument"
    )
    assert "reyestr-" in response["Content-Disposition"]

    from io import BytesIO

    from openpyxl import load_workbook

    book = load_workbook(BytesIO(b"".join(response.streaming_content))
                         if response.streaming else BytesIO(response.content))
    assert book.sheetnames == ["O'quvchilar", "O'qituvchilar", "Yaqinlar"]

    pupils = book["O'quvchilar"]
    assert pupils.cell(row=1, column=1).value == "Familiya"
    assert pupils.cell(row=2, column=1).value == student.last_name
    assert pupils.cell(row=2, column=4).value == student.class_group.display_name


def test_the_export_is_written_to_the_audit_trail(dev_client, school, student):
    from apps.audit.constants import AuditAction
    from apps.audit.models import AuditLog

    dev_client.get(reverse("management:export"))
    assert AuditLog.objects.filter(action=AuditAction.EXPORT_REGISTER).exists()


def test_a_school_admin_does_not_get_the_schools_attendance_figures(api, school_admin):
    """The overview is today's attendance of the whole school — not an ADMIN's."""
    response = as_user(api, school_admin).get(reverse("management:overview"))
    assert response.status_code == 403


def test_a_parent_cannot_read_the_overview(api, parent_user):
    assert as_user(api, parent_user).get(reverse("management:overview")).status_code == 403
