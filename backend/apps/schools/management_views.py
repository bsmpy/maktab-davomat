"""Management API for the ADMIN cabinet.

Everything an administrator needs to run the register: create and retire whole
parallels (``11-sinf``), create and retire class groups (``3-G``, ``6-A``), and
add pupils together with their guardians and their face photo — which is pushed
to the access terminals in the same operation, so a pupil added in the morning
can pass the turnstile the same day.

Access is ``IsSchoolAdmin`` throughout, and every write resolves its school
through :func:`apps.schools.services.management.resolve_school`, so an ADMIN
scoped to one school cannot reach another one's register.
"""
from __future__ import annotations

import logging

from django.db import transaction
from django.db.models import Count, Prefetch, Q
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.accounts.catalog import Perm
from apps.accounts.constants import Role
from apps.accounts.models import User
from apps.accounts.services.provisioning import (
    assert_may_manage_user,
    create_staff_user,
    issue_temporary_password,
    update_staff_user,
)
from apps.audit.constants import AuditAction
from apps.audit.services import log_action
from apps.common.exceptions import ConflictError, NotFoundError
from apps.common.media import absolute_media_url
from apps.common.pagination import DefaultPagination
from apps.common.permissions import CanManageUsers, IsSchoolAdmin
from apps.guardians.constants import Relation
from apps.guardians.models import Guardian, GuardianStudent
from apps.students.models import Student

from .management_serializers import (
    ClassGroupPatchSerializer,
    ClassGroupWriteSerializer,
    GradeWriteSerializer,
    ManagedClassGroupSerializer,
    ManagedGradeSerializer,
    ManagedGuardianRowSerializer,
    ManagedStudentSerializer,
    StaffUserPatchSerializer,
    StaffUserSerializer,
    StaffUserWriteSerializer,
    StudentPatchSerializer,
    StudentPhotoSerializer,
    StudentWriteSerializer,
)
from .models import ClassGroup, Grade
from .services.management import (
    accessible_schools,
    create_class_group,
    create_grade,
    delete_class_group,
    delete_grade,
    resolve_school,
    retire_student,
)

logger = logging.getLogger(__name__)

SCHOOL_PARAM = OpenApiParameter("school", str, description="Maktab id (ixtiyoriy)")


class ManagementView(APIView):
    """Base: admin-only, and scoped to the schools the caller may manage."""

    permission_classes = [IsSchoolAdmin]

    def school(self, request):
        return resolve_school(request.user, request.query_params.get("school"))

    def school_for_write(self, request, data: dict):
        return resolve_school(request.user, data.get("school"))

    def school_ids(self, request):
        return accessible_schools(request.user).values_list("id", flat=True)


# --------------------------------------------------------------------------- #
# Grades — the 1..11 parallels
# --------------------------------------------------------------------------- #
@extend_schema(tags=["management"], parameters=[SCHOOL_PARAM])
class ManagedGradeListView(ManagementView):
    read_permission = Perm.CLASSES_VIEW
    write_permission = Perm.CLASSES_MANAGE

    @extend_schema(responses={200: ManagedGradeSerializer(many=True)}, summary="Sinflar")
    def get(self, request):
        grades = (
            Grade.objects.filter(school_id__in=self.school_ids(request))
            .annotate(
                class_groups_count=Count(
                    "class_groups",
                    filter=Q(class_groups__deleted_at__isnull=True),
                    distinct=True,
                ),
                students_count=Count(
                    "class_groups__students",
                    filter=Q(
                        class_groups__deleted_at__isnull=True,
                        class_groups__students__deleted_at__isnull=True,
                    ),
                    distinct=True,
                ),
            )
            .order_by("level")
        )
        return Response(
            {
                "results": [
                    {
                        "id": str(grade.id),
                        "level": grade.level,
                        "label": grade.label,
                        "class_groups_count": grade.class_groups_count,
                        "students_count": grade.students_count,
                    }
                    for grade in grades
                ]
            }
        )

    @extend_schema(
        request=GradeWriteSerializer,
        responses={201: ManagedGradeSerializer},
        summary="Sinf qo'shish",
    )
    def post(self, request):
        serializer = GradeWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        school = self.school_for_write(request, data)
        grade = create_grade(school=school, level=data["level"])
        log_action(
            AuditAction.SCHOOL_STRUCTURE_CHANGE,
            user=request.user,
            entity=grade,
            request=request,
            new_data={"level": grade.level, "school": str(school.id)},
        )
        return Response(
            {
                "id": str(grade.id),
                "level": grade.level,
                "label": grade.label,
                "class_groups_count": 0,
                "students_count": 0,
            },
            status=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["management"])
