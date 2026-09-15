"""Provisioning staff accounts, and who is allowed to provision whom.

The ladder is the whole point: a SUPER_ADMIN grows the layer below them, a
DEVELOPER grows any layer including its own. You may edit your own name, phone
and lower roles, but never switch yourself off, drop your highest role, reset
your own password or delete yourself.

Passwords are Argon2 hashes and are never readable by any role. The capability
that replaces "show me the password" is a one-off password that is displayed
once, forces a change at next login and is written to the audit trail — these
tests pin exactly that.
"""
from __future__ import annotations

import pytest
from django.urls import reverse

from apps.accounts import rbac
from apps.accounts.constants import Role, manageable_roles
from apps.accounts.models import User
from apps.accounts.services.auth import issue_tokens
from apps.audit.constants import AuditAction
from apps.audit.models import AuditLog
from tests.conftest import PASSWORD

pytestmark = pytest.mark.django_db


def as_user(api, user):
    access, _refresh, _ttl = issue_tokens(user)
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return api


@pytest.fixture
def developer(db) -> User:
    return User.objects.create_user(
        username="dev", password=PASSWORD, role=Role.DEVELOPER,
        first_name="Dev", last_name="Eloper", is_staff=True, is_superuser=True,
    )


@pytest.fixture
def super_admin(db) -> User:
    return User.objects.create_user(
        username="superadmin", password=PASSWORD, role=Role.SUPER_ADMIN,
        first_name="Super", last_name="Adminov",
    )


@pytest.fixture
def school_admin(school, db) -> User:
    from apps.schools.models import Teacher

    user = User.objects.create_user(
        username="maktabadmin", password=PASSWORD, role=Role.ADMIN,
        first_name="Nodir", last_name="Adminov",
    )
    Teacher.objects.create(school=school, user=user, first_name="Nodir", last_name="Adminov")
    return user


# --------------------------------------------------------------------------- #
# The ladder
# --------------------------------------------------------------------------- #
#: Everything a platform owner may hand out. OTA-ONA is absent everywhere — a
#: parent proves who they are and registers themselves.
PROVISIONABLE = {
    Role.DEVELOPER,
    Role.SUPER_ADMIN,
    Role.MODERATOR,
    Role.ADMIN,
    Role.TEACHER,
    Role.CURATOR,
    Role.STAFF,
}


def test_a_developer_may_create_every_role_including_its_own():
    assert set(manageable_roles(Role.DEVELOPER)) == PROVISIONABLE


def test_a_super_admin_may_grow_every_layer_but_the_platform_owner():
    """A school with one SUPER_ADMIN has to be able to grow a second.

    What a SUPER_ADMIN still cannot do is mint a DEVELOPER — that account is
    the platform's, not the school's, and it is invisible to them besides.
    """
    assert set(manageable_roles(Role.SUPER_ADMIN)) == PROVISIONABLE - {Role.DEVELOPER}


def test_everybody_else_provisions_nobody():
    for role in (Role.MODERATOR, Role.ADMIN, Role.TEACHER, Role.CURATOR, Role.STAFF, Role.PARENT):
        assert manageable_roles(role) == ()


# --------------------------------------------------------------------------- #
# Access
# --------------------------------------------------------------------------- #
def test_a_school_admin_cannot_open_the_user_list(api, school_admin):
    client = as_user(api, school_admin)
    assert client.get(reverse("management:users")).status_code == 403


def test_a_parent_cannot_open_the_user_list(auth_client):
    assert auth_client.get(reverse("management:users")).status_code == 403


def test_a_super_admin_has_the_same_school_management_as_an_admin(
    api, super_admin, class_groups, student
):
    """Everything an ADMIN can reach, a SUPER_ADMIN can reach too."""
    client = as_user(api, super_admin)
    assert client.get(reverse("management:grades")).status_code == 200
    assert client.get(reverse("management:class-groups")).status_code == 200
    assert client.get(reverse("management:students")).status_code == 200
    assert client.get(reverse("management:guardians")).status_code == 200


def test_a_super_admin_is_not_scoped_to_one_school(api, super_admin, student, school):
    from apps.schools.models import School

    other = School.objects.create(name="Ikkinchi maktab")
    from apps.students.models import Student

    Student.objects.filter(pk=student.id).update(school=other)

    client = as_user(api, super_admin)
    response = client.get(reverse("management:student-detail", args=[student.id]))
    assert response.status_code == 200


