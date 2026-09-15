"""The one place that answers "may this person do this, to this row?".

Everything else — DRF permission classes, querysets, serializers, the frontend
payload — reads from here, so a rule is written once and cannot drift between
the endpoint that lists rows and the endpoint that opens one.

Three kinds of question live here:

``has_role`` / ``has_permission``
    Does the person hold this role at all, and does their **active** role carry
    this permission?

``visible_*`` / ``accessible_*``
    The queryset a role may read. These are what stop a teacher from listing
    another teacher's class — they are applied before anything is serialised,
    so there is no "filtered in the UI" version of the data.

``can_access_*`` / ``can_manage_*``
    The object-level check, expressed as "is this row inside the queryset you
    were allowed to read". Fetching a row by id therefore answers exactly the
    same as listing it, which is why a guessed UUID gets a 404 rather than a
    record.

Imports of the domain apps are deliberately function-local: ``accounts`` sits
below ``schools`` and ``students`` in the dependency graph and has to stay
importable from them.
"""
from __future__ import annotations

from django.db import transaction
from django.db.models import Q, QuerySet

from .catalog import Perm, permissions_for
from .constants import (
    DEFAULT_STAFF_ROLE,
    PROVISIONABLE_ROLES,
    Role,
    manageable_roles,
    rank,
)


# --------------------------------------------------------------------------- #
# Roles held, and the role in use
# --------------------------------------------------------------------------- #
def is_developer(user) -> bool:
    """The platform owner, whatever hat they are currently wearing."""
    return bool(user and getattr(user, "is_authenticated", False) and user.is_developer)


def has_role(user, role: str) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False
    return user.has_role(role)


def has_any_role(user, *roles: str) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False
    return user.has_any_role(*roles)


def active_role(user) -> str:
    return getattr(user, "role", "") or ""


def has_permission(user, permission: str) -> bool:
    """Does the user's active role carry ``permission``?"""
    if not user or not getattr(user, "is_authenticated", False) or not user.is_active:
        return False
    return user.has_permission(permission)


def active_permissions(user) -> list[str]:
    if not user or not getattr(user, "is_authenticated", False):
        return []
    return sorted(permissions_for(user.role))


def _forget_cached_roles(user) -> None:
    """Drop a prefetched ``user_roles`` cache after the table has changed.

    List endpoints prefetch the roles to serialise a page in two queries. That
    cache is correct until something writes to the table — and then it is a
    stale answer that would make an audit entry claim a role was granted and
    never revoked. Cheap to drop, and only ever dropped on the write paths.
    """
    cache = getattr(user, "_prefetched_objects_cache", None)
    if cache:
        cache.pop("user_roles", None)


@transaction.atomic
def set_roles(user, roles, *, actor=None, keep_active: bool = True) -> list[str]:
    """Make ``roles`` the complete set of roles on ``user``.

    An account with nothing chosen for it becomes ``STAFF``: everybody who
    works at the school is at least an employee, and a role-less account is a
    person who can sign in and see nothing at all.

    The active role is repaired here too — pulling a role out from under
    somebody must not leave them working through one they no longer hold.
    """
    from .models import UserRole

    wanted = {str(role) for role in roles if role}
    if not wanted:
        wanted = {str(DEFAULT_STAFF_ROLE)}

    current = {row.role: row for row in UserRole.objects.filter(user=user)}
    for role in wanted - set(current):
        UserRole.objects.create(user=user, role=role, granted_by=actor)
    for role in set(current) - wanted:
        current[role].delete()
    _forget_cached_roles(user)

    if not keep_active or user.role not in wanted:
        user.role = _preferred_active(wanted)
        user.save(update_fields=["role", "updated_at"])
    return sorted(wanted, key=rank, reverse=True)


def _preferred_active(roles) -> str:
    """Which of several granted roles a session should open on.

    The most privileged one: somebody who is both an ADMIN and a TEACHER lands
    in the console, which is the screen they signed in for, and switches to the
    register when they want to teach.
    """
    return max(roles, key=rank) if roles else str(DEFAULT_STAFF_ROLE)


def grant_role(user, role: str, *, actor=None) -> bool:
    """Add one role. Returns True when it was not already there."""
    from .models import UserRole

    _, created = UserRole.objects.get_or_create(
        user=user, role=role, defaults={"granted_by": actor}
    )
    _forget_cached_roles(user)
    return created


def revoke_role(user, role: str) -> bool:
    """Remove one role, repairing the active one if it was the one removed."""
    from .models import UserRole

    deleted, _ = UserRole.objects.filter(user=user, role=role).delete()
    if not deleted:
        return False
    _forget_cached_roles(user)
    remaining = set(user.role_codes) - {role}
    if user.role == role:
        user.role = _preferred_active(remaining or {DEFAULT_STAFF_ROLE})
        user.save(update_fields=["role", "updated_at"])
    return True