class ManagedGradeDetailView(ManagementView):
    read_permission = Perm.CLASSES_VIEW
    write_permission = Perm.CLASSES_MANAGE

    def get_object(self, request, pk) -> Grade:
        grade = Grade.objects.filter(
            pk=pk, school_id__in=self.school_ids(request)
        ).first()
        if grade is None:
            raise NotFoundError("Sinf topilmadi.", code="GRADE_NOT_FOUND")
        return grade

    @extend_schema(
        responses={200: OpenApiResponse(description="O'chirilgan sinf tafsiloti")},
        summary="Sinfni butunlay o'chirish",
    )
    def delete(self, request, pk):
        grade = self.get_object(request, pk)
        summary = delete_grade(grade)
        log_action(
            AuditAction.SCHOOL_STRUCTURE_CHANGE,
            user=request.user,
            entity_type=Grade._meta.label,
            entity_id=str(pk),
            request=request,
            old_data=summary,
            metadata={"operation": "delete_grade"},
        )
        return Response({"deleted": True, **summary})


# --------------------------------------------------------------------------- #
# Class groups — 3-G, 6-A, …
# --------------------------------------------------------------------------- #
@extend_schema(tags=["management"], parameters=[SCHOOL_PARAM])
class ManagedClassGroupListView(ManagementView):
    read_permission = Perm.CLASSES_VIEW
    write_permission = Perm.CLASSES_MANAGE

    @extend_schema(
        responses={200: ManagedClassGroupSerializer(many=True)}, summary="Sinf guruhlari"
    )
    def get(self, request):
        groups = (
            ClassGroup.objects.filter(school_id__in=self.school_ids(request))
            .select_related("grade")
            .annotate(
                students_count=Count(
                    "students", filter=Q(students__deleted_at__isnull=True), distinct=True
                )
            )
            .order_by("grade__level", "name")
        )
        if request.query_params.get("grade"):
            groups = groups.filter(grade_id=request.query_params["grade"])
        return Response(
            {
                "results": [
                    {
                        "id": str(group.id),
                        "name": group.name,
                        "display_name": group.display_name,
                        "room": group.room,
                        "grade_id": str(group.grade_id),
                        "grade_level": group.grade.level,
                        "students_count": group.students_count,
                    }
                    for group in groups
                ]
            }
        )

    @extend_schema(
        request=ClassGroupWriteSerializer,
        responses={201: ManagedClassGroupSerializer},
        summary="Guruh qo'shish",
    )
    def post(self, request):
        serializer = ClassGroupWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        school = self.school_for_write(request, data)
        grade = self._resolve_grade(school, data)
        group = create_class_group(
            school=school, grade=grade, name=data["name"], room=data.get("room", "")
        )
        log_action(
            AuditAction.SCHOOL_STRUCTURE_CHANGE,
            user=request.user,
            entity=group,
            request=request,
            new_data={"class_group": group.display_name},
        )
        return Response(
            {
                "id": str(group.id),
                "name": group.name,
                "display_name": group.display_name,
                "room": group.room,
                "grade_id": str(group.grade_id),
                "grade_level": grade.level,
                "students_count": 0,
            },
            status=status.HTTP_201_CREATED,
        )

    def _resolve_grade(self, school, data) -> Grade:
        if data.get("grade"):
            grade = Grade.objects.filter(pk=data["grade"], school=school).first()
            if grade is None:
                raise NotFoundError("Sinf topilmadi.", code="GRADE_NOT_FOUND")
            return grade
        # Creating "3-G" while grade 3 does not exist yet simply creates it too.
        existing = Grade.objects.filter(school=school, level=data["level"]).first()
        return existing or create_grade(school=school, level=data["level"])


