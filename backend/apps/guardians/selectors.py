"""Who may see which pupil.

Every attendance endpoint resolves its target through here, so object-level
access is enforced in exactly one place and can never be bypassed by passing a
different ``student_id`` from the frontend.
"""
from __future__ import annotations

from django.db.models import Q, QuerySet

from apps.accounts.catalog import Perm
from apps.accounts.constants import Role
from apps.students.models import Student

from .models import GuardianStudent


def children_links(user) -> QuerySet[GuardianStudent]:
    """Verified guardian↔student links for a parent account."""
    guardian = getattr(user, "guardian_profile", None)
    if guardian is None:
        return GuardianStudent.objects.none()
    return (
        GuardianStudent.objects.filter(guardian=guardian, verified=True)
        .select_related(
            "student",
            "student__class_group",
            "student__class_group__grade",
            "student__school",
        )
        .filter(student__deleted_at__isnull=True, student__is_active=True)
        .order_by("-is_primary", "student__last_name", "student__first_name")
    )


def accessible_students(user) -> QuerySet[Student]:
    """Pupils the user is allowed to read, by their **active** role.

    The list is the same object-level rule the detail endpoints use, so a role
    that cannot list a pupil cannot open one either.
    """
    if not user or not user.is_authenticated:
        return Student.objects.none()

    role = user.role

    # DEVELOPER, SUPER_ADMIN and MODERATOR are never scoped to a school.
    if role in Role.unrestricted_roles():
        return Student.objects.active().with_class()

    if role == Role.ADMIN:
        # Admins are scoped to the schools they have a profile record in.
        from apps.accounts.rbac import user_school_ids

        school_ids = user_school_ids(user)
        if not school_ids:
            return Student.objects.active().with_class()
        return Student.objects.active().with_class().filter(school_id__in=school_ids)

    if role == Role.TEACHER:
        teacher = getattr(user, "teacher_profile", None)
        if teacher is None:
            return Student.objects.none()
        # Their homeroom classes, every class they are timetabled for, and
        # every class one of their subjects belongs to. ``Q`` rather than
        # ``union`` so the result stays filterable.
        return (
            Student.objects.active()
            .with_class()
            .filter(
                Q(class_group__in=teacher.schedules.values("class_group"))
                | Q(class_group__in=teacher.subjects.values("class_group"))
                | Q(class_group__homeroom_teacher=teacher)
            )
            .distinct()
        )

    if role == Role.CURATOR:
        # Exactly the groups they were put in charge of. Nothing about the rest
        # of the school reaches a curator.
        from apps.accounts.rbac import curator_group_ids

        return (
            Student.objects.active()
            .with_class()
            .filter(class_group_id__in=curator_group_ids(user))
        )

    if role == Role.PARENT:
        return Student.objects.active().with_class().filter(
            id__in=children_links(user).values("student_id")
        )

    # STAFF and anything else: their cabinet is about themselves.
    if user.has_permission(Perm.STUDENTS_VIEW):  # pragma: no cover - defensive
        return Student.objects.active().with_class()
    return Student.objects.none()


def get_accessible_student(user, student_id) -> Student | None:
    """Single-pupil lookup honouring the same rules as ``accessible_students``."""
    if not user or not user.is_authenticated:
        return None
    if user.role == Role.PARENT:
        link = children_links(user).filter(student_id=student_id).first()
        return link.student if link else None
    return accessible_students(user).filter(pk=student_id).first()
