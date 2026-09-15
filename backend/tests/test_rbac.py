"""Roles, the hats people wear, and what each one can actually reach.

The suite is written against the API rather than against the helpers, because
the promise being tested is "a request from this person cannot get that row" —
and a request is the only thing that proves it. Where a role must not see
something, the assertion is on the *response*, not on a queryset.
"""
from __future__ import annotations

import pytest
from django.urls import reverse

from apps.accounts import rbac
from apps.accounts.catalog import Perm
from apps.accounts.constants import Role
from apps.accounts.models import User, UserRole
from apps.accounts.services.auth import issue_tokens
from apps.schools.models import ClassGroup, CuratorAssignment, StaffMember

from .conftest import PASSWORD

pytestmark = pytest.mark.django_db


def as_user(api, user):
    access, _refresh, _ttl = issue_tokens(user)
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return api


def make_user(username: str, *roles: str) -> User:
    """An account holding several roles, opened on the most privileged one."""
    user = User.objects.create_user(username=username, password=PASSWORD, role=roles[0])
    rbac.set_roles(user, roles, keep_active=False)
    user.refresh_from_db()
    return user


# --------------------------------------------------------------------------- #
# Several roles on one person
# --------------------------------------------------------------------------- #
def test_one_person_may_hold_several_roles():
    user = make_user("multi", Role.TEACHER, Role.CURATOR, Role.STAFF)

    assert set(user.role_codes) == {Role.TEACHER, Role.CURATOR, Role.STAFF}
    # Most privileged first, and that is where the session opens.
    assert user.role_codes[0] == Role.TEACHER
    assert user.active_role == Role.TEACHER


def test_the_active_role_decides_what_the_session_may_do():
    """Roles are not summed: an admin working as a teacher is a teacher."""
    user = make_user("both", Role.ADMIN, Role.TEACHER)
    assert user.has_permission(Perm.STUDENTS_MANAGE) is True

    rbac.set_active_role(user, Role.TEACHER)
    assert user.has_permission(Perm.STUDENTS_MANAGE) is False
    assert user.has_permission(Perm.ATTENDANCE_MARK) is True
    # The role itself is still held — it is simply not the one in use.
    assert user.has_role(Role.ADMIN) is True


def test_an_account_saved_with_a_role_holds_it():
    """Every creation path writes the role table, not only the console."""
    user = User.objects.create_user(username="signal", password=PASSWORD, role=Role.TEACHER)
    assert UserRole.objects.filter(user=user, role=Role.TEACHER).exists()


def test_an_account_with_no_roles_becomes_staff():
    user = User.objects.create_user(username="blank", password=PASSWORD, role=Role.STAFF)
    rbac.set_roles(user, [])
    user.refresh_from_db()
    assert user.role_codes == [Role.STAFF]
    assert user.active_role == Role.STAFF


def test_revoking_the_active_role_moves_the_person_to_another_one():
    user = make_user("demoted", Role.ADMIN, Role.STAFF)
    assert user.active_role == Role.ADMIN

    rbac.revoke_role(user, Role.ADMIN)
    user.refresh_from_db()
    assert user.role_codes == [Role.STAFF]
    assert user.active_role == Role.STAFF


# --------------------------------------------------------------------------- #
# Switching hats
# --------------------------------------------------------------------------- #
def test_switching_the_active_role_needs_no_second_login(api):
    user = make_user("switcher", Role.TEACHER, Role.CURATOR)
    client = as_user(api, user)

    response = client.post(
        reverse("auth:active-role"), {"role": Role.CURATOR}, format="json"
    )
    assert response.status_code == 200
    assert response.data["user"]["active_role"] == Role.CURATOR
    assert set(response.data["user"]["roles"]) == {Role.TEACHER, Role.CURATOR}

    user.refresh_from_db()
    assert user.active_role == Role.CURATOR


def test_the_switch_survives_a_reload(api):
    """It is stored on the account, so /me answers the same after a refresh."""
    user = make_user("sticky", Role.TEACHER, Role.STAFF)
    client = as_user(api, user)
    client.post(reverse("auth:active-role"), {"role": Role.STAFF}, format="json")

    assert client.get(reverse("auth:me")).data["active_role"] == Role.STAFF