@extend_schema(tags=["management"])
class ManagedClassGroupDetailView(ManagementView):
    read_permission = Perm.CLASSES_VIEW
    write_permission = Perm.CLASSES_MANAGE

    def get_object(self, request, pk) -> ClassGroup:
        group = (
            ClassGroup.objects.select_related("grade")
            .filter(pk=pk, school_id__in=self.school_ids(request))
            .first()
        )
        if group is None:
            raise NotFoundError("Guruh topilmadi.", code="CLASS_GROUP_NOT_FOUND")
        return group

    @extend_schema(
        request=ClassGroupPatchSerializer,
        responses={200: ManagedClassGroupSerializer},
        summary="Guruhni tahrirlash",
    )
    def patch(self, request, pk):
        group = self.get_object(request, pk)
        serializer = ClassGroupPatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        old = group.display_name
        if data.get("name"):
            clash = (
                ClassGroup.objects.filter(
                    grade=group.grade,
                    academic_year=group.academic_year,
                    name__iexact=data["name"],
                )
                .exclude(pk=group.pk)
                .exists()
            )
            if clash:
                raise ConflictError(
                    f"{group.grade.level}-{data['name']} allaqachon mavjud.",
                    code="CLASS_GROUP_EXISTS",
                )
            group.name = data["name"]
        if "room" in data:
            group.room = data["room"]
        group.save(update_fields=["name", "room", "updated_at"])

        log_action(
            AuditAction.SCHOOL_STRUCTURE_CHANGE,
            user=request.user,
            entity=group,
            request=request,
            old_data={"class_group": old},
            new_data={"class_group": group.display_name},
        )
        return Response(
            {
                "id": str(group.id),
                "name": group.name,
                "display_name": group.display_name,
                "room": group.room,
                "grade_id": str(group.grade_id),
                "grade_level": group.grade.level,
                "students_count": group.students.count(),
            }
        )

    @extend_schema(
        responses={200: OpenApiResponse(description="O'chirilgan guruh tafsiloti")},
        summary="Guruhni o'chirish",
    )
    def delete(self, request, pk):
        group = self.get_object(request, pk)
        summary = delete_class_group(group)
        log_action(
            AuditAction.SCHOOL_STRUCTURE_CHANGE,
            user=request.user,
            entity_type=ClassGroup._meta.label,
            entity_id=str(pk),
            request=request,
            old_data=summary,
            metadata={"operation": "delete_class_group"},
        )
        return Response({"deleted": True, **summary})


# --------------------------------------------------------------------------- #
# Students
# --------------------------------------------------------------------------- #
def _student_queryset(school_ids):
    return (
        Student.objects.filter(school_id__in=school_ids)
        .select_related("class_group", "class_group__grade", "school", "terminal_person")
        .prefetch_related(
            Prefetch(
                "guardian_links",
                queryset=GuardianStudent.objects.select_related("guardian").order_by(
                    "-is_primary"
                ),
            )
        )
        .order_by("class_group__grade__level", "class_group__name", "last_name", "first_name")
    )


@extend_schema(tags=["management"], parameters=[SCHOOL_PARAM])
class ManagedStudentListView(ManagementView):
    read_permission = Perm.STUDENTS_VIEW
    write_permission = Perm.STUDENTS_MANAGE

    @extend_schema(
        parameters=[
            OpenApiParameter("class_group", str, description="Guruh id"),
            OpenApiParameter("q", str, description="Ism bo'yicha qidiruv"),
            OpenApiParameter(
                "registered",
                str,
                description="yes — yaqini ro'yxatdan o'tgan, no — hali o'tmagan",
            ),
        ],
        responses={200: ManagedStudentSerializer(many=True)},
        summary="O'quvchilar ro'yxati",
    )
    def get(self, request):
        queryset = _student_queryset(self.school_ids(request))
        if request.query_params.get("class_group"):
            queryset = queryset.filter(class_group_id=request.query_params["class_group"])
        query = (request.query_params.get("q") or "").strip()
        if query:
            from apps.common.text import transliterate

            queryset = queryset.filter(search_name__icontains=transliterate(query))

        registered = (request.query_params.get("registered") or "").lower()
        if registered in ("yes", "true", "1"):
            queryset = queryset.filter(guardian_links__guardian__user__isnull=False).distinct()
        elif registered in ("no", "false", "0"):
            queryset = queryset.exclude(guardian_links__guardian__user__isnull=False)

        paginator = DefaultPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        return paginator.get_paginated_response(
            ManagedStudentSerializer(page, many=True).data
        )

    @extend_schema(
        request=StudentWriteSerializer,
        responses={201: ManagedStudentSerializer},
        summary="O'quvchi qo'shish",
    )
    def post(self, request):
        serializer = StudentWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        group = self._resolve_group(request, data["class_group"])
        student = _create_student(data, group=group, user=request.user, request=request)
        return Response(
            ManagedStudentSerializer(student).data, status=status.HTTP_201_CREATED
        )

    def _resolve_group(self, request, class_group_id) -> ClassGroup:
        group = (
            ClassGroup.objects.select_related("grade", "school")
            .filter(pk=class_group_id, school_id__in=self.school_ids(request))
            .first()
        )
        if group is None:
            raise NotFoundError("Guruh topilmadi.", code="CLASS_GROUP_NOT_FOUND")
        return group


