"""Roles, the hierarchy between them, and who may hand which one out.

A user holds *several* roles (``accounts.UserRole``) and works through one of
them at a time (``User.active_role``). This module is the vocabulary: the role
codes themselves, the ladder they sit on, and the rules about who may grant
what. What each role may *do* lives next door in :mod:`apps.accounts.catalog`,
and the checks that read both live in :mod:`apps.accounts.rbac`.

The codes are deliberately not translated: ``TEACHER`` reads as ``TEACHER`` in
Uzbek, Russian and English alike, so a role named in a support call means the
same thing on every screen. That is why every label below equals its value.
"""
from django.db import models


class Role(models.TextChoices):
    """Access levels, most privileged first.

    ``DEVELOPER`` is the platform-owner role: it bypasses every scope check, is
    the only role allowed to change integration credentials, and is invisible
    to everybody else — a SUPER_ADMIN cannot see it, search it, fetch it by id
    or grant it.

    ``PARENT`` is the Python name of the ``OTA-ONA`` role; the code on the wire
    and in the database is ``OTA-ONA``. The member keeps its old name so the
    hundreds of ``Role.PARENT`` references across the project stay correct.
    """

    DEVELOPER = "DEVELOPER", "DEVELOPER"
    SUPER_ADMIN = "SUPER_ADMIN", "SUPER_ADMIN"
    MODERATOR = "MODERATOR", "MODERATOR"
    ADMIN = "ADMIN", "ADMIN"
    TEACHER = "TEACHER", "TEACHER"
    CURATOR = "CURATOR", "CURATOR"
    STAFF = "STAFF", "STAFF"
    PARENT = "OTA-ONA", "OTA-ONA"

    # --- groupings the rest of the project asks about ------------------- #
    @classmethod
    def admin_roles(cls) -> tuple[str, ...]:
        """Roles that run a school's register and see all of it."""
        return (cls.DEVELOPER, cls.SUPER_ADMIN, cls.MODERATOR, cls.ADMIN)

    @classmethod
    def staff_roles(cls) -> tuple[str, ...]:
        """Deprecated alias of :meth:`admin_roles` — kept for older callers.

        Not to be confused with ``Role.STAFF``, which is one ordinary employee.
        """
        return cls.admin_roles()

    @classmethod
    def elevated_roles(cls) -> tuple[str, ...]:
        """Everything above a parent: the cabinet's working roles."""
        return (
            cls.DEVELOPER,
            cls.SUPER_ADMIN,
            cls.MODERATOR,
            cls.ADMIN,
            cls.TEACHER,
            cls.CURATOR,
            cls.STAFF,
        )

    @classmethod
    def unrestricted_roles(cls) -> tuple[str, ...]:
        """Roles that are never scoped to a single school."""
        return (cls.DEVELOPER, cls.SUPER_ADMIN, cls.MODERATOR)

    @classmethod
    def read_only_roles(cls) -> tuple[str, ...]:
        """Roles that may look at everything and change nothing."""
        return (cls.MODERATOR,)

    @classmethod
    def settings_roles(cls) -> tuple[str, ...]:
        """Who may open Sozlamalar.

        An ADMIN reaches it for the two appearance switches and nothing else;
        the integration credentials inside are filtered per-section by
        :mod:`apps.accounts.catalog`.
        """
        return (cls.DEVELOPER, cls.SUPER_ADMIN, cls.ADMIN)

    @classmethod
    def integration_roles(cls) -> tuple[str, ...]:
        """Who may read integration configuration."""
        return (cls.DEVELOPER, cls.SUPER_ADMIN)

    @classmethod
    def integration_write_roles(cls) -> tuple[str, ...]:
        """Who may change credentials. Deliberately DEVELOPER only."""
        return (cls.DEVELOPER,)

    @classmethod
    def staff_assignable_roles(cls) -> tuple[str, ...]:
        """Roles a staff member's cabinet account may be given.

        ``DEVELOPER`` is deliberately absent: it is not a job anybody holds at
        a school — it is the platform owner's own account, which exists outside
        the register. Whoever is provisioning is still limited by
        :func:`manageable_roles` on top of this.
        """
        return (
            cls.SUPER_ADMIN,
            cls.MODERATOR,
            cls.ADMIN,
            cls.TEACHER,
            cls.CURATOR,
            cls.STAFF,
        )

    @classmethod
    def user_management_roles(cls) -> tuple[str, ...]:
        """Who may open Foydalanuvchilar and provision accounts."""
        return (cls.DEVELOPER, cls.SUPER_ADMIN)


#: Rank used for "at least this privileged" comparisons.
ROLE_RANK = {
    Role.PARENT: 0,
    Role.STAFF: 1,
    Role.CURATOR: 2,
    Role.TEACHER: 3,
    Role.ADMIN: 4,
    Role.MODERATOR: 5,
    Role.SUPER_ADMIN: 6,
    Role.DEVELOPER: 7,
}

#: The role a cabinet account falls back to when nobody picked one for it.
#: Everybody who works at the school is at least an employee.
DEFAULT_STAFF_ROLE = Role.STAFF


def rank(role: str) -> int:
    return ROLE_RANK.get(role, -1)


def at_least(role: str, minimum: str) -> bool:
    return rank(role) >= rank(minimum)


#: Roles an operator may provision by hand, in the order the UI offers them.
#: ``OTA-ONA`` is never provisioned — a parent proves who they are and
#: registers themselves.
PROVISIONABLE_ROLES = (
    Role.DEVELOPER,
    Role.SUPER_ADMIN,
    Role.MODERATOR,
    Role.ADMIN,
    Role.TEACHER,
    Role.CURATOR,
    Role.STAFF,
)


def manageable_roles(actor_role: str) -> tuple[str, ...]:
    """Which roles ``actor_role`` may create, edit and reset passwords for.

    A SUPER_ADMIN provisions everything below the platform owner, its own role
    included: a school that has one needs to be able to grow a second without
    the platform owner being on the phone. DEVELOPER may create its own role
    too, because somebody has to be able to hand the platform over. Nobody else
    provisions at all.
    """
    if actor_role == Role.DEVELOPER:
        return PROVISIONABLE_ROLES
    if actor_role == Role.SUPER_ADMIN:
        return tuple(role for role in PROVISIONABLE_ROLES if role != Role.DEVELOPER)
    return ()


def can_manage_role(actor_role: str, target_role: str) -> bool:
    return target_role in manageable_roles(actor_role)


def staff_roles_for(actor_role: str) -> tuple[str, ...]:
    """What ``actor_role`` may hand to a member of the staff register.

    The intersection of two rules: nobody provisions above their own station,
    and nobody is a DEVELOPER by way of the staff register.
    """
    allowed = set(Role.staff_assignable_roles())
    return tuple(role for role in manageable_roles(actor_role) if role in allowed)