def test_nobody_can_switch_into_a_role_they_were_never_given(api):
    user = make_user("climber", Role.TEACHER, Role.STAFF)
    client = as_user(api, user)

    response = client.post(
        reverse("auth:active-role"), {"role": Role.DEVELOPER}, format="json"
    )
    assert response.status_code == 403

    user.refresh_from_db()
    assert user.active_role == Role.TEACHER
    assert Role.DEVELOPER not in user.role_codes


def test_me_carries_everything_the_cabinet_draws_itself_from(api, teaching_user):
    body = as_user(api, teaching_user).get(reverse("auth:me")).data

    assert body["active_role"] == Role.TEACHER
    assert body["roles"] == [Role.TEACHER]
    assert Perm.ATTENDANCE_MARK in body["permissions"]
    assert Perm.STUDENTS_MANAGE not in body["permissions"]
    # The teacher's own world, by name, so the rail can draw it.
    assert [row["class_group"] for row in body["scope"]["teacher_subjects"]] == ["7-A"]
    assert [row["display_name"] for row in body["scope"]["teacher_groups"]] == ["7-A"]


def test_role_codes_are_never_translated(api, teaching_user):
    """TEACHER reads as TEACHER on a Russian screen as much as an Uzbek one."""
    body = as_user(api, teaching_user).get(reverse("auth:me")).data
    assert body["role_label"] == "TEACHER"


# --------------------------------------------------------------------------- #
# DEVELOPER is invisible to everybody else
# --------------------------------------------------------------------------- #
@pytest.fixture
def developer() -> User:
    return make_user("platform.owner", Role.DEVELOPER)


@pytest.fixture
def super_admin() -> User:
    return make_user("boss", Role.SUPER_ADMIN)


def test_a_super_admin_never_sees_a_developer_in_the_list(api, developer, super_admin):
    rows = as_user(api, super_admin).get(reverse("management:users")).data["results"]
    assert developer.username not in {row["username"] for row in rows}


def test_a_developer_is_hidden_even_when_wearing_another_hat(api, super_admin):
    """The role is an identity, not a hat: switching does not reveal them."""
    owner = make_user("owner.teaching", Role.DEVELOPER, Role.TEACHER)
    rbac.set_active_role(owner, Role.TEACHER)

    rows = as_user(api, super_admin).get(reverse("management:users")).data["results"]
    assert owner.username not in {row["username"] for row in rows}


def test_asking_for_a_developer_by_id_answers_not_found(api, developer, super_admin):
    """No 403 either — a refusal would confirm the account exists."""
    client = as_user(api, super_admin)
    url = reverse("management:user-detail", args=[developer.pk])

    assert client.get(url).status_code == 404
    assert client.patch(url, {"is_active": False}, format="json").status_code == 404
    assert client.delete(url).status_code == 404
    assert (
        client.post(
            reverse("management:user-reset-password", args=[developer.pk]), {}, format="json"
        ).status_code
        == 404
    )

    developer.refresh_from_db()
    assert developer.is_active is True


def test_the_developer_role_is_not_on_offer_to_a_super_admin(api, super_admin):
    body = as_user(api, super_admin).get(reverse("management:users")).data
    assert Role.DEVELOPER not in {row["value"] for row in body["assignable_roles"]}


def test_a_developer_sees_every_developer(api, developer):
    peer = make_user("second.owner", Role.DEVELOPER)
    rows = as_user(api, developer).get(reverse("management:users")).data["results"]
    assert peer.username in {row["username"] for row in rows}


# --------------------------------------------------------------------------- #
# MODERATOR: reads everything, writes nothing
# --------------------------------------------------------------------------- #
@pytest.fixture
def moderator(school) -> User:
    user = make_user("watcher", Role.MODERATOR)
    return user