@transaction.atomic
def _create_student(data: dict, *, group: ClassGroup, user, request=None) -> Student:
    student = Student.objects.create(
        school=group.school,
        class_group=group,
        last_name=data["last_name"],
        first_name=data["first_name"],
        middle_name=data.get("middle_name", ""),
        birth_date=data.get("birth_date"),
        gender=data.get("gender", ""),
        student_code=(data.get("student_code") or "").strip(),
    )
    _sync_guardians(student, data.get("guardians") or [], user=user, request=request)

    log_action(
        AuditAction.STUDENT_CREATE,
        user=user,
        entity=student,
        request=request,
        new_data={"full_name": student.full_name, "class_group": group.display_name},
    )
    _queue_enrollment(student)
    return student


def _sync_guardians(student, entries: list[dict], *, user, request=None) -> None:
    """Create/attach the pupil's guardians, dropping links that were removed.

    A row is matched by ``id`` when the form is editing an existing guardian,
    and otherwise by JSHSHIR inside the school — so the same father added for a
    second child reuses the existing record instead of duplicating it.
    """
    keep_ids: list = []
    primary_guardian = None

    for entry in entries:
        guardian = _resolve_guardian(student, entry)
        if guardian is None:
            guardian = Guardian(school=student.school)
            guardian.set_jshshir(entry["jshshir"])
        elif guardian.deleted_at is not None:
            guardian.restore()

        guardian.last_name = entry["last_name"]
        guardian.first_name = entry["first_name"]
        guardian.middle_name = entry.get("middle_name", "")
        guardian.phone = entry["phone"]
        if entry.get("jshshir"):
            guardian.set_jshshir(entry["jshshir"])
        guardian.save()

        link, _created = GuardianStudent.objects.update_or_create(
            guardian=guardian,
            student=student,
            defaults={
                "relation": entry["relation"],
                # An administrator filling in the register *is* the school's own
                # record, so the link is trusted from the start.
                "verified": True,
                "verified_at": timezone.now(),
            },
        )
        keep_ids.append(link.id)
        if entry.get("is_primary") or primary_guardian is None:
            primary_guardian = guardian

        log_action(
            AuditAction.GUARDIAN_STUDENT_LINK,
            user=user,
            entity=link,
            request=request,
            metadata={"student_id": str(student.id), "relation": link.relation},
        )

    if not entries:
        return

    # Links the form no longer lists are detached (the guardian record itself
    # survives — they may still be another pupil's parent).
    removed = GuardianStudent.objects.filter(student=student).exclude(id__in=keep_ids)
    for link in removed:
        log_action(
            AuditAction.GUARDIAN_STUDENT_UNLINK,
            user=user,
            entity_type=GuardianStudent._meta.label,
            entity_id=str(link.id),
            request=request,
            metadata={"student_id": str(student.id)},
        )
    removed.delete()

    # Exactly one primary guardian: the flagged one, or the first one entered.
    GuardianStudent.objects.filter(student=student).update(is_primary=False)
    if primary_guardian is not None:
        GuardianStudent.objects.filter(
            student=student, guardian=primary_guardian
        ).update(is_primary=True)


