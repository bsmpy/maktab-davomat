"""Lavozimlar and Xodimlar: the school's employees who are not teachers.

A staff member is entered on the same form as a teacher — the same name,
documents and contacts — with a position instead of subjects. A position is
nothing but its name, written once in each of the three interface languages.
"""
from __future__ import annotations

import pytest
from django.urls import reverse

from apps.accounts.constants import Role
from apps.accounts.models import User
from apps.accounts.services.auth import issue_tokens
from apps.schools.models import Position, StaffMember
from tests.conftest import PASSWORD

pytestmark = pytest.mark.django_db


def as_user(api, user):
    access, _refresh, _ttl = issue_tokens(user)
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return api


@pytest.fixture
def developer(db) -> User:
    return User.objects.create_user(
        username="bsm", password=PASSWORD, role=Role.DEVELOPER,
        first_name="Developer", last_name="BSM",
    )


@pytest.fixture
def dev_client(api, developer):
    return as_user(api, developer)


@pytest.fixture
def position(school) -> Position:
    return Position.objects.create(
        school=school, title_uz="Hisobchi", title_ru="Бухгалтер", title_en="Accountant"
    )


# --------------------------------------------------------------------------- #
# Positions
# --------------------------------------------------------------------------- #
def test_a_position_is_created_with_all_three_titles(dev_client, school):
    response = dev_client.post(
        reverse("management:positions"),
        {"title_uz": "Farrosh", "title_ru": "Уборщица", "title_en": "Cleaner"},
        format="json",
    )

    assert response.status_code == 201
    assert response.data["titles"] == {
        "uz": "Farrosh", "ru": "Уборщица", "en": "Cleaner",
    }


def test_only_the_uzbek_title_is_required(dev_client, school):
    """The other two can be filled in later; Uzbek is what they fall back to."""
    response = dev_client.post(
        reverse("management:positions"), {"title_uz": "Qorovul"}, format="json"
    )

    assert response.status_code == 201
    assert Position.objects.get(title_uz="Qorovul").title_for("ru") == "Qorovul"


def test_a_position_without_a_title_is_refused(dev_client, school):
    response = dev_client.post(
        reverse("management:positions"), {"title_ru": "Только по-русски"}, format="json"
    )
    assert response.status_code == 400


def test_the_same_position_cannot_be_added_twice(dev_client, school, position):
    response = dev_client.post(
        reverse("management:positions"), {"title_uz": "hisobchi"}, format="json"
    )

    assert response.status_code == 409
    assert response.data["error"]["code"] == "POSITION_EXISTS"


def test_a_position_lists_how_many_people_hold_it(dev_client, school, position):
    StaffMember.objects.create(
        school=school, position=position, first_name="Aziz", last_name="Karimov"
    )

    row = dev_client.get(reverse("management:positions")).data["results"][0]
    assert row["staff_count"] == 1


def test_a_position_in_use_is_not_deleted_out_from_under_its_people(
    dev_client, school, position
):
    StaffMember.objects.create(
        school=school, position=position, first_name="Aziz", last_name="Karimov"
    )

    response = dev_client.delete(
        reverse("management:position-detail", args=[position.id])
    )

    assert response.status_code == 409
    assert response.data["error"]["code"] == "POSITION_IN_USE"
    assert Position.objects.filter(pk=position.id).exists()


def test_an_unused_position_is_deleted(dev_client, school, position):
    response = dev_client.delete(
        reverse("management:position-detail", args=[position.id])
    )

    assert response.status_code == 200
    assert not Position.objects.filter(pk=position.id).exists()
    # Soft delete: the row is still there for the audit trail.
    assert Position.all_objects.filter(pk=position.id).exists()


def test_a_deleted_position_gives_its_name_back(dev_client, school, position):
    dev_client.delete(reverse("management:position-detail", args=[position.id]))

    again = dev_client.post(
        reverse("management:positions"), {"title_uz": "Hisobchi"}, format="json"
    )
    assert again.status_code == 201