# --------------------------------------------------------------------------- #
# Creating accounts
# --------------------------------------------------------------------------- #
def test_a_super_admin_creates_an_admin(api, super_admin, school):
    client = as_user(api, super_admin)
    response = client.post(
        reverse("management:users"),
        {"last_name": "Karimov", "first_name": "Jasur", "role": "ADMIN"},
        format="json",
    )
    assert response.status_code == 201
    assert response.data["user"]["role"] == "ADMIN"
    assert response.data["user"]["username"] == "j.karimov"

    created = User.objects.get(username="j.karimov")
    assert created.role == Role.ADMIN
    # Scoped to a school, or they would see every register.
    assert created.teacher_profile.school == school


def test_a_super_admin_cannot_create_a_developer(api, super_admin):
    """The role is a valid value, so this is a refusal, not a bad request."""
    client = as_user(api, super_admin)
    response = client.post(
        reverse("management:users"),
        {"last_name": "Karimov", "first_name": "Jasur", "roles": ["DEVELOPER"]},
        format="json",
    )
    assert response.status_code == 403
    assert response.data["error"]["code"] == "FORBIDDEN"
    assert not User.objects.filter(last_name="Karimov").exists()


def test_a_super_admin_may_create_a_peer(api, super_admin):
    response = as_user(api, super_admin).post(
        reverse("management:users"),
        {"last_name": "Nazarova", "first_name": "Dilnoza", "roles": ["SUPER_ADMIN"]},
        format="json",
    )
    assert response.status_code == 201
    assert response.data["user"]["roles"] == ["SUPER_ADMIN"]


def test_a_developer_creates_a_super_admin_and_another_developer(api, developer, school):
    client = as_user(api, developer)
    for role, last in (("SUPER_ADMIN", "Nazarov"), ("DEVELOPER", "Yusupov")):
        response = client.post(
            reverse("management:users"),
            {"last_name": last, "first_name": "Aziz", "role": role},
            format="json",
        )
        assert response.status_code == 201, role
        assert response.data["user"]["role"] == role

    # Only the platform owner role gets the Django admin.
    assert User.objects.get(last_name="Yusupov").is_staff is True
    assert User.objects.get(last_name="Nazarov").is_staff is False


def test_creating_an_account_returns_a_one_off_password(api, developer, school):
    client = as_user(api, developer)
    response = client.post(
        reverse("management:users"),
        {"last_name": "Karimov", "first_name": "Jasur", "role": "ADMIN"},
        format="json",
    )
    password = response.data["temporary_password"]

    assert len(password) >= 12
    created = User.objects.get(username=response.data["user"]["username"])
    # It works, it is not stored in the clear, and it has to be replaced.
    assert created.check_password(password)
    assert created.password != password
    assert created.must_change_password is True


def test_creating_an_account_is_audited(api, developer, school):
    client = as_user(api, developer)
    client.post(
        reverse("management:users"),
        {"last_name": "Karimov", "first_name": "Jasur", "role": "ADMIN"},
        format="json",
    )
    assert AuditLog.objects.filter(action=AuditAction.USER_CREATE).exists()


# --------------------------------------------------------------------------- #
# Temporary passwords
# --------------------------------------------------------------------------- #
def test_no_endpoint_ever_returns_an_existing_password(api, developer, school_admin):
    """The store is one-way: there is nothing to read back, for anyone."""
    client = as_user(api, developer)
    listed = client.get(reverse("management:users"))

    body = str(listed.data)
    assert "password" not in body.lower() or "must_change_password" in body
    for row in listed.data["results"]:
        assert "password" not in {key for key in row if key != "must_change_password"}


def test_a_developer_issues_a_fresh_password_for_a_locked_out_admin(
    api, developer, school_admin
):
    client = as_user(api, developer)
    response = client.post(
        reverse("management:user-reset-password", args=[school_admin.pk])
    )
    assert response.status_code == 200

    password = response.data["temporary_password"]
    school_admin.refresh_from_db()
    assert school_admin.check_password(password)
    assert school_admin.check_password(PASSWORD) is False  # the old one is dead
    assert school_admin.must_change_password is True


def test_a_reset_kills_every_live_session(api, developer, school_admin):
    from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken

    issue_tokens(school_admin)
    client = as_user(api, developer)
    client.post(reverse("management:user-reset-password", args=[school_admin.pk]))

    assert BlacklistedToken.objects.exists()