def _resolve_guardian(student, entry: dict):
    """Find the guardian a form row refers to, by id first and JSHSHIR second."""
    from apps.common.crypto import hash_value

    if entry.get("id"):
        found = Guardian.all_objects.filter(
            pk=entry["id"], school=student.school
        ).first()
        if found is None:
            raise NotFoundError("Yaqini topilmadi.", code="GUARDIAN_NOT_FOUND")
        return found
    if entry.get("jshshir"):
        return Guardian.all_objects.filter(
            school=student.school, jshshir_hash=hash_value(entry["jshshir"])
        ).first()
    return None


def queue_enrollment(person) -> None:
    """Push a pupil or a member of staff onto the terminals after commit.

    Adding someone to the register is the whole action: nobody should have to
    open Sozlamalar → Face ID afterwards to make the gate recognise them. The
    "Avtomatik yuklash" switch is still honoured — a switch that silently does
    nothing is worse than no switch at all — and when it is off the person is
    still created, only the push waits to be run by hand.
    """
    from apps.integrations.constants import IntegrationKind
    from apps.integrations.services.enrollment import person_field
    from apps.integrations.services.registry import integration_config

    config = integration_config(IntegrationKind.FACE_ID, person.school)
    if not config.get("auto_enroll", True):
        logger.info("auto_enroll is off; skipping terminal push for %s", person.id)
        return

    field = person_field(person)
    person_id = str(person.id)

    def _enroll():
        from apps.integrations.tasks import (
            enroll_staff_on_terminals,
            enroll_student_on_terminals,
            enroll_teacher_on_terminals,
        )

        task = {
            "student": enroll_student_on_terminals,
            "teacher": enroll_teacher_on_terminals,
            "staff": enroll_staff_on_terminals,
        }[field]
        task.delay(person_id)

    transaction.on_commit(_enroll)


#: The pupil call sites still read better with the old name.
_queue_enrollment = queue_enrollment


@extend_schema(tags=["management"])
class ManagedStudentDetailView(ManagementView):
    read_permission = Perm.STUDENTS_VIEW
    write_permission = Perm.STUDENTS_MANAGE

    def get_object(self, request, pk) -> Student:
        student = _student_queryset(self.school_ids(request)).filter(pk=pk).first()
        if student is None:
            raise NotFoundError("O'quvchi topilmadi.", code="STUDENT_NOT_FOUND")
        return student

    @extend_schema(responses={200: ManagedStudentSerializer}, summary="O'quvchi ma'lumoti")
    def get(self, request, pk):
        return Response(ManagedStudentSerializer(self.get_object(request, pk)).data)

    @extend_schema(
        request=StudentPatchSerializer,
        responses={200: ManagedStudentSerializer},
        summary="O'quvchini tahrirlash",
    )
    def patch(self, request, pk):
        student = self.get_object(request, pk)
        serializer = StudentPatchSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        old = {"full_name": student.full_name, "class_group": student.class_group.display_name}

        for field in ("last_name", "first_name", "middle_name", "birth_date", "gender"):
            if field in data:
                setattr(student, field, data[field])
        if "student_code" in data:
            student.student_code = (data["student_code"] or "").strip()
        if data.get("class_group"):
            group = (
                ClassGroup.objects.select_related("grade", "school")
                .filter(pk=data["class_group"], school_id__in=self.school_ids(request))
                .first()
            )
            if group is None:
                raise NotFoundError("Guruh topilmadi.", code="CLASS_GROUP_NOT_FOUND")
            student.class_group = group
            student.school = group.school
        student.save()

        if "guardians" in data:
            _sync_guardians(student, data["guardians"], user=request.user, request=request)

        log_action(
            AuditAction.STUDENT_UPDATE,
            user=request.user,
            entity=student,
            request=request,
            old_data=old,
            new_data={
                "full_name": student.full_name,
                "class_group": student.class_group.display_name,
            },
        )
        return Response(ManagedStudentSerializer(self.get_object(request, pk)).data)

    @extend_schema(
        responses={200: OpenApiResponse(description="O'chirildi")},
        summary="O'quvchini o'chirish",
    )
    def delete(self, request, pk):
        student = self.get_object(request, pk)
        full_name = student.full_name
        retire_student(student)
        log_action(
            AuditAction.STUDENT_DELETE,
            user=request.user,
            entity_type=Student._meta.label,
            entity_id=str(pk),
            request=request,
            old_data={"full_name": full_name},
        )
        return Response({"deleted": True, "student": full_name})


