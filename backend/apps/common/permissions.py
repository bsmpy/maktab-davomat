"""Role-aware DRF permissions.

Every class here is a thin reading of :mod:`apps.accounts.rbac` — the rules
themselves live there, so an endpoint and the queryset behind it can never
disagree about who is allowed in.

Object-level access is *always* re-checked on the server; the frontend role is
presentation only.
"""
from __future__ import annotations

from rest_framework.permissions import SAFE_METHODS, BasePermission

from apps.accounts import rbac
from apps.accounts.catalog import Perm
from apps.accounts.constants import Role


class IsAuthenticatedActive(BasePermission):
    message = "Autentifikatsiya talab qilinadi."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_active)


class HasRole(IsAuthenticatedActive):
    """Set ``required_roles`` on the view (or subclass and set ``roles``).

    Matches on the **active** role: somebody who holds ADMIN but is working as
    a TEACHER is a teacher here, which is the whole point of the switcher.
    """

    roles: tuple[str, ...] = ()

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        allowed = tuple(getattr(view, "required_roles", ()) or self.roles)
        if not allowed:
            return True
        return request.user.role in allowed


class HasPermission(IsAuthenticatedActive):
    """The workhorse: an endpoint names a permission, not a list of roles.

    Views declare what reading and writing each cost::

        class ManagedStudentListView(ManagementView):
            read_permission = Perm.STUDENTS_VIEW
            write_permission = Perm.STUDENTS_MANAGE

    A role that holds the read permission and not the write one — MODERATOR
    everywhere, TEACHER on the register — gets its GETs and a 403 on anything
    else, without a single ``if role ==`` in the view body.
    """

    #: Fallbacks for subclasses that are about exactly one permission.
    read_permission: str | None = None
    write_permission: str | None = None
    #: Checked before either of the above, when set. It is how a whole section
    #: is gated on top of its per-area permissions: the admin console asks for
    #: ``register.access`` first, so holding ``classes.view`` for your own
    #: classes does not open Boshqaruv.
    base_permission: str | None = None
    message = "Bu amal uchun ruxsatingiz yo'q."

    def _required(self, request, view) -> str | None:
        if request.method in SAFE_METHODS:
            return getattr(view, "read_permission", None) or self.read_permission
        return (
            getattr(view, "write_permission", None)
            or self.write_permission
            # An endpoint that names only its read permission is read-only by
            # omission rather than accidentally open to writes.
            or getattr(view, "read_permission", None)
            or self.read_permission
        )

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        base = getattr(view, "base_permission", None) or self.base_permission
        if base is not None and not rbac.has_permission(request.user, base):
            return False
        required = self._required(request, view)
        if required is None:
            return True
        return rbac.has_permission(request.user, required)


def permission_required(permission: str, write_permission: str | None = None):
    """A one-off ``HasPermission`` subclass, for views with nothing to subclass."""
    return type(
        "RequiresPermission",
        (HasPermission,),
        {"read_permission": permission, "write_permission": write_permission or permission},
    )


class IsParent(HasRole):
    roles = (Role.PARENT,)
    message = "Bu bo'lim faqat ota-onalar uchun."


class IsTeacher(HasPermission):
    """The lesson register: whoever may read it, and whoever may mark it."""

    read_permission = Perm.ATTENDANCE_VIEW
    write_permission = Perm.ATTENDANCE_MARK
    message = "Bu bo'lim faqat o'qituvchilar uchun."


class CanMarkAttendance(HasPermission):
    read_permission = Perm.ATTENDANCE_MARK
    write_permission = Perm.ATTENDANCE_MARK
    message = "Davomat qo'yish uchun ruxsatingiz yo'q."


class IsSchoolAdmin(HasPermission):
    """The admin console: readable by the observing roles, writable by the running ones.

    ``register.access`` is the door and the per-area permission is the room —
    both are required, which is what keeps a teacher's ``classes.view`` (their
    own classes, on their own pages) from opening the school's register.
    """

    base_permission = Perm.REGISTER_ACCESS
    read_permission = Perm.SCHOOL_VIEW
    write_permission = Perm.SCHOOL_MANAGE
    message = "Bu bo'lim faqat administratorlar uchun."


class IsSuperAdmin(HasRole):
    roles = (Role.DEVELOPER, Role.SUPER_ADMIN)
    message = "Bu amal uchun ruxsat yo'q."


class CanOpenSettings(HasPermission):
    read_permission = Perm.SETTINGS_VIEW
    message = "Sozlamalar bo'limiga ruxsatingiz yo'q."


class CanReadIntegrations(HasPermission):
    """Reading integration config exposes masked credentials and device hosts."""

    read_permission = Perm.INTEGRATIONS_VIEW
    write_permission = Perm.INTEGRATIONS_MANAGE
    message = "Integratsiyalarni ko'rish uchun ruxsatingiz yo'q."


class IsDeveloper(IsAuthenticatedActive):
    """Full, unscoped access — the only role allowed to change credentials."""

    message = "Bu amal faqat dasturchi uchun."

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        return rbac.is_developer(request.user)


class CanManageUsers(HasPermission):
    """Who may open Foydalanuvchilar and provision accounts.

    Which *roles* each may touch is decided per-write by
    ``apps.accounts.rbac.assignable_roles``, and which *accounts* they can even
    see by ``visible_users`` — a SUPER_ADMIN never meets a DEVELOPER row.
    """

    read_permission = Perm.USERS_VIEW
    write_permission = Perm.USERS_MANAGE
    message = "Foydalanuvchilarni boshqarish uchun ruxsatingiz yo'q."


class CanViewAudit(HasPermission):
    read_permission = Perm.AUDIT_VIEW
    message = "Audit jurnaliga ruxsatingiz yo'q."