def set_active_role(user, role: str) -> str:
    """Switch the working role, refusing anything the user does not hold.

    This is the check that makes the switcher safe: the browser sends a role
    name, and a name the account was never granted — ``DEVELOPER``, say — is
    refused here rather than trusted.
    """
    from apps.common.exceptions import PermissionError_

    if role not in user.role_codes:
        raise PermissionError_("Sizda bunday rol yo'q.")
    if user.role != role:
        user.role = role
        user.save(update_fields=["role", "updated_at"])
    return role


# --------------------------------------------------------------------------- #
# Which roles an operator may see and hand out
# --------------------------------------------------------------------------- #
def visible_roles(actor) -> tuple[str, ...]:
    """The roles ``actor`` is even allowed to know exist.

    DEVELOPER is absent for everybody else — it must not appear in a filter
    dropdown, a counter or a role list, because each of those would confirm
    that such an account exists.
    """
    if is_developer(actor):
        return PROVISIONABLE_ROLES
    return tuple(role for role in PROVISIONABLE_ROLES if role != Role.DEVELOPER)


def assignable_roles(actor) -> tuple[str, ...]:
    """The roles ``actor`` may grant to somebody else."""
    if not has_permission(actor, Perm.ROLES_ASSIGN):
        return ()
    return manageable_roles(active_role(actor))


def can_assign_role(actor, role: str) -> bool:
    return role in assignable_roles(actor)


# --------------------------------------------------------------------------- #
# Accounts
# --------------------------------------------------------------------------- #
def visible_users(actor) -> QuerySet:
    """Accounts ``actor`` may see at all.

    A DEVELOPER sees everybody, its own kind included — the platform has to be
    handable over. Everybody else sees every account that holds *no* DEVELOPER
    role: not filtered out of the list only, but genuinely absent, so a
    counter, a search and a fetch-by-id all agree that the account is not
    there.
    """
    from .models import User

    queryset = User.objects.all()
    if not is_developer(actor):
        queryset = queryset.exclude(
            Q(user_roles__role=Role.DEVELOPER) | Q(role=Role.DEVELOPER)
        )
    return queryset.distinct()


def can_see_user(actor, target) -> bool:
    if is_developer(actor):
        return True
    return not target.is_developer


def can_manage_user(actor, target) -> bool:
    """May ``actor`` edit, disable, re-password or delete ``target``?

    Never for their own account — disabling, deleting or re-passwording
    yourself from the console is refused. Editing yourself is a narrower
    question, answered by :func:`can_edit_self`. Nobody touches an account they
    cannot even see, and beyond that it is the ladder: every role the target
    holds must be one the actor may hand out.
    """
    if actor is None or target is None:
        return False
    if actor.pk == target.pk:
        return False
    if not can_see_user(actor, target):
        return False
    allowed = set(assignable_roles(actor))
    if not allowed:
        return False
    return set(target.role_codes).issubset(allowed)


def can_edit_self(actor) -> bool:
    """May ``actor`` change their own name, phone and lower roles in the console?

    Whoever may write accounts at all. The limits — no switching yourself off,
    no dropping your highest role, nothing above what you may hand out — are
    enforced by ``provisioning.update_staff_user``.
    """
    return actor is not None and has_permission(actor, Perm.USERS_MANAGE)


# --------------------------------------------------------------------------- #
# Schools, class groups, subjects
# --------------------------------------------------------------------------- #
def curator_group_ids(user) -> QuerySet:
    """The class groups this account was put in charge of, as a values-queryset."""
    from apps.schools.models import CuratorAssignment

    return CuratorAssignment.objects.filter(user=user).values_list(
        "class_group_id", flat=True
    )


def teacher_profile(user):
    return getattr(user, "teacher_profile", None)


def staff_profile(user):
    return getattr(user, "staff_profile", None)


def person_record(user):
    """The register row behind a cabinet account: a teacher, or a staff member.

    Both carry the same person fields and both pass the same turnstile, so
    everything about *their own day* — presence, chronology, the profile page —
    is written against whichever one exists.
    """
    return teacher_profile(user) or staff_profile(user)


def user_school_ids(user) -> set:
    """Schools this account belongs to, by whichever record it has."""
    ids = set()
    for profile in (teacher_profile(user), staff_profile(user), getattr(user, "guardian_profile", None)):
        if profile is not None:
            ids.add(profile.school_id)
    return ids


def accessible_class_groups(user) -> QuerySet:
    """Class groups the user may read.

    * admin roles — every group in the schools they administer;
    * TEACHER — the groups they carry a subject in, plus their homeroom;
    * CURATOR — the groups they were assigned;
    * everybody else — none. A parent reads their child through the child
      endpoints, not through the class register.
    """
    from apps.schools.models import ClassGroup
    from apps.schools.services.management import accessible_schools

    if not user or not getattr(user, "is_authenticated", False):
        return ClassGroup.objects.none()

    if has_permission(user, Perm.CLASSES_VIEW) and user.role in Role.admin_roles():
        return ClassGroup.objects.filter(school__in=accessible_schools(user))

    filters = Q(pk__in=[])
    teacher = teacher_profile(user)
    if user.role == Role.TEACHER and teacher is not None:
        filters |= Q(subjects__teachers=teacher) | Q(homeroom_teacher=teacher)
    if user.role == Role.CURATOR:
        filters |= Q(id__in=curator_group_ids(user))

    return ClassGroup.objects.filter(filters).distinct()