@extend_schema(tags=["management"])
class ManagedStudentPhotoView(ManagementView):
    """Upload the pupil's face photo — stored and pushed to the terminals."""

    read_permission = Perm.STUDENTS_VIEW
    write_permission = Perm.STUDENTS_MANAGE

    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        request=StudentPhotoSerializer,
        responses={200: OpenApiResponse(description="Rasm saqlandi va terminalga yuborildi")},
        summary="O'quvchi rasmini yuklash",
    )
    def post(self, request, pk):
        student = _student_queryset(self.school_ids(request)).filter(pk=pk).first()
        if student is None:
            raise NotFoundError("O'quvchi topilmadi.", code="STUDENT_NOT_FOUND")

        serializer = StudentPhotoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        upload = serializer.validated_data["photo"]

        from apps.integrations.constants import IntegrationKind
        from apps.integrations.services.enrollment import EnrollmentError, prepare_face_image
        from apps.integrations.services.registry import integration_config

        config = integration_config(IntegrationKind.FACE_ID, student.school)
        raw = upload.read()
        if len(raw) < int(config.get("min_photo_bytes", 8 * 1024)):
            raise ConflictError(
                "Rasm juda kichik — aniqroq surat yuklang.", code="PHOTO_TOO_SMALL"
            )
        if len(raw) > int(config.get("max_photo_bytes", 2 * 1024 * 1024)):
            raise ConflictError("Rasm hajmi juda katta.", code="PHOTO_TOO_LARGE")
        try:
            prepare_face_image(raw)
        except EnrollmentError as exc:
            raise ConflictError(str(exc), code="PHOTO_INVALID") from None

        upload.seek(0)
        student.photo = upload
        student.save(update_fields=["photo", "updated_at"])

        log_action(
            AuditAction.STUDENT_UPDATE,
            user=request.user,
            entity=student,
            request=request,
            metadata={"operation": "photo_upload"},
        )
        _queue_enrollment(student)
        return Response(
            {
                "ok": True,
                "photo": absolute_media_url(student.photo),
                "enrollment": "queued",
            }
        )


@extend_schema(
    tags=["management"],
    responses={200: OpenApiResponse(description="Otasi / Onasi / Vasiysi / Boshqa")},
    summary="Qarindoshlik turlari",
)
class RelationChoicesView(ManagementView):
    read_permission = Perm.STUDENTS_VIEW

    def get(self, request):
        return Response(
            {
                "results": [
                    {"value": value, "label": label} for value, label in Relation.choices
                ]
            }
        )


# --------------------------------------------------------------------------- #
# Staff accounts (Foydalanuvchilar)
# --------------------------------------------------------------------------- #
class UserManagementView(APIView):
    """Foydalanuvchilar. Reading it and changing it are two different rights.

    ``users.view`` opens the screen — a MODERATOR has it and sees the accounts
    without a single button. ``users.manage`` is what any write costs, and the
    ladder in ``rbac`` then decides, per row, who may touch whom.
    """

    permission_classes = [CanManageUsers]

    def visible_users(self, request):
        """Accounts the caller may see.

        Two filters, and the order matters. First ``rbac.visible_users`` drops
        every account holding the DEVELOPER role for anybody who is not one
        themselves — not hidden in the template, *absent from the queryset*, so
        the list, the counters, the search and a fetch by id all agree the row
        is not there. Then the cabinet's own scope: this screen is about staff
        accounts, so a row has to hold at least one role the caller is allowed
        to know about. Parents are managed in Yaqinlar, not here.

        Deliberately *visible* roles rather than assignable ones: a MODERATOR
        reads this screen and hands out nothing, and filtering by what they may
        grant would leave them an empty page. Whether each row can be touched
        is a separate question, answered per row by ``can_manage``.
        """
        known = set(rbac.visible_roles(request.user))
        return (
            rbac.visible_users(request.user)
            .filter(user_roles__role__in=known)
            .select_related(
                "teacher_profile",
                "teacher_profile__school",
                "staff_profile",
                "staff_profile__school",
            )
            .prefetch_related("user_roles")
            .distinct()
            .order_by("role", "last_name", "first_name")
        )

    def get_target(self, request, pk) -> User:
        """One account, or a 404 that says nothing about why.

        A SUPER_ADMIN asking for a DEVELOPER's id by hand lands here and is
        told the user does not exist — the same answer as for an id that never
        existed, so the endpoint confirms nothing.
        """
        target = self.visible_users(request).filter(pk=pk).first()
        if target is None:
            raise NotFoundError("Foydalanuvchi topilmadi.", code="USER_NOT_FOUND")
        return target