def test_a_reset_is_audited_with_who_did_it(api, developer, school_admin):
    client = as_user(api, developer)
    client.post(reverse("management:user-reset-password", args=[school_admin.pk]))

    entry = AuditLog.objects.filter(action=AuditAction.USER_PASSWORD_RESET).first()
    assert entry is not None
    assert entry.user_id == developer.pk
    assert entry.metadata["target"] == school_admin.username


def test_a_super_admin_cannot_reset_a_developer(api, super_admin, developer):
    client = as_user(api, super_admin)
    response = client.post(reverse("management:user-reset-password", args=[developer.pk]))
    assert response.status_code == 404  # not even visible


def test_nobody_resets_their_own_password_from_here(api, developer):
    client = as_user(api, developer)
    response = client.post(reverse("management:user-reset-password", args=[developer.pk]))
    assert response.status_code == 409
    assert response.data["error"]["code"] == "SELF_MANAGEMENT"


# --------------------------------------------------------------------------- #
# Editing your own account
# --------------------------------------------------------------------------- #
def test_an_operator_edits_their_own_name_phone_and_lower_roles(api, developer):
    rbac.set_roles(developer, [Role.DEVELOPER])
    response = as_user(api, developer).patch(
        reverse("management:user-detail", args=[developer.pk]),
        {
            "first_name": "Bosh",
            "last_name": "Dasturchi",
            "phone": "+998901234567",
            "roles": [Role.DEVELOPER, Role.TEACHER],
        },
        format="json",
    )
    assert response.status_code == 200, response.data
    developer.refresh_from_db()
    assert developer.first_name == "Bosh"
    assert developer.phone == "+998901234567"
    assert set(developer.role_codes) == {Role.DEVELOPER, Role.TEACHER}
    # Still working through the role they were in.
    assert developer.role == Role.DEVELOPER
    assert developer.is_superuser is True


def test_nobody_drops_their_own_highest_role(api, developer):
    rbac.set_roles(developer, [Role.DEVELOPER, Role.TEACHER])
    response = as_user(api, developer).patch(
        reverse("management:user-detail", args=[developer.pk]),
        {"roles": [Role.TEACHER]},
        format="json",
    )
    assert response.status_code == 409
    assert response.data["error"]["code"] == "SELF_TOP_ROLE"
    assert Role.DEVELOPER in developer.role_codes


def test_nobody_switches_their_own_account_off(api, developer):
    response = as_user(api, developer).patch(
        reverse("management:user-detail", args=[developer.pk]),
        {"is_active": False},
        format="json",
    )
    assert response.status_code == 409
    assert response.data["error"]["code"] == "SELF_DEACTIVATION"
    developer.refresh_from_db()
    assert developer.is_active is True


def test_a_super_admin_cannot_promote_themselves_to_developer(api, super_admin):
    rbac.set_roles(super_admin, [Role.SUPER_ADMIN])
    response = as_user(api, super_admin).patch(
        reverse("management:user-detail", args=[super_admin.pk]),
        {"roles": [Role.SUPER_ADMIN, Role.DEVELOPER]},
        format="json",
    )
    assert response.status_code == 403
    assert Role.DEVELOPER not in super_admin.role_codes


def test_nobody_deletes_themselves(api, developer):
    response = as_user(api, developer).delete(
        reverse("management:user-detail", args=[developer.pk])
    )
    assert response.status_code == 409
    assert User.objects.filter(pk=developer.pk).exists()


def test_the_list_marks_your_own_row_as_editable_but_not_manageable(api, developer):
    rbac.set_roles(developer, [Role.DEVELOPER])
    rows = as_user(api, developer).get(reverse("management:users")).data["results"]
    mine = next(row for row in rows if row["id"] == developer.pk)
    assert mine["is_self"] is True
    assert mine["can_edit"] is True
    assert mine["can_manage"] is False
    assert mine["locked_role"] == Role.DEVELOPER


def test_a_moderator_cannot_edit_even_themselves(api):
    moderator = User.objects.create_user(
        username="watcher", password=PASSWORD, role=Role.MODERATOR
    )
    rbac.set_roles(moderator, [Role.MODERATOR])
    client = as_user(api, moderator)
    rows = client.get(reverse("management:users")).data["results"]
    assert next(row for row in rows if row["id"] == moderator.pk)["can_edit"] is False
    response = client.patch(
        reverse("management:user-detail", args=[moderator.pk]),
        {"first_name": "Boshqa"},
        format="json",
    )
    assert response.status_code == 403