def test_a_moderator_may_read_the_register(api, moderator, class_groups, student):
    client = as_user(api, moderator)
    for name in ("grades", "class-groups", "students", "teachers", "staff", "subjects"):
        assert client.get(reverse(f"management:{name}")).status_code == 200, name


def test_a_moderator_may_not_write_anything(api, moderator, school, class_groups, student):
    client = as_user(api, moderator)
    group = class_groups["7-A"]

    assert client.post(reverse("management:grades"), {"level": 9}, format="json").status_code == 403
    assert (
        client.patch(
            reverse("management:class-group-detail", args=[group.id]),
            {"room": "101"},
            format="json",
        ).status_code
        == 403
    )
    assert (
        client.delete(reverse("management:student-detail", args=[student.id])).status_code == 403
    )
    assert (
        client.post(
            reverse("management:positions"), {"title_uz": "Hisobchi"}, format="json"
        ).status_code
        == 403
    )


def test_a_moderator_may_not_mark_attendance(api, moderator, class_subject):
    response = as_user(api, moderator).post(
        reverse("teaching:teaching-roster", args=[class_subject.id]),
        {"date": "2026-09-08", "marks": []},
        format="json",
    )
    assert response.status_code == 403


def test_a_moderator_reads_settings_but_changes_nothing_in_them(api, moderator):
    """Sozlamalar holds O'quvchilar and Lavozimlar now, so a moderator opens it.

    Opening is all: the appearance switches and the integrations stay shut.
    """
    client = as_user(api, moderator)
    assert client.get(reverse("settings:overview")).status_code == 200
    assert client.get(reverse("settings:integrations")).status_code == 403
    assert client.patch(reverse("appearance"), {"particles": False}, format="json").status_code == 403
    # Reading the user list is allowed; provisioning is not.
    assert client.post(
        reverse("management:users"),
        {"last_name": "Yangi", "first_name": "Xodim", "roles": ["STAFF"]},
        format="json",
    ).status_code == 403


# --------------------------------------------------------------------------- #
# ADMIN: runs the school, does not run the platform
# --------------------------------------------------------------------------- #
@pytest.fixture
def school_admin(school) -> User:
    from apps.schools.models import Teacher

    user = make_user("maktabadmin", Role.ADMIN)
    Teacher.objects.create(school=school, user=user, first_name="Nodir", last_name="Adminov")
    return user


def test_an_admin_runs_the_register(api, school_admin, class_groups):
    client = as_user(api, school_admin)
    assert client.post(reverse("management:grades"), {"level": 9}, format="json").status_code == 201
    assert (
        client.post(
            reverse("management:positions"), {"title_uz": "Hisobchi"}, format="json"
        ).status_code
        == 201
    )


def test_an_admin_owns_the_appearance_switches_and_nothing_else_in_settings(api, school_admin):
    client = as_user(api, school_admin)
    assert client.patch(reverse("appearance"), {"particles": False}, format="json").status_code == 200
    assert client.get(reverse("settings:overview")).status_code == 200
    assert client.get(reverse("settings:integrations")).status_code == 403


def test_an_admin_cannot_reach_accounts_or_the_audit_trail(api, school_admin):
    client = as_user(api, school_admin)
    assert client.get(reverse("management:users")).status_code == 403
    assert client.get(reverse("management:audit")).status_code == 403


# --------------------------------------------------------------------------- #
# TEACHER: their own subjects, and only those
# --------------------------------------------------------------------------- #
def test_a_teacher_reaches_only_their_own_subject(api, teaching_user, class_subject, school, class_groups):
    from apps.schools.models import Subject

    someone_elses = Subject.objects.create(
        school=school, class_group=class_groups["3-A"], name="Fizika"
    )
    client = as_user(api, teaching_user)

    assert client.get(reverse("teaching:teaching-roster", args=[class_subject.id])).status_code == 200
    # Not 403: an id they may not read is an id that does not exist for them.
    assert client.get(reverse("teaching:teaching-roster", args=[someone_elses.id])).status_code == 404


def test_a_teacher_cannot_open_another_classs_day(api, teaching_user, class_groups):
    response = as_user(api, teaching_user).get(
        reverse("teaching:teaching-class-day", args=[class_groups["3-B"].id])
    )
    assert response.status_code == 404


