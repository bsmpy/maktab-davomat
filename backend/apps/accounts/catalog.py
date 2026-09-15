"""What each role is allowed to do, written once.

This is the whole permission table for the installation. Views name a
permission (``read_permission = Perm.STUDENTS_VIEW``) instead of listing roles,
so adding a role is an entry here rather than an edit in forty view classes,
and the answer to "may a CURATOR do X" is readable in one place.

Two rules hold the table together:

* **Permissions say what, scopes say whose.** ``students.view`` means "may read
  pupils"; *which* pupils is decided by the queryset filters in
  :mod:`apps.accounts.rbac`. A TEACHER and a MODERATOR both hold
  ``students.view`` and see very different lists.
* **A role is not the sum of the roles below it.** The ladder in
  ``apps.accounts.constants`` orders roles for "who may manage whom"; it does
  *not* grant permissions downwards. MODERATOR outranks ADMIN and yet cannot
  write a single row.
"""
from __future__ import annotations

from .constants import Role


class Perm:
    """Permission codes, ``<area>.<action>``.

    Plain strings on purpose: they travel to the browser in ``/auth/me/`` and
    are compared as strings on both sides.
    """

    # Platform ownership — the surfaces only the owner sees.
    SYSTEM_DEVELOPER = "system.developer"

    # Cabinet accounts and the roles on them.
    USERS_VIEW = "users.view"
    USERS_MANAGE = "users.manage"
    ROLES_ASSIGN = "roles.assign"
    AUDIT_VIEW = "audit.view"

    # Sozlamalar.
    SETTINGS_VIEW = "settings.view"
    SETTINGS_APPEARANCE = "settings.appearance"
    INTEGRATIONS_VIEW = "integrations.view"
    INTEGRATIONS_MANAGE = "integrations.manage"

    # The register.
    #: The console itself. Held by the roles that administer a school, and by
    #: nobody else — a TEACHER holds ``classes.view`` for *their own* classes,
    #: which must not be mistaken for the right to open Boshqaruv.
    REGISTER_ACCESS = "register.access"
    SCHOOL_VIEW = "school.view"
    SCHOOL_MANAGE = "school.manage"
    STUDENTS_VIEW = "students.view"
    STUDENTS_MANAGE = "students.manage"
    TEACHERS_VIEW = "teachers.view"
    TEACHERS_MANAGE = "teachers.manage"
    STAFF_VIEW = "staff.view"
    STAFF_MANAGE = "staff.manage"
    POSITIONS_VIEW = "positions.view"
    POSITIONS_MANAGE = "positions.manage"
    CLASSES_VIEW = "classes.view"
    CLASSES_MANAGE = "classes.manage"
    SUBJECTS_VIEW = "subjects.view"
    SUBJECTS_MANAGE = "subjects.manage"
    TIMETABLE_VIEW = "timetable.view"
    TIMETABLE_MANAGE = "timetable.manage"
    CURATORS_VIEW = "curators.view"
    CURATORS_MANAGE = "curators.manage"
    GUARDIANS_VIEW = "guardians.view"

    # Davomat.
    ATTENDANCE_VIEW = "attendance.view"
    ATTENDANCE_MARK = "attendance.mark"
    ABSENCE_REVIEW = "absence.review"

    # Numbers and files.
    REPORTS_VIEW = "reports.view"
    EXPORT_RUN = "export.run"
    IMPORT_RUN = "import.run"

    # Everybody's own corner of the cabinet.
    SELF_VIEW = "self.view"
    #: The employee's own day at the turnstile: arrival, departure, chronology.
    #: Every role that works at the school has it; a parent does not, because
    #: a parent does not clock in.
    STAFF_CABINET = "staff.cabinet"
    CHILDREN_VIEW = "children.view"


#: Every permission there is — what a DEVELOPER holds.
ALL_PERMISSIONS: frozenset[str] = frozenset(
    value
    for name, value in vars(Perm).items()
    if not name.startswith("_") and isinstance(value, str)
)

#: Read-only half of the register: what "may look at the school" means.
_REGISTER_READ = frozenset(
    {
        Perm.REGISTER_ACCESS,
        Perm.SCHOOL_VIEW,
        Perm.STUDENTS_VIEW,
        Perm.TEACHERS_VIEW,
        Perm.STAFF_VIEW,
        Perm.POSITIONS_VIEW,
        Perm.CLASSES_VIEW,
        Perm.SUBJECTS_VIEW,
        Perm.TIMETABLE_VIEW,
        Perm.CURATORS_VIEW,
        Perm.GUARDIANS_VIEW,
        Perm.ATTENDANCE_VIEW,
        Perm.REPORTS_VIEW,
        Perm.SELF_VIEW,
        Perm.STAFF_CABINET,
    }
)

