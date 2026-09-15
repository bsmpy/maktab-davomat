"""Kuratorlar — who watches which class.

A curator is an employee put in front of a class group: "Ali Valiyev → 7-A".
That single row is their whole cabinet — the group, its pupils, their
attendance and nothing else — so this section is deliberately small: pick a
person, pick a group, and the role follows.

Two things happen together on purpose, because doing one without the other
leaves somebody in a half-state nobody asked for:

* assigning a group **grants the CURATOR role**, so the person can actually
  open the cabinet the assignment was made for;
* removing their **last** group **takes the role away** again, because a
  curator of nothing is an account that signs in to an empty screen.
"""
from __future__ import annotations

from django.db import transaction
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers, status
from rest_framework.response import Response

from apps.accounts import rbac
from apps.accounts.audit import log_curator_change
from apps.accounts.catalog import Perm
from apps.accounts.constants import Role
from apps.accounts.models import User
from apps.audit.constants import AuditAction
from apps.common.exceptions import ConflictError, NotFoundError

from .management_views import SCHOOL_PARAM, ManagementView
from .models import ClassGroup, CuratorAssignment


class CuratorAssignmentSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    user = serializers.IntegerField(read_only=True, source="user_id")
    username = serializers.CharField(read_only=True, source="user.username")
    full_name = serializers.CharField(read_only=True, source="user.full_name")
    phone = serializers.CharField(read_only=True, source="user.phone", default="")
    class_group = serializers.UUIDField(read_only=True, source="class_group_id")
    class_group_name = serializers.CharField(
        read_only=True, source="class_group.display_name"
    )
    grade_level = serializers.IntegerField(
        read_only=True, source="class_group.grade.level"
    )
    students_count = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField(read_only=True)
    #: Куратор — это учитель или сотрудник; карточка открывает его профиль.
    teacher_id = serializers.SerializerMethodField()
    staff_id = serializers.SerializerMethodField()
    photo = serializers.SerializerMethodField()
    roles = serializers.ListField(
        child=serializers.CharField(), read_only=True, source="user.role_codes"
    )

    def get_students_count(self, row) -> int:
        return self.context.get("sizes", {}).get(row.class_group_id, 0)

    def get_teacher_id(self, row) -> str | None:
        profile = getattr(row.user, "teacher_profile", None)
        return str(profile.id) if profile is not None else None

    def get_staff_id(self, row) -> str | None:
        profile = getattr(row.user, "staff_profile", None)
        return str(profile.id) if profile is not None else None

    def get_photo(self, row) -> str | None:
        from apps.common.media import absolute_media_url

        for attribute in ("teacher_profile", "staff_profile"):
            profile = getattr(row.user, attribute, None)
            if profile is not None and profile.photo:
                return absolute_media_url(profile.photo)
        return None


class CuratorWriteSerializer(serializers.Serializer):
    """One assignment. ``user`` is a cabinet account, not a staff register row."""

    user = serializers.IntegerField()
    class_group = serializers.UUIDField()


class CuratorPatchSerializer(serializers.Serializer):
    class_group = serializers.UUIDField()


def _group_sizes(group_ids) -> dict:
    from django.db.models import Count

    from apps.students.models import Student

    return dict(
        Student.objects.active()
        .filter(class_group_id__in=list(group_ids))
        .values_list("class_group_id")
        .annotate(total=Count("id"))
    )


class CuratorSectionView(ManagementView):
    """Shared scope: the groups and the people this caller may work with."""

    read_permission = Perm.CURATORS_VIEW
    write_permission = Perm.CURATORS_MANAGE

    def assignments(self, request):
        return (
            CuratorAssignment.objects.filter(
                class_group__school_id__in=self.school_ids(request)
            )
            .select_related(
                "user", "user__teacher_profile", "user__staff_profile",
                "class_group", "class_group__grade",
            )
            .prefetch_related("user__user_roles")
            .order_by("class_group__grade__level", "class_group__name", "user__last_name")
        )

    def resolve_group(self, request, group_id) -> ClassGroup:
        group = (
            ClassGroup.objects.filter(
                pk=group_id, school_id__in=self.school_ids(request)
            )
            .select_related("grade")
            .first()
        )
        if group is None:
            raise NotFoundError("Sinf guruhi topilmadi.", code="CLASS_GROUP_NOT_FOUND")
        return group

    def resolve_user(self, request, user_id) -> User:
        """The account being made a curator.

        It has to be somebody the caller can see and manage: a SUPER_ADMIN
        cannot reach into a DEVELOPER account through this screen any more than
        through Foydalanuvchilar.
        """
        target = rbac.visible_users(request.user).filter(pk=user_id).first()
        if target is None:
            raise NotFoundError("Foydalanuvchi topilmadi.", code="USER_NOT_FOUND")
        if not rbac.can_assign_role(request.user, Role.CURATOR):
            raise ConflictError(
                "CURATOR rolini berishga ruxsatingiz yo'q.", code="ROLE_FORBIDDEN"
            )
        return target