@extend_schema(tags=["management"])
class ManagedUserListView(UserManagementView):
    @extend_schema(
        parameters=[
            OpenApiParameter("role", str, description="Rol bo'yicha filtr"),
            OpenApiParameter("q", str, description="Ism yoki login bo'yicha qidiruv"),
        ],
        responses={200: StaffUserSerializer(many=True)},
        summary="Foydalanuvchilar ro'yxati",
    )
    def get(self, request):
        queryset = self.visible_users(request)
        role = request.query_params.get("role")
        if role:
            # Filter on what the person *holds*, not on the hat they happen to
            # be wearing: a teacher who is also a curator belongs in both lists.
            queryset = queryset.filter(user_roles__role=role)
        query = (request.query_params.get("q") or "").strip()
        if query:
            queryset = queryset.filter(
                Q(first_name__icontains=query)
                | Q(last_name__icontains=query)
                | Q(username__icontains=query)
            )
        return Response(
            {
                "assignable_roles": [
                    {"value": role, "label": Role(role).label}
                    for role in rbac.assignable_roles(request.user)
                ],
                "results": StaffUserSerializer(
                    queryset.distinct(), many=True, context={"actor": request.user}
                ).data,
            }
        )

    @extend_schema(
        request=StaffUserWriteSerializer,
        responses={201: OpenApiResponse(description="Akkaunt va bir martalik parol")},
        summary="Foydalanuvchi qo'shish",
    )
    def post(self, request):
        serializer = StaffUserWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        roles = data.get("roles") or []
        school = None
        # A school-scoped role has to be scoped by something, so the register
        # row is created alongside the account.
        if {Role.ADMIN, Role.TEACHER, Role.CURATOR} & set(roles):
            school = resolve_school(request.user, data.get("school"))

        user, password = create_staff_user(
            actor=request.user,
            roles=roles,
            first_name=data["first_name"],
            last_name=data["last_name"],
            middle_name=data.get("middle_name", ""),
            phone=data.get("phone", ""),
            school=school,
            request=request,
        )
        return Response(
            {
                "user": StaffUserSerializer(user, context={"actor": request.user}).data,
                # Shown once, then gone: it is not stored anywhere in the clear.
                "temporary_password": password,
                "detail": (
                    "Parol faqat shu safar ko'rsatiladi. Foydalanuvchi birinchi "
                    "kirishda uni o'zgartirishi shart."
                ),
            },
            status=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["management"])