def can_access_group(user, class_group_id) -> bool:
    """Object-level check for one class group."""
    if class_group_id is None:
        return False
    return accessible_class_groups(user).filter(pk=class_group_id).exists()


def get_accessible_group(user, class_group_id):
    return (
        accessible_class_groups(user)
        .select_related("grade", "school")
        .filter(pk=class_group_id)
        .first()
    )


# --------------------------------------------------------------------------- #
# People
# --------------------------------------------------------------------------- #
def accessible_students(user) -> QuerySet:
    """Delegates to the pupil scope, which is the same rule everywhere."""
    from apps.guardians.selectors import accessible_students as _students

    return _students(user)


def can_access_student(user, student_id) -> bool:
    from apps.guardians.selectors import get_accessible_student

    return get_accessible_student(user, student_id) is not None


def can_access_child(user, student_id) -> bool:
    """A parent's own verified children — nothing else, ever."""
    from apps.guardians.selectors import children_links

    if not has_permission(user, Perm.CHILDREN_VIEW):
        return False
    return children_links(user).filter(student_id=student_id).exists()


def accessible_staff(user) -> QuerySet:
    """Staff rows the user may read.

    An ordinary STAFF account sees exactly one row: its own. That is the whole
    of their register — asking for a colleague's id returns nothing, because
    the colleague is not in the queryset to begin with.
    """
    from apps.schools.models import StaffMember
    from apps.schools.services.management import accessible_schools

    if not user or not getattr(user, "is_authenticated", False):
        return StaffMember.objects.none()

    if has_permission(user, Perm.STAFF_VIEW):
        return StaffMember.objects.filter(school__in=accessible_schools(user))

    own = staff_profile(user)
    if own is not None:
        return StaffMember.objects.filter(pk=own.pk)
    return StaffMember.objects.none()


def can_access_staff(user, staff_id) -> bool:
    return accessible_staff(user).filter(pk=staff_id).exists()


def accessible_teachers(user) -> QuerySet:
    from apps.schools.models import Teacher
    from apps.schools.services.management import accessible_schools

    if not user or not getattr(user, "is_authenticated", False):
        return Teacher.objects.none()
    if has_permission(user, Perm.TEACHERS_VIEW):
        return Teacher.objects.filter(school__in=accessible_schools(user))
    own = teacher_profile(user)
    if own is not None:
        return Teacher.objects.filter(pk=own.pk)
    return Teacher.objects.none()


# --------------------------------------------------------------------------- #
# What the browser is told about itself
# --------------------------------------------------------------------------- #
def session_scope(user) -> dict:
    """The ids and names the cabinet needs to draw the signed-in person's world.

    Only what the active role actually uses: a TEACHER gets their subjects and
    groups, a CURATOR their groups, a parent their children. Nothing sensitive
    travels — ids and display names, the same strings the pages already show.
    The server re-checks every one of them on the endpoints behind these
    screens, so this is convenience, never authority.
    """
    scope: dict = {
        "teacher_subjects": [],
        "teacher_groups": [],
        "curator_groups": [],
        "children": [],
    }
    if not user or not getattr(user, "is_authenticated", False):
        return scope

    role = user.role

    if role == Role.TEACHER:
        teacher = teacher_profile(user)
        if teacher is not None:
            subjects = (
                teacher.subjects.filter(deleted_at__isnull=True)
                .select_related("class_group", "class_group__grade")
                .order_by("class_group__grade__level", "class_group__name", "name")
            )
            groups = {}
            for subject in subjects:
                scope["teacher_subjects"].append(
                    {
                        "id": str(subject.id),
                        "name": subject.name,
                        "display_name": subject.display_name,
                        "class_group": (
                            subject.class_group.display_name
                            if subject.class_group_id
                            else ""
                        ),
                        "class_group_id": (
                            str(subject.class_group_id) if subject.class_group_id else None
                        ),
                    }
                )
                if subject.class_group_id:
                    groups[subject.class_group_id] = subject.class_group
            scope["teacher_groups"] = [
                {"id": str(group.id), "display_name": group.display_name}
                for group in sorted(
                    groups.values(), key=lambda row: (row.grade.level, row.name)
                )
            ]

    if role == Role.CURATOR:
        from apps.schools.models import ClassGroup

        groups = (
            ClassGroup.objects.filter(id__in=curator_group_ids(user))
            .select_related("grade")
            .order_by("grade__level", "name")
        )
        scope["curator_groups"] = [
            {"id": str(group.id), "display_name": group.display_name} for group in groups
        ]

    if role == Role.PARENT:
        from apps.guardians.selectors import children_links

        scope["children"] = [
            {
                "id": str(link.student_id),
                "full_name": link.student.full_name,
                "class_group": link.student.class_group.display_name,
            }
            for link in children_links(user)
        ]

    return scope