@extend_schema(tags=["management"], parameters=[SCHOOL_PARAM])
class CuratorListView(CuratorSectionView):
    """Every curator link, plus what the form needs to make another one."""

    @extend_schema(
        responses={200: CuratorAssignmentSerializer(many=True)},
        summary="Kuratorlar",
    )
    def get(self, request):
        rows = list(self.assignments(request))
        sizes = _group_sizes({row.class_group_id for row in rows})

        school_ids = list(self.school_ids(request))
        groups = (
            ClassGroup.objects.filter(school_id__in=school_ids, is_active=True)
            .select_related("grade")
            .order_by("grade__level", "name")
        )
        # Who can be made a curator: an active account that holds at least one
        # job at the school. A parent account is not on the list — being a
        # parent is not a job — but a teacher who is *also* a parent is, which
        # is why this asks for a staff role rather than excluding OTA-ONA.
        candidates = (
            rbac.visible_users(request.user)
            .filter(is_active=True, user_roles__role__in=Role.staff_assignable_roles())
            .prefetch_related("user_roles")
            .distinct()
            .order_by("last_name", "first_name")
        )

        return Response(
            {
                "results": CuratorAssignmentSerializer(
                    rows, many=True, context={"sizes": sizes}
                ).data,
                "class_groups": [
                    {
                        "id": str(group.id),
                        "display_name": group.display_name,
                        "grade_level": group.grade.level,
                        "students_count": sizes.get(group.id, 0),
                    }
                    for group in groups
                ],
                "candidates": [
                    {
                        "id": person.id,
                        "username": person.username,
                        "full_name": person.full_name,
                        "roles": person.role_codes,
                    }
                    for person in candidates
                ],
            }
        )

    @extend_schema(
        request=CuratorWriteSerializer,
        responses={201: CuratorAssignmentSerializer},
        summary="Kurator biriktirish",
    )
    def post(self, request):
        serializer = CuratorWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        target = self.resolve_user(request, data["user"])
        group = self.resolve_group(request, data["class_group"])

        with transaction.atomic():
            row, created = CuratorAssignment.objects.get_or_create(
                user=target, class_group=group, defaults={"assigned_by": request.user}
            )
            if not created:
                raise ConflictError(
                    f"{target.full_name} allaqachon {group.display_name} kuratori.",
                    code="CURATOR_EXISTS",
                )
            # The role is what makes the assignment usable; granting it here
            # means nobody has to remember to do it in a second screen.
            rbac.grant_role(target, Role.CURATOR, actor=request.user)

        log_curator_change(
            AuditAction.CURATOR_ASSIGNED,
            actor=request.user,
            target=target,
            class_group=group,
            request=request,
        )
        return Response(
            CuratorAssignmentSerializer(
                row, context={"sizes": _group_sizes([group.id])}
            ).data,
            status=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["management"])
class CuratorDetailView(CuratorSectionView):
    def get_object(self, request, pk) -> CuratorAssignment:
        row = self.assignments(request).filter(pk=pk).first()
        if row is None:
            raise NotFoundError("Biriktiruv topilmadi.", code="CURATOR_NOT_FOUND")
        return row

    @extend_schema(
        request=CuratorPatchSerializer,
        responses={200: CuratorAssignmentSerializer},
        summary="Kurator guruhini o'zgartirish",
    )
    def patch(self, request, pk):
        row = self.get_object(request, pk)
        serializer = CuratorPatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        group = self.resolve_group(request, serializer.validated_data["class_group"])
        if group.id != row.class_group_id:
            clash = CuratorAssignment.objects.filter(
                user_id=row.user_id, class_group=group
            ).exists()
            if clash:
                raise ConflictError(
                    f"Bu xodim allaqachon {group.display_name} kuratori.",
                    code="CURATOR_EXISTS",
                )
            previous = row.class_group
            row.class_group = group
            row.save(update_fields=["class_group", "updated_at"])
            log_curator_change(
                AuditAction.CURATOR_REMOVED,
                actor=request.user,
                target=row.user,
                class_group=previous,
                request=request,
            )
            log_curator_change(
                AuditAction.CURATOR_ASSIGNED,
                actor=request.user,
                target=row.user,
                class_group=group,
                request=request,
            )
        return Response(
            CuratorAssignmentSerializer(
                row, context={"sizes": _group_sizes([row.class_group_id])}
            ).data
        )

    @extend_schema(
        responses={200: OpenApiResponse(description="Biriktiruv olib tashlandi")},
        summary="Biriktiruvni olib tashlash",
    )
    def delete(self, request, pk):
        row = self.get_object(request, pk)
        target, group = row.user, row.class_group

        with transaction.atomic():
            row.delete()
            # Their last group: the role has nothing left to point at, so it
            # goes too rather than leaving an account that opens on nothing.
            revoked = False
            if not CuratorAssignment.objects.filter(user=target).exists():
                revoked = rbac.revoke_role(target, Role.CURATOR)

        log_curator_change(
            AuditAction.CURATOR_REMOVED,
            actor=request.user,
            target=target,
            class_group=group,
            request=request,
        )
        return Response(
            {
                "deleted": True,
                "role_revoked": revoked,
                "curator": target.full_name,
                "class_group": group.display_name,
            }
        )