class ManagedUserDetailView(UserManagementView):
    @extend_schema(
        responses={200: StaffUserSerializer},
        summary="Foydalanuvchi",
    )
    def get(self, request, pk):
        return Response(
            StaffUserSerializer(
                self.get_target(request, pk), context={"actor": request.user}
            ).data
        )

    @extend_schema(
        request=StaffUserPatchSerializer,
        responses={200: StaffUserSerializer},
        summary="Foydalanuvchini tahrirlash",
    )
    def patch(self, request, pk):
        target = self.get_target(request, pk)
        serializer = StaffUserPatchSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        updated = update_staff_user(
            actor=request.user, target=target, request=request, **serializer.validated_data
        )
        return Response(
            StaffUserSerializer(updated, context={"actor": request.user}).data
        )

    @extend_schema(
        responses={200: OpenApiResponse(description="O'chirildi yoki bloklandi")},
        summary="Foydalanuvchini o'chirish",
    )
    def delete(self, request, pk):
        """Remove an account, keeping the history it is referenced by.

        A person who has approved an absence or marked a register is written
        into rows that must not disappear with them, and the database says so
        with ``PROTECT``. So the row goes when it can go, and when it cannot
        the account is disabled instead — either way the login stops working
        immediately and every live session is revoked. The response says which
        of the two happened rather than pretending they are the same.
        """
        from django.db.models import ProtectedError

        from apps.accounts.services.password_reset import revoke_all_sessions

        target = self.get_target(request, pk)
        assert_may_manage_user(request.user, target)

        username, roles = target.username, list(target.role_codes)
        revoke_all_sessions(target)
        try:
            with transaction.atomic():
                target.delete()
            removed = True
        except ProtectedError:
            target.is_active = False
            target.save(update_fields=["is_active", "updated_at"])
            removed = False

        log_action(
            AuditAction.USER_DELETE,
            user=request.user,
            entity=None,
            entity_type="accounts.User",
            entity_id=str(pk),
            request=request,
            old_data={"username": username, "roles": roles},
            metadata={"hard_delete": removed},
        )
        return Response(
            {
                "deleted": removed,
                "disabled": not removed,
                "username": username,
                "detail": (
                    "Foydalanuvchi o'chirildi."
                    if removed
                    else (
                        "Foydalanuvchi tarixda qatnashgani uchun o'chirilmadi — "
                        "akkaunt bloklandi va barcha sessiyalari tugatildi."
                    )
                ),
            }
        )


@extend_schema(tags=["management"])
class ManagedUserPasswordView(UserManagementView):
    """Issue a one-off password for an account.

    Existing passwords are Argon2 hashes and cannot be read back by anyone —
    this hands out a new one instead, shows it exactly once, forces a change at
    next login and writes who did it to the audit trail.
    """

    @extend_schema(
        request=None,
        responses={200: OpenApiResponse(description="Bir martalik parol")},
        summary="Vaqtinchalik parol berish",
    )
    def post(self, request, pk):
        target = self.get_target(request, pk)
        password = issue_temporary_password(
            actor=request.user, target=target, request=request
        )
        return Response(
            {
                "user": StaffUserSerializer(target, context={"actor": request.user}).data,
                "temporary_password": password,
                "detail": (
                    "Parol faqat shu safar ko'rsatiladi. Foydalanuvchi birinchi "
                    "kirishda uni o'zgartirishi shart."
                ),
            }
        )


# --------------------------------------------------------------------------- #
# Guardians (Yaqinlar) — who has registered, and against which child
# --------------------------------------------------------------------------- #
@extend_schema(tags=["management"], parameters=[SCHOOL_PARAM])
class ManagedGuardianListView(ManagementView):
    """The register of parents, and whether they have claimed their account."""

    read_permission = Perm.GUARDIANS_VIEW

    @extend_schema(
        parameters=[
            OpenApiParameter(
                "registered",
                str,
                description="yes — akkaunt ochganlar, no — hali ochmaganlar",
            ),
            OpenApiParameter("class_group", str, description="Guruh id"),
            OpenApiParameter("q", str, description="Ism bo'yicha qidiruv"),
        ],
        responses={200: ManagedGuardianRowSerializer(many=True)},
        summary="Yaqinlar va ro'yxatdan o'tganlar",
    )
    def get(self, request):
        queryset = (
            Guardian.objects.filter(school_id__in=self.school_ids(request))
            .select_related("user")
            .prefetch_related(
                Prefetch(
                    "student_links",
                    queryset=GuardianStudent.objects.select_related(
                        "student", "student__class_group", "student__class_group__grade"
                    ).order_by("-is_primary"),
                )
            )
            .order_by("last_name", "first_name")
        )

        registered = (request.query_params.get("registered") or "").lower()
        if registered in ("yes", "true", "1"):
            queryset = queryset.filter(user__isnull=False)
        elif registered in ("no", "false", "0"):
            queryset = queryset.filter(user__isnull=True)

        if request.query_params.get("class_group"):
            queryset = queryset.filter(
                student_links__student__class_group_id=request.query_params["class_group"]
            ).distinct()

        query = (request.query_params.get("q") or "").strip()
        if query:
            from apps.common.text import transliterate

            queryset = queryset.filter(search_name__icontains=transliterate(query))

        paginator = DefaultPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        return paginator.get_paginated_response(
            ManagedGuardianRowSerializer(page, many=True).data
        )