def test_a_teacher_sees_only_the_pupils_of_their_own_groups(
    api, teaching_user, student, other_student
):
    """``student`` is in 7-A, which they teach; ``other_student`` is in 7-B."""
    rows = as_user(api, teaching_user).get(reverse("children")).data["results"]
    ids = {row["id"] for row in rows}
    assert str(student.id) in ids
    assert str(other_student.id) not in ids


def test_a_teacher_cannot_open_a_pupil_from_another_class(api, teaching_user, other_student):
    response = as_user(api, teaching_user).get(
        reverse("child-detail", args=[other_student.id])
    )
    assert response.status_code == 404


# --------------------------------------------------------------------------- #
# CURATOR: the groups they were given
# --------------------------------------------------------------------------- #
@pytest.fixture
def curator(school, class_groups) -> User:
    user = make_user("a.valiyev.curator", Role.CURATOR)
    CuratorAssignment.objects.create(user=user, class_group=class_groups["7-A"])
    return user


def test_a_curator_sees_their_group_and_its_pupils(api, curator, student, other_student):
    body = as_user(api, curator).get(reverse("children")).data
    ids = {row["id"] for row in body["results"]}
    assert str(student.id) in ids
    assert str(other_student.id) not in ids


def test_a_curators_scope_is_on_their_own_me_payload(api, curator):
    scope = as_user(api, curator).get(reverse("auth:me")).data["scope"]
    assert [row["display_name"] for row in scope["curator_groups"]] == ["7-A"]


def test_a_curator_cannot_open_another_group(api, curator, class_groups):
    client = as_user(api, curator)
    assert (
        client.get(
            reverse("teaching:teaching-class-day", args=[class_groups["7-A"].id])
        ).status_code
        == 200
    )
    assert (
        client.get(
            reverse("teaching:teaching-class-day", args=[class_groups["3-A"].id])
        ).status_code
        == 404
    )


def test_a_curator_watches_a_class_but_does_not_mark_it(api, curator, class_subject):
    client = as_user(api, curator)
    assert client.get(reverse("teaching:teaching-roster", args=[class_subject.id])).status_code == 200
    assert (
        client.post(
            reverse("teaching:teaching-roster", args=[class_subject.id]),
            {"date": "2026-09-08", "marks": []},
            format="json",
        ).status_code
        == 403
    )


def test_assigning_a_group_grants_the_role_and_removing_the_last_takes_it_back(
    api, super_admin, school, class_groups
):
    person = make_user("kurator.nomzod", Role.STAFF)
    client = as_user(api, super_admin)

    created = client.post(
        reverse("management:curators"),
        {"user": person.pk, "class_group": str(class_groups["7-A"].id)},
        format="json",
    )
    assert created.status_code == 201
    person.refresh_from_db()
    assert Role.CURATOR in person.role_codes

    removed = client.delete(
        reverse("management:curator-detail", args=[created.data["id"]])
    )
    assert removed.status_code == 200
    assert removed.data["role_revoked"] is True
    person.refresh_from_db()
    assert Role.CURATOR not in person.role_codes


# --------------------------------------------------------------------------- #
# STAFF: themselves, and nobody else
# --------------------------------------------------------------------------- #
@pytest.fixture
def staff_member(school) -> User:
    user = make_user("oshpaz", Role.STAFF)
    StaffMember.objects.create(
        school=school, user=user, first_name="Zilola", last_name="Umarova"
    )
    return user


def test_a_staff_member_opens_their_own_cabinet(api, staff_member):
    client = as_user(api, staff_member)
    assert client.get(reverse("teaching:teacher-profile")).status_code == 200
    assert client.get(reverse("teaching:teacher-dashboard")).status_code == 200


def test_a_staff_member_cannot_read_the_staff_register(api, staff_member):
    client = as_user(api, staff_member)
    assert client.get(reverse("management:staff")).status_code == 403
    assert client.get(reverse("management:students")).status_code == 403
    assert client.get(reverse("children")).data["results"] == []