#: Write half, for the roles that actually run the register.
_REGISTER_WRITE = frozenset(
    {
        Perm.STUDENTS_MANAGE,
        Perm.TEACHERS_MANAGE,
        Perm.STAFF_MANAGE,
        Perm.POSITIONS_MANAGE,
        Perm.CLASSES_MANAGE,
        Perm.SUBJECTS_MANAGE,
        Perm.TIMETABLE_MANAGE,
        Perm.CURATORS_MANAGE,
        Perm.SCHOOL_MANAGE,
        Perm.ATTENDANCE_MARK,
        Perm.ABSENCE_REVIEW,
        Perm.EXPORT_RUN,
        Perm.IMPORT_RUN,
    }
)


#: Everything that shows or changes *somebody else's* attendance: the gate and
#: lesson registers, absence requests, and the school-wide figures built on
#: them. Held back from ADMIN as a block.
_OTHERS_ATTENDANCE = frozenset(
    {
        Perm.ATTENDANCE_VIEW,
        Perm.ATTENDANCE_MARK,
        Perm.ABSENCE_REVIEW,
        Perm.REPORTS_VIEW,
    }
)


#: role → what it may do. Scopes narrow this further; see ``rbac``.
ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    # The platform owner. No artificial limits anywhere, by design.
    Role.DEVELOPER: ALL_PERMISSIONS,
    # Everything a school can need, minus the two things that belong to the
    # platform rather than to the school: the DEVELOPER surfaces, and writing
    # integration credentials (bot tokens, turnstile passwords).
    Role.SUPER_ADMIN: ALL_PERMISSIONS
    - {Perm.SYSTEM_DEVELOPER, Perm.INTEGRATIONS_MANAGE},
    # Read-only, everywhere. Not a weaker administrator — an observer: the
    # table below is the entire reason POST/PATCH/DELETE answer 403 for them.
    # ``settings.view`` only opens the Sozlamalar shell, because O'quvchilar and
    # Lavozimlar live inside it; appearance and integrations stay shut.
    Role.MODERATOR: _REGISTER_READ | {Perm.USERS_VIEW, Perm.SETTINGS_VIEW},
    # Runs the school day to day. Sozlamalar opens for the appearance
    # switches only — no integrations, no accounts, no audit trail. And no
    # attendance of anybody else: not the pupils', not the teachers', not the
    # staff's — no Davomat, no Kalendar, no school figures. Their own day at the
    # gate stays theirs through ``staff.cabinet``.
    Role.ADMIN: (_REGISTER_READ | _REGISTER_WRITE | {Perm.SETTINGS_VIEW, Perm.SETTINGS_APPEARANCE})
    - _OTHERS_ATTENDANCE,
    # Their own subjects, their own classes, their own pupils.
    Role.TEACHER: frozenset(
        {
            Perm.SELF_VIEW,
            Perm.STAFF_CABINET,
            Perm.CLASSES_VIEW,
            Perm.SUBJECTS_VIEW,
            Perm.STUDENTS_VIEW,
            Perm.TIMETABLE_VIEW,
            Perm.ATTENDANCE_VIEW,
            Perm.ATTENDANCE_MARK,
            Perm.ABSENCE_REVIEW,
        }
    ),
    # The groups they were put in charge of, and nothing else. No marking:
    # a curator watches a class, they do not teach it.
    Role.CURATOR: frozenset(
        {
            Perm.SELF_VIEW,
            Perm.STAFF_CABINET,
            Perm.CLASSES_VIEW,
            Perm.STUDENTS_VIEW,
            Perm.TIMETABLE_VIEW,
            Perm.ATTENDANCE_VIEW,
            Perm.REPORTS_VIEW,
        }
    ),
    # An ordinary employee: their own day at the gate, and nothing about
    # anybody else.
    Role.STAFF: frozenset({Perm.SELF_VIEW, Perm.STAFF_CABINET}),
    # Their own children's days.
    Role.PARENT: frozenset({Perm.SELF_VIEW, Perm.CHILDREN_VIEW}),
}


def permissions_for(role: str | None) -> frozenset[str]:
    """What one role may do. Unknown roles may do nothing."""
    if not role:
        return frozenset()
    return ROLE_PERMISSIONS.get(role, frozenset())


def role_has_permission(role: str | None, permission: str) -> bool:
    return permission in permissions_for(role)