# --------------------------------------------------------------------------- #
# Editing accounts
# --------------------------------------------------------------------------- #
def test_deactivating_an_account_revokes_its_sessions(api, developer, school_admin):
    from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken

    issue_tokens(school_admin)
    client = as_user(api, developer)
    response = client.patch(
        reverse("management:user-detail", args=[school_admin.pk]),
        {"is_active": False},
        format="json",
    )
    assert response.status_code == 200
    school_admin.refresh_from_db()
    assert school_admin.is_active is False
    assert BlacklistedToken.objects.exists()


def test_a_super_admin_cannot_grant_the_developer_role(api, super_admin, school_admin):
    client = as_user(api, super_admin)
    response = client.patch(
        reverse("management:user-detail", args=[school_admin.pk]),
        {"roles": ["DEVELOPER"]},
        format="json",
    )
    assert response.status_code == 403
    school_admin.refresh_from_db()
    assert school_admin.role == Role.ADMIN
    assert school_admin.role_codes == [Role.ADMIN]


def test_a_developer_may_promote_an_admin(api, developer, school_admin):
    client = as_user(api, developer)
    response = client.patch(
        reverse("management:user-detail", args=[school_admin.pk]),
        {"role": "SUPER_ADMIN"},
        format="json",
    )
    assert response.status_code == 200
    school_admin.refresh_from_db()
    assert school_admin.role == Role.SUPER_ADMIN


def test_the_list_marks_which_rows_the_caller_may_touch(api, super_admin, school_admin):
    client = as_user(api, super_admin)
    rows = {row["username"]: row for row in client.get(reverse("management:users")).data["results"]}

    assert rows[school_admin.username]["can_manage"] is True
    # Their own row is visible but not editable from here.
    assert rows[super_admin.username]["can_manage"] is False


# --------------------------------------------------------------------------- #
# Registration visibility
# --------------------------------------------------------------------------- #
def test_the_guardian_list_shows_who_has_registered(
    api, super_admin, guardian, guardian_links, parent_user, student
):
    client = as_user(api, super_admin)
    response = client.get(reverse("management:guardians"))
    assert response.status_code == 200

    row = next(item for item in response.data["results"] if item["id"] == str(guardian.id))
    assert row["has_account"] is True
    assert row["username"] == parent_user.username
    assert row["phone"] == guardian.phone
    # The identifier is masked here as everywhere else.
    assert row["masked_jshshir"].startswith("*")

    children = {child["id"] for child in row["children"]}
    assert str(student.id) in children
    assert row["children"][0]["relation_label"] in ("Otasi", "Onasi", "Vasiysi", "Boshqa")


def test_guardians_can_be_split_by_whether_they_registered(
    api, super_admin, guardian, guardian_links, parent_user, school
):
    from apps.guardians.models import Guardian

    unclaimed = Guardian(
        school=school, first_name="Nilufar", last_name="Karimova", phone="+998901119988"
    )
    unclaimed.set_jshshir("52234567890123")
    unclaimed.save()

    client = as_user(api, super_admin)
    registered = client.get(reverse("management:guardians"), {"registered": "yes"})
    pending = client.get(reverse("management:guardians"), {"registered": "no"})

    assert {row["id"] for row in registered.data["results"]} == {str(guardian.id)}
    assert {row["id"] for row in pending.data["results"]} == {str(unclaimed.id)}


def test_pupils_can_be_split_by_whether_a_relative_registered(
    api, super_admin, student, other_student, guardian_links, parent_user
):
    client = as_user(api, super_admin)
    registered = client.get(reverse("management:students"), {"registered": "yes"})
    pending = client.get(reverse("management:students"), {"registered": "no"})

    assert str(student.id) in {row["id"] for row in registered.data["results"]}
    assert str(other_student.id) in {row["id"] for row in pending.data["results"]}


def test_a_pupil_row_counts_its_registered_guardians(
    api, super_admin, student, guardian_links, parent_user
):
    client = as_user(api, super_admin)
    response = client.get(reverse("management:student-detail", args=[student.id]))
    assert response.data["registered_guardians"] == 1
    assert response.data["guardians"][0]["has_account"] is True