def test_a_staff_member_cannot_open_a_colleague(api, staff_member, school):
    colleague = StaffMember.objects.create(
        school=school, first_name="Rustam", last_name="Qodirov"
    )
    response = as_user(api, staff_member).get(
        reverse("management:staff-detail", args=[colleague.id])
    )
    assert response.status_code == 403
    assert rbac.can_access_staff(staff_member, colleague.id) is False


def test_a_staff_members_own_row_is_the_whole_of_their_register(api, staff_member, school):
    StaffMember.objects.create(school=school, first_name="Rustam", last_name="Qodirov")
    mine = rbac.accessible_staff(staff_member)
    assert [row.user_id for row in mine] == [staff_member.pk]


# --------------------------------------------------------------------------- #
# OTA-ONA
# --------------------------------------------------------------------------- #
def test_the_parent_role_is_called_ota_ona(parent_user):
    assert parent_user.role == "OTA-ONA"
    assert Role.PARENT.value == "OTA-ONA"
    assert Role(parent_user.role).label == "OTA-ONA"


def test_a_parent_reaches_their_children_and_no_others(api, parent_user, student, other_student):
    client = as_user(api, parent_user)
    assert client.get(reverse("child-detail", args=[student.id])).status_code == 200
    assert client.get(reverse("child-detail", args=[other_student.id])).status_code == 404
    assert rbac.can_access_child(parent_user, student.id) is True
    assert rbac.can_access_child(parent_user, other_student.id) is False


def test_a_parents_children_travel_on_the_me_payload(api, parent_user, student, sibling):
    scope = as_user(api, parent_user).get(reverse("auth:me")).data["scope"]
    assert {row["id"] for row in scope["children"]} == {str(student.id), str(sibling.id)}


def test_a_parent_has_no_employee_cabinet(api, parent_user):
    client = as_user(api, parent_user)
    assert client.get(reverse("teaching:teacher-dashboard")).status_code == 403
    assert client.get(reverse("teaching:teacher-calendar")).status_code == 403


# --------------------------------------------------------------------------- #
# Provisioning with several roles
# --------------------------------------------------------------------------- #
def test_an_account_can_be_created_with_several_roles(api, super_admin, school):
    response = as_user(api, super_admin).post(
        reverse("management:users"),
        {
            "last_name": "Valiyev",
            "first_name": "Ali",
            "roles": [Role.TEACHER, Role.CURATOR, Role.STAFF],
        },
        format="json",
    )
    assert response.status_code == 201
    assert set(response.data["user"]["roles"]) == {Role.TEACHER, Role.CURATOR, Role.STAFF}
    assert response.data["user"]["active_role"] == Role.TEACHER


def test_a_staff_account_created_without_a_role_becomes_staff(api, super_admin, school):
    response = as_user(api, super_admin).post(
        reverse("management:staff"),
        {
            "last_name": "Qodirov",
            "first_name": "Rustam",
            "username": "r.qodirov",
            "password": "Xodim!Parol2026",
            "password_confirm": "Xodim!Parol2026",
        },
        format="json",
    )
    assert response.status_code == 201
    account = User.objects.get(username="r.qodirov")
    assert account.role_codes == [Role.STAFF]


def test_roles_are_replaced_as_a_set(api, super_admin, school):
    person = make_user("rollar", Role.TEACHER, Role.STAFF)
    response = as_user(api, super_admin).patch(
        reverse("management:user-detail", args=[person.pk]),
        {"roles": [Role.CURATOR, Role.STAFF]},
        format="json",
    )
    assert response.status_code == 200
    person.refresh_from_db()
    assert set(person.role_codes) == {Role.CURATOR, Role.STAFF}


def test_a_forbidden_role_in_the_list_changes_nothing(api, super_admin):
    """All or nothing: one refused role must not leave the others applied."""
    person = make_user("rollar.2", Role.STAFF)
    response = as_user(api, super_admin).patch(
        reverse("management:user-detail", args=[person.pk]),
        {"roles": [Role.TEACHER, Role.DEVELOPER]},
        format="json",
    )
    assert response.status_code == 403
    person.refresh_from_db()
    assert person.role_codes == [Role.STAFF]