def test_a_title_can_be_translated_after_the_fact(dev_client, school):
    created = dev_client.post(
        reverse("management:positions"), {"title_uz": "Qorovul"}, format="json"
    ).data

    response = dev_client.patch(
        reverse("management:position-detail", args=[created["id"]]),
        {"title_ru": "Охранник", "title_en": "Guard"},
        format="json",
    )

    assert response.status_code == 200
    assert response.data["titles"]["ru"] == "Охранник"
    assert response.data["titles"]["uz"] == "Qorovul"


# --------------------------------------------------------------------------- #
# Staff
# --------------------------------------------------------------------------- #
def test_a_staff_member_is_added_like_a_teacher_but_with_a_position(
    dev_client, school, position
):
    response = dev_client.post(
        reverse("management:staff"),
        {
            "first_name": "Aziz",
            "last_name": "Karimov",
            "middle_name": "Akmalovich",
            "passport_id": "AB1234567",
            "jshshir": "31234567890123",
            "birth_date": "1990-04-12",
            "gender": "MALE",
            "phone": "+998901234567",
            "position": str(position.id),
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.data["full_name"] == "Karimov Aziz"
    assert response.data["position"]["titles"]["ru"] == "Бухгалтер"
    # The JSHSHIR fans out the same way a teacher's does.
    assert response.data["has_jshshir"] is True
    assert StaffMember.objects.get(last_name="Karimov").jshshir == "31234567890123"


def test_a_staff_member_is_added_before_anyone_decides_what_to_call_them(
    dev_client, school
):
    """A name is enough. The label and the account come later, or never."""
    response = dev_client.post(
        reverse("management:staff"),
        {"first_name": "Aziz", "last_name": "Karimov"},
        format="json",
    )

    assert response.status_code == 201
    assert response.data["position"] is None
    assert response.data["role"] is None
    assert response.data["username"] is None


def test_a_position_is_attached_after_the_fact(dev_client, school, position):
    created = dev_client.post(
        reverse("management:staff"),
        {"first_name": "Aziz", "last_name": "Karimov"},
        format="json",
    ).data

    response = dev_client.patch(
        reverse("management:staff-detail", args=[created["id"]]),
        {"position": str(position.id)},
        format="json",
    )

    assert response.status_code == 200
    assert response.data["position"]["title_uz"] == "Hisobchi"


@pytest.mark.parametrize("empty", [None, ""])
def test_a_browser_form_may_say_no_position_either_way(dev_client, school, empty):
    """A `<select>` with nothing chosen sends "", not null."""
    response = dev_client.post(
        reverse("management:staff"),
        {"first_name": "Aziz", "last_name": "Karimov", "position": empty},
        format="json",
    )

    assert response.status_code == 201
    assert response.data["position"] is None


def test_a_position_that_is_not_a_uuid_is_named_as_the_problem(dev_client, school):
    response = dev_client.post(
        reverse("management:staff"),
        {"first_name": "Aziz", "last_name": "Karimov", "position": "not-a-uuid"},
        format="json",
    )

    assert response.status_code == 400
    assert "position" in response.data["error"]["fields"]


def test_a_position_is_taken_off_again_by_sending_it_empty(
    dev_client, school, position
):
    staff = StaffMember.objects.create(
        school=school, position=position, first_name="Aziz", last_name="Karimov"
    )

    response = dev_client.patch(
        reverse("management:staff-detail", args=[staff.id]),
        {"position": None},
        format="json",
    )

    assert response.status_code == 200
    assert response.data["position"] is None


def test_removing_a_position_leaves_its_people_standing(dev_client, school, position):
    """The label goes; the person stays, unlabelled."""
    staff = StaffMember.objects.create(
        school=school, position=position, first_name="Aziz", last_name="Karimov"
    )
    staff.position = None
    staff.save(update_fields=["position"])

    assert dev_client.delete(
        reverse("management:position-detail", args=[position.id])
    ).status_code == 200
    staff.refresh_from_db()
    assert StaffMember.objects.filter(pk=staff.id).exists()
    assert staff.position_id is None


# --------------------------------------------------------------------------- #
# Roles — optional, and never DEVELOPER
# --------------------------------------------------------------------------- #
def test_an_account_is_created_with_the_role_that_was_asked_for(dev_client, school):
    response = dev_client.post(
        reverse("management:staff"),
        {
            "first_name": "Aziz",
            "last_name": "Karimov",
            "username": "a.karimov",
            "password": PASSWORD,
            "password_confirm": PASSWORD,
            "role": Role.TEACHER,
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.data["role"] == Role.TEACHER
    assert response.data["username"] == "a.karimov"


def test_a_role_is_changed_after_the_account_exists(dev_client, school):
    created = dev_client.post(
        reverse("management:staff"),
        {
            "first_name": "Aziz",
            "last_name": "Karimov",
            "username": "a.karimov",
            "password": PASSWORD,
            "password_confirm": PASSWORD,
            "role": Role.TEACHER,
        },
        format="json",
    ).data

    response = dev_client.patch(
        reverse("management:staff-detail", args=[created["id"]]),
        {"role": Role.ADMIN},
        format="json",
    )

    assert response.status_code == 200
    assert response.data["role"] == Role.ADMIN
    assert User.objects.get(username="a.karimov").role == Role.ADMIN


def test_a_role_cannot_be_given_to_somebody_with_no_account(dev_client, school):
    staff = StaffMember.objects.create(
        school=school, first_name="Aziz", last_name="Karimov"
    )

    response = dev_client.patch(
        reverse("management:staff-detail", args=[staff.id]),
        {"role": Role.ADMIN},
        format="json",
    )

    assert response.status_code == 409
    assert response.data["error"]["code"] == "STAFF_HAS_NO_ACCOUNT"


def test_the_developer_role_is_not_handed_out_through_the_staff_register(
    dev_client, school
):
    """The platform owner's account is not a job at a school."""
    response = dev_client.post(
        reverse("management:staff"),
        {
            "first_name": "Aziz",
            "last_name": "Karimov",
            "username": "a.karimov",
            "password": PASSWORD,
            "password_confirm": PASSWORD,
            "role": Role.DEVELOPER,
        },
        format="json",
    )

    assert response.status_code == 409
    assert response.data["error"]["code"] == "STAFF_ROLE_FORBIDDEN"
    assert not User.objects.filter(username="a.karimov").exists()


def test_an_existing_account_cannot_be_promoted_to_developer_either(
    dev_client, school
):
    created = dev_client.post(
        reverse("management:staff"),
        {
            "first_name": "Aziz",
            "last_name": "Karimov",
            "username": "a.karimov",
            "password": PASSWORD,
            "password_confirm": PASSWORD,
            "role": Role.ADMIN,
        },
        format="json",
    ).data

    response = dev_client.patch(
        reverse("management:staff-detail", args=[created["id"]]),
        {"role": Role.DEVELOPER},
        format="json",
    )

    assert response.status_code == 409
    assert User.objects.get(username="a.karimov").role == Role.ADMIN


def test_the_register_never_offers_the_developer_role(dev_client, school):
    offered = dev_client.get(reverse("management:staff")).data["assignable_roles"]
    assert Role.DEVELOPER not in [row["value"] for row in offered]
    assert Role.ADMIN in [row["value"] for row in offered]


def test_a_super_admin_is_never_offered_the_developer_role(api, school):
    """Nobody becomes the platform owner by way of the staff register."""
    boss = User.objects.create_user(
        username="boss", password=PASSWORD, role=Role.SUPER_ADMIN
    )
    offered = as_user(api, boss).get(reverse("management:staff")).data["assignable_roles"]

    values = [row["value"] for row in offered]
    assert Role.DEVELOPER not in values
    assert Role.ADMIN in values
    assert Role.CURATOR in values
    assert Role.STAFF in values


def test_a_position_from_another_school_is_not_accepted(dev_client, school, position):
    from apps.schools.models import School

    other = School.objects.create(name="Boshqa maktab")
    theirs = Position.objects.create(school=other, title_uz="Hisobchi")

    # Name the school explicitly: a developer is unscoped, so with two schools
    # in the database "which school" is otherwise the test's own ambiguity
    # rather than the thing under test.
    response = dev_client.post(
        reverse("management:staff"),
        {
            "first_name": "Aziz",
            "last_name": "Karimov",
            "position": str(theirs.id),
            "school": str(school.id),
        },
        format="json",
    )

    assert response.status_code == 404
    assert response.data["error"]["code"] == "POSITION_NOT_FOUND"


def test_two_staff_members_cannot_share_a_passport(dev_client, school, position):
    payload = {
        "first_name": "Aziz",
        "last_name": "Karimov",
        "passport_id": "AB1234567",
        "position": str(position.id),
    }
    assert dev_client.post(reverse("management:staff"), payload, format="json").status_code == 201

    clash = dev_client.post(
        reverse("management:staff"), {**payload, "last_name": "Toshmatov"}, format="json"
    )
    assert clash.status_code == 409
    assert clash.data["error"]["code"] == "STAFF_PASSPORT_EXISTS"


def test_a_staff_member_may_hold_a_passport_a_teacher_also_holds(
    dev_client, school, position
):
    """Separate registers, separate uniqueness — they are not the same list."""
    from apps.schools.models import Teacher

    Teacher.objects.create(
        school=school, first_name="Saodaddin", last_name="Rasulov", passport_id="AB1234567"
    )

    response = dev_client.post(
        reverse("management:staff"),
        {
            "first_name": "Aziz",
            "last_name": "Karimov",
            "passport_id": "AB1234567",
            "position": str(position.id),
        },
        format="json",
    )
    assert response.status_code == 201


def test_a_staff_member_can_be_moved_to_another_position(dev_client, school, position):
    staff = StaffMember.objects.create(
        school=school, position=position, first_name="Aziz", last_name="Karimov"
    )
    guard = Position.objects.create(school=school, title_uz="Qorovul")

    response = dev_client.patch(
        reverse("management:staff-detail", args=[staff.id]),
        {"position": str(guard.id)},
        format="json",
    )

    assert response.status_code == 200
    assert response.data["position"]["title_uz"] == "Qorovul"


def test_deleting_a_staff_member_is_a_soft_delete(dev_client, school, position):
    staff = StaffMember.objects.create(
        school=school, position=position, first_name="Aziz", last_name="Karimov"
    )

    response = dev_client.delete(reverse("management:staff-detail", args=[staff.id]))

    assert response.status_code == 200
    assert not StaffMember.objects.filter(pk=staff.id).exists()
    assert StaffMember.all_objects.filter(pk=staff.id).exists()


def test_staff_are_searchable_by_name(dev_client, school, position):
    for last in ("Karimov", "Toshmatov"):
        StaffMember.objects.create(
            school=school, position=position, first_name="Aziz", last_name=last
        )

    found = dev_client.get(reverse("management:staff"), {"q": "tosh"}).data["results"]
    assert [row["last_name"] for row in found] == ["Toshmatov"]


# --------------------------------------------------------------------------- #
# Access
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("role", "expected"),
    [
        (Role.DEVELOPER, 200),
        (Role.SUPER_ADMIN, 200),
        (Role.ADMIN, 200),
        (Role.TEACHER, 403),
        (Role.PARENT, 403),
    ],
)
def test_who_may_read_the_staff_register(api, school, role, expected):
    user = User.objects.create_user(
        username=f"staff.{role.lower()}", password=PASSWORD, role=role
    )
    assert as_user(api, user).get(reverse("management:staff")).status_code == expected


def test_the_home_screen_counts_staff_and_positions(dev_client, school, position):
    StaffMember.objects.create(
        school=school, position=position, first_name="Aziz", last_name="Karimov"
    )

    register = dev_client.get(reverse("management:overview")).data["register"]

    assert register["staff"] == 1
    assert register["positions"] == 1
