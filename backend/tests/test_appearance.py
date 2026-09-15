"""Ko'rinish: the interface switches that apply to everybody.

These used to be a per-browser preference. The rule now is the opposite: one
row decides for the whole installation, the two unscoped roles move it, and
everybody else reads it.
"""
from __future__ import annotations

import pytest
from django.urls import reverse

from apps.accounts.constants import Role
from apps.accounts.models import User
from apps.accounts.services.auth import issue_tokens
from apps.audit.constants import AuditAction
from apps.audit.models import AuditLog
from apps.common.models import AppearanceSettings

pytestmark = pytest.mark.django_db

PASSWORD = "Test!Parol2026"
URL = "appearance"


def make_user(username: str, role: str) -> User:
    return User.objects.create_user(username=username, password=PASSWORD, role=role)


def as_user(api, user):
    access, _refresh, _ttl = issue_tokens(user)
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return api


def test_the_row_is_created_on_first_read_with_everything_on(api):
    assert AppearanceSettings.objects.count() == 0

    body = as_user(api, make_user("first.reader", Role.PARENT)).get(reverse(URL)).data

    assert body["multi_theme"] is True
    assert body["particles"] is True
    assert AppearanceSettings.objects.count() == 1


@pytest.mark.parametrize(
    "role",
    [Role.DEVELOPER, Role.SUPER_ADMIN, Role.ADMIN, Role.TEACHER, Role.PARENT],
)
def test_everyone_signed_in_may_read_it(api, role):
    """A parent's browser has to know whether to draw the theme menu at all."""
    user = make_user(f"reader.{role.lower()}", role)
    assert as_user(api, user).get(reverse(URL)).status_code == 200


def test_an_anonymous_visitor_may_not(api):
    api.credentials()
    assert api.get(reverse(URL)).status_code == 401


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        (Role.DEVELOPER, 200),
        (Role.SUPER_ADMIN, 200),
        # Mavzular and Zarrachalar are the two settings a school administrator
        # owns: they are about how the cabinet looks to the people in it, not
        # about the installation's credentials.
        (Role.ADMIN, 200),
        (Role.MODERATOR, 403),
        (Role.TEACHER, 403),
        (Role.CURATOR, 403),
        (Role.STAFF, 403),
        (Role.PARENT, 403),
    ],
)
def test_only_the_settings_roles_may_change_it(api, role, expected):
    user = make_user(f"writer.{role.lower()}", role)
    response = as_user(api, user).patch(reverse(URL), {"particles": False}, format="json")
    assert response.status_code == expected


def test_a_refused_write_changes_nothing(api):
    AppearanceSettings.load()
    teacher = make_user("nosy.teacher", Role.TEACHER)

    as_user(api, teacher).patch(reverse(URL), {"particles": False}, format="json")

    assert AppearanceSettings.load().particles is True


def test_can_edit_tells_the_client_which_it_is(api):
    developer = make_user("cap.dev", Role.DEVELOPER)
    parent = make_user("cap.parent", Role.PARENT)

    assert as_user(api, developer).get(reverse(URL)).data["can_edit"] is True
    assert as_user(api, parent).get(reverse(URL)).data["can_edit"] is False


def test_what_a_super_admin_turns_off_is_off_for_a_parent_too(api):
    """The point of the whole change: one switch, everybody's screen."""
    super_admin = make_user("boss", Role.SUPER_ADMIN)
    parent = make_user("ota", Role.PARENT)

    as_user(api, super_admin).patch(
        reverse(URL), {"multi_theme": False, "particles": False}, format="json"
    )

    seen_by_parent = as_user(api, parent).get(reverse(URL)).data
    assert seen_by_parent["multi_theme"] is False
    assert seen_by_parent["particles"] is False


def test_a_partial_write_leaves_the_other_switch_alone(api):
    developer = make_user("half.dev", Role.DEVELOPER)

    as_user(api, developer).patch(reverse(URL), {"particles": False}, format="json")

    row = AppearanceSettings.load()
    assert row.particles is False
    assert row.multi_theme is True


def test_a_change_is_audited_with_who_and_what(api):
    developer = make_user("audited.dev", Role.DEVELOPER)

    as_user(api, developer).patch(reverse(URL), {"particles": False}, format="json")

    entry = AuditLog.objects.filter(action=AuditAction.APPEARANCE_UPDATE).get()
    assert entry.user == developer
    assert entry.old_data["particles"] is True
    assert entry.new_data["particles"] is False


def test_writing_the_same_values_is_not_an_audit_entry(api):
    developer = make_user("noop.dev", Role.DEVELOPER)
    AppearanceSettings.load()

    as_user(api, developer).patch(reverse(URL), {"particles": True}, format="json")

    assert not AuditLog.objects.filter(action=AuditAction.APPEARANCE_UPDATE).exists()


def test_there_is_only_ever_one_row(api):
    """Saving a second instance updates the first rather than adding to it."""
    AppearanceSettings.load()
    AppearanceSettings(multi_theme=False).save()

    assert AppearanceSettings.objects.count() == 1
    assert AppearanceSettings.load().multi_theme is False