# --------------------------------------------------------------------------- #
# The audit trail
# --------------------------------------------------------------------------- #
def test_granting_and_revoking_a_role_is_recorded(api, super_admin, school):
    from apps.audit.constants import AuditAction
    from apps.audit.models import AuditLog

    person = make_user("audited", Role.STAFF)
    client = as_user(api, super_admin)
    client.patch(
        reverse("management:user-detail", args=[person.pk]),
        {"roles": [Role.TEACHER]},
        format="json",
    )

    actions = set(
        AuditLog.objects.filter(entity_id=str(person.pk)).values_list("action", flat=True)
    )
    assert AuditAction.ROLE_ASSIGNED in actions
    assert AuditAction.ROLE_REVOKED in actions


def test_switching_roles_is_recorded(api):
    from apps.audit.constants import AuditAction
    from apps.audit.models import AuditLog

    user = make_user("audited.switch", Role.TEACHER, Role.STAFF)
    as_user(api, user).post(
        reverse("auth:active-role"), {"role": Role.STAFF}, format="json"
    )
    assert AuditLog.objects.filter(
        action=AuditAction.ACTIVE_ROLE_SWITCH, user=user
    ).exists()


# --------------------------------------------------------------------------- #
# The helpers the rest of the project calls
# --------------------------------------------------------------------------- #
def test_can_access_group_is_the_same_answer_as_the_endpoint(curator, class_groups):
    assert rbac.can_access_group(curator, class_groups["7-A"].id) is True
    assert rbac.can_access_group(curator, class_groups["3-A"].id) is False


def test_can_manage_user_follows_the_ladder(super_admin, developer):
    admin = make_user("ladder.admin", Role.ADMIN)
    assert rbac.can_manage_user(super_admin, admin) is True
    assert rbac.can_manage_user(super_admin, developer) is False
    assert rbac.can_manage_user(developer, super_admin) is True
    # Nobody edits themselves out of their own station.
    assert rbac.can_manage_user(super_admin, super_admin) is False


def test_class_group_scope_by_role(school_admin, curator, teaching_user, class_groups):
    everything = set(ClassGroup.objects.values_list("id", flat=True))
    assert set(rbac.accessible_class_groups(school_admin).values_list("id", flat=True)) == everything
    assert set(rbac.accessible_class_groups(curator).values_list("id", flat=True)) == {
        class_groups["7-A"].id
    }
    assert set(rbac.accessible_class_groups(teaching_user).values_list("id", flat=True)) == {
        class_groups["7-A"].id
    }


# --------------------------------------------------------------------------- #
# An employee's own figures
# --------------------------------------------------------------------------- #
def test_a_staff_member_reads_their_own_week_month_and_year(api, staff_member):
    body = as_user(api, staff_member).get(reverse("teaching:teacher-stats")).data

    assert set(body) == {"date", "week", "month", "year"}
    for span in ("week", "month", "year"):
        assert set(body[span]) >= {
            "school_days",
            "days_present",
            "days_absent",
            "active_minutes",
            "late_days",
            "rate",
        }


def test_the_stats_endpoint_is_about_you_and_takes_no_id(api, parent_user):
    """A parent does not clock in, so there is nothing here for them."""
    assert (
        as_user(api, parent_user).get(reverse("teaching:teacher-stats")).status_code == 403
    )


def test_a_moderator_reads_the_user_list_without_being_offered_a_single_button(
    api, moderator, developer, super_admin
):
    """Reading the accounts and changing them are two different rights."""
    body = as_user(api, moderator).get(reverse("management:users")).data

    usernames = {row["username"] for row in body["results"]}
    assert super_admin.username in usernames
    # Still invisible, even to a role that may read every other account.
    assert developer.username not in usernames
    # Nothing to hand out, and no row they may touch.
    assert body["assignable_roles"] == []
    assert all(row["can_manage"] is False for row in body["results"])
