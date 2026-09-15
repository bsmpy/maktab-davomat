"""Object-level guard for every pupil-scoped endpoint."""
from __future__ import annotations

from rest_framework.permissions import BasePermission

from apps.accounts.catalog import Perm
from apps.common.exceptions import NotFoundError
from apps.guardians.selectors import get_accessible_student


class CanAccessStudent(BasePermission):
    """Backs the ``StudentScopedMixin``; access is decided per object, never per role alone.

    Every endpoint behind it is a pupil's attendance, so seeing the pupil in the
    register is not enough: the active role must read attendance too — a parent
    their own children's, staff through ``attendance.view``. An ADMIN lists
    pupils but never opens their days.
    """

    message = "Bu o'quvchi ma'lumotlariga ruxsatingiz yo'q."

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        return user.has_permission(Perm.CHILDREN_VIEW) or user.has_permission(
            Perm.ATTENDANCE_VIEW
        )


class StudentScopedMixin:
    """Resolves ``student_id`` from the URL against what the user may read.

    A parent passing someone else's id gets a 404 — identical to a genuinely
    missing pupil, so the endpoint leaks no existence information.
    """

    permission_classes = [CanAccessStudent]

    def get_student(self):
        student = get_accessible_student(self.request.user, self.kwargs["student_id"])
        if student is None:
            raise NotFoundError("O'quvchi topilmadi.", code="STUDENT_NOT_FOUND")
        return student
