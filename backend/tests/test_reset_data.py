"""``reset_data`` — the wipe that hands back an empty register.

It is irreversible, so what it refuses to do matters as much as what it does:
it will not run without an explicit ``--yes``, it will not leave the platform
with no way in, and it keeps live integration credentials unless told not to.
"""
from __future__ import annotations

import pytest
from django.core.management import CommandError, call_command

from apps.accounts.constants import Role
from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.guardians.models import Guardian, GuardianStudent
from apps.integrations.models import DailyPresence, Integration, TerminalEvent
from apps.notifications.models import Notification
from apps.schools.models import ClassGroup, Grade, School
from apps.students.models import Student
from tests.conftest import PASSWORD

pytestmark = pytest.mark.django_db


@pytest.fixture
def owner(db) -> User:
    return User.objects.create_user(
        username="bsm", password=PASSWORD, role=Role.DEVELOPER,
        first_name="Developer", last_name="BSM", is_staff=True, is_superuser=True,
    )


@pytest.fixture
def populated(owner, school, class_groups, student, guardian, guardian_links, present_day):
    """A school with people, gate history and a live integration row."""
    Integration.objects.create(
        kind="TELEGRAM_BOT", is_enabled=True, config={"bot_username": "davomat_bot"}
    )
    Notification.objects.create(
        user=owner, type="SYSTEM", title="Salom", message="Test"
    )
    return owner


# --------------------------------------------------------------------------- #
# Refusals
# --------------------------------------------------------------------------- #
def test_it_refuses_to_run_without_an_account_to_keep(populated):
    with pytest.raises(CommandError, match="Refusing to delete every account"):
        call_command("reset_data", "--yes")
    assert Student.objects.exists()


def test_it_refuses_an_account_that_does_not_exist(populated):
    with pytest.raises(CommandError, match="No such account"):
        call_command("reset_data", "--keep-user", "nobody", "--yes")
    assert Student.objects.exists()


def test_without_yes_it_only_previews(populated):
    call_command("reset_data", "--keep-user", "bsm")
    assert Student.objects.exists()
    assert School.objects.exists()


# --------------------------------------------------------------------------- #
# The wipe
# --------------------------------------------------------------------------- #
def test_it_empties_the_register(populated):
    call_command("reset_data", "--keep-user", "bsm", "--yes")

    # Nothing survives, not even soft-deleted rows.
    assert School.all_objects.count() == 0
    assert Grade.all_objects.count() == 0
    assert ClassGroup.all_objects.count() == 0
    assert Student.all_objects.count() == 0
    assert Guardian.all_objects.count() == 0
    assert GuardianStudent.objects.count() == 0


def test_it_clears_everything_derived_from_the_gate(populated):
    assert TerminalEvent.objects.exists()
    assert DailyPresence.objects.exists()

    call_command("reset_data", "--keep-user", "bsm", "--yes")

    assert TerminalEvent.objects.count() == 0
    assert DailyPresence.objects.count() == 0
    assert Notification.objects.count() == 0
    assert AuditLog.objects.count() == 0


def test_it_keeps_exactly_the_named_account(populated):
    call_command("reset_data", "--keep-user", "bsm", "--yes")

    remaining = list(User.objects.all())
    assert len(remaining) == 1
    assert remaining[0].username == "bsm"
    assert remaining[0].role == Role.DEVELOPER
    assert remaining[0].is_superuser is True
    # The surviving account can still sign in.
    assert remaining[0].check_password(PASSWORD)


def test_it_can_keep_several_accounts(populated, super_admin_account):
    call_command("reset_data", "--keep-user", "bsm", "--keep-user", "superadmin", "--yes")
    assert set(User.objects.values_list("username", flat=True)) == {"bsm", "superadmin"}


@pytest.fixture
def super_admin_account(db) -> User:
    return User.objects.create_user(
        username="superadmin", password=PASSWORD, role=Role.SUPER_ADMIN,
        first_name="Bosh", last_name="Admin",
    )


# --------------------------------------------------------------------------- #
# Configuration is not data
# --------------------------------------------------------------------------- #
def test_integration_credentials_survive_by_default(populated):
    """Wiping the demo register must not take the running bot offline."""
    call_command("reset_data", "--keep-user", "bsm", "--yes")
    assert Integration.objects.count() == 1


def test_integrations_can_be_dropped_on_request(populated):
    call_command("reset_data", "--keep-user", "bsm", "--integrations", "--yes")
    assert Integration.objects.count() == 0


# --------------------------------------------------------------------------- #
# Afterwards
# --------------------------------------------------------------------------- #
def test_the_platform_is_usable_again_afterwards(populated):
    """An empty register is a starting point, not a broken state."""
    from apps.schools.services.management import create_class_group, create_grade

    call_command("reset_data", "--keep-user", "bsm", "--yes")

    school = School.objects.create(name="Yangi maktab")
    from apps.schools.models import AcademicYear
    from tests.conftest import TODAY

    AcademicYear.objects.create(
        school=school,
        name="2026-2027",
        start_date=TODAY.replace(month=1, day=1),
        end_date=TODAY.replace(month=12, day=31),
        is_current=True,
    )
    grade = create_grade(school=school, level=1)
    group = create_class_group(school=school, grade=grade, name="A")

    assert group.display_name == "1-A"
