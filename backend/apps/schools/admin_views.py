"""What the Django admin used to do, as a proper API.

The cabinet owns administration now, so everything the built-in admin provided
and the management screens did not — the school profile, academic years,
holidays, subjects, teachers, the Excel import and the audit trail — lives
here, behind the same role checks as the rest of ``/api/v1/management/``.
"""
from __future__ import annotations

import logging

from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponse
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from apps.accounts.catalog import Perm
from apps.accounts.constants import Role, staff_roles_for
from apps.accounts.services.provisioning import create_staff_user, update_staff_user
from apps.attendance.models import Schedule
from apps.attendance.services.timetable import add_entry, entry_payload, remove_entry
from apps.audit.constants import AuditAction
from apps.audit.models import AuditLog
from apps.audit.services import log_action
from apps.common.crypto import hash_value
from apps.common.exceptions import ConflictError, NotFoundError
from apps.common.pagination import DefaultPagination
from apps.common.permissions import CanViewAudit

from .admin_serializers import (
    AcademicYearWriteSerializer,
    AuditLogSerializer,
    HolidayWriteSerializer,
    ImportRequestSerializer,
    ManagedAcademicYearSerializer,
    ManagedHolidaySerializer,
    ManagedPositionSerializer,
    ManagedSchoolSerializer,
    ManagedStaffSerializer,
    ManagedSubjectSerializer,
    ManagedTeacherSerializer,
    PositionWriteSerializer,
    ScheduleEntrySerializer,
    ScheduleEntryWriteSerializer,
    SchoolWriteSerializer,
    StaffWriteSerializer,
    SubjectWriteSerializer,
    TeacherWriteSerializer,
)
from .management_views import SCHOOL_PARAM, ManagementView, queue_enrollment
from .models import (
    AcademicYear,
    ClassGroup,
    Holiday,
    Position,
    School,
    StaffMember,
    Subject,
    Teacher,
)
from .services.management import resolve_school

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# School profile
# --------------------------------------------------------------------------- #
@extend_schema(tags=["admin"], parameters=[SCHOOL_PARAM])
class ManagedSchoolListView(ManagementView):
    read_permission = Perm.SCHOOL_VIEW
    write_permission = Perm.SCHOOL_MANAGE

    @extend_schema(responses={200: ManagedSchoolSerializer(many=True)}, summary="Maktablar")
    def get(self, request):
        schools = (
            School.objects.filter(id__in=self.school_ids(request))
            .annotate(
                students_count=Count(
                    "students", filter=Q(students__deleted_at__isnull=True), distinct=True
                ),
                class_groups_count=Count(
                    "class_groups",
                    filter=Q(class_groups__deleted_at__isnull=True),
                    distinct=True,
                ),
            )
            .order_by("name")
        )
        return Response({"results": ManagedSchoolSerializer(schools, many=True).data})

    @extend_schema(
        request=SchoolWriteSerializer,
        responses={201: ManagedSchoolSerializer},
        summary="Maktab qo'shish",
    )
    def post(self, request):
        # Only the platform owner adds a school: an admin scoped to one cannot
        # create the second one and then walk into it.
        if not request.user.can_manage_integrations:
            raise ConflictError(
                "Yangi maktabni faqat dasturchi qo'sha oladi.", code="DEVELOPER_ONLY"
            )
        serializer = SchoolWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        school = School.objects.create(**serializer.validated_data)
        log_action(
            AuditAction.SCHOOL_STRUCTURE_CHANGE,
            user=request.user,
            entity=school,
            request=request,
            new_data={"name": school.name},
        )
        return Response(
            ManagedSchoolSerializer(school).data, status=status.HTTP_201_CREATED
        )


@extend_schema(tags=["admin"])
class ManagedSchoolDetailView(ManagementView):
    read_permission = Perm.SCHOOL_VIEW
    write_permission = Perm.SCHOOL_MANAGE

    def get_object(self, request, pk) -> School:
        school = School.objects.filter(pk=pk, id__in=self.school_ids(request)).first()
        if school is None:
            raise NotFoundError("Maktab topilmadi.", code="SCHOOL_NOT_FOUND")
        return school

    @extend_schema(
        request=SchoolWriteSerializer,
        responses={200: ManagedSchoolSerializer},
        summary="Maktab ma'lumotlarini tahrirlash",
    )
    def patch(self, request, pk):
        school = self.get_object(request, pk)
        serializer = SchoolWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        old = {"name": school.name, "working_weekdays": school.working_weekdays}
        for field, value in serializer.validated_data.items():
            setattr(school, field, value)
        school.save()

        log_action(
            AuditAction.SCHOOL_STRUCTURE_CHANGE,
            user=request.user,
            entity=school,
            request=request,
            old_data=old,
            new_data={"name": school.name, "working_weekdays": school.working_weekdays},
        )
        return Response(ManagedSchoolSerializer(school).data)


# --------------------------------------------------------------------------- #
# Academic years
# --------------------------------------------------------------------------- #
@extend_schema(tags=["admin"], parameters=[SCHOOL_PARAM])
class ManagedAcademicYearListView(ManagementView):
    read_permission = Perm.SCHOOL_VIEW
    write_permission = Perm.SCHOOL_MANAGE

    @extend_schema(
        responses={200: ManagedAcademicYearSerializer(many=True)}, summary="O'quv yillari"
    )
    def get(self, request):
        years = AcademicYear.objects.filter(
            school_id__in=self.school_ids(request)
        ).order_by("-start_date")
        return Response({"results": ManagedAcademicYearSerializer(years, many=True).data})

    @extend_schema(
        request=AcademicYearWriteSerializer,
        responses={201: ManagedAcademicYearSerializer},
        summary="O'quv yili qo'shish",
    )
    def post(self, request):
        serializer = AcademicYearWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        school = resolve_school(request.user, data.pop("school", None))
        if AcademicYear.objects.filter(school=school, name=data["name"]).exists():
            raise ConflictError("Bu o'quv yili allaqachon mavjud.", code="YEAR_EXISTS")

        with transaction.atomic():
            # A partial unique index enforces one current year per school, so
            # the old one has to be stood down before the new row is inserted.
            if data.get("is_current"):
                AcademicYear.objects.filter(school=school, is_current=True).update(
                    is_current=False
                )
            year = AcademicYear.objects.create(school=school, **data)

        log_action(
            AuditAction.SCHOOL_STRUCTURE_CHANGE,
            user=request.user,
            entity=year,
            request=request,
            new_data={"academic_year": year.name},
        )
        return Response(
            ManagedAcademicYearSerializer(year).data, status=status.HTTP_201_CREATED
        )


@extend_schema(tags=["admin"])
class ManagedAcademicYearDetailView(ManagementView):
    read_permission = Perm.SCHOOL_VIEW
    write_permission = Perm.SCHOOL_MANAGE

    def get_object(self, request, pk) -> AcademicYear:
        year = AcademicYear.objects.filter(
            pk=pk, school_id__in=self.school_ids(request)
        ).first()
        if year is None:
            raise NotFoundError("O'quv yili topilmadi.", code="YEAR_NOT_FOUND")
        return year

    @extend_schema(
        request=AcademicYearWriteSerializer,
        responses={200: ManagedAcademicYearSerializer},
        summary="O'quv yilini tahrirlash",
    )
    def patch(self, request, pk):
        year = self.get_object(request, pk)
        serializer = AcademicYearWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        data.pop("school", None)

        with transaction.atomic():
            if data.get("is_current"):
                AcademicYear.objects.filter(
                    school=year.school, is_current=True
                ).exclude(pk=year.pk).update(is_current=False)
            for field, value in data.items():
                setattr(year, field, value)
            year.save()

        log_action(
            AuditAction.SCHOOL_STRUCTURE_CHANGE,
            user=request.user,
            entity=year,
            request=request,
            new_data={"academic_year": year.name, "is_current": year.is_current},
        )
        return Response(ManagedAcademicYearSerializer(year).data)

    @extend_schema(
        responses={200: OpenApiResponse(description="O'chirildi")},
        summary="O'quv yilini o'chirish",
    )
    def delete(self, request, pk):
        year = self.get_object(request, pk)
        if ClassGroup.all_objects.filter(academic_year=year).exists():
            raise ConflictError(
                "Bu o'quv yiliga bog'langan guruhlar bor — avval ularni o'chiring.",
                code="YEAR_IN_USE",
            )
        name = year.name
        year.delete()
        log_action(
            AuditAction.SCHOOL_STRUCTURE_CHANGE,
            user=request.user,
            entity_type=AcademicYear._meta.label,
            entity_id=str(pk),
            request=request,
            old_data={"academic_year": name},
        )
        return Response({"deleted": True, "academic_year": name})


# --------------------------------------------------------------------------- #
# Holidays — days the school is shut, which never count against a pupil
# --------------------------------------------------------------------------- #
@extend_schema(tags=["admin"], parameters=[SCHOOL_PARAM])
class ManagedHolidayListView(ManagementView):
    read_permission = Perm.SCHOOL_VIEW
    write_permission = Perm.SCHOOL_MANAGE

    @extend_schema(
        parameters=[OpenApiParameter("academic_year", str, description="O'quv yili id")],
        responses={200: ManagedHolidaySerializer(many=True)},
        summary="Bayram va dam olish kunlari",
    )
    def get(self, request):
        holidays = (
            Holiday.objects.filter(school_id__in=self.school_ids(request))
            .select_related("academic_year")
            .order_by("-date")
        )
        if request.query_params.get("academic_year"):
            holidays = holidays.filter(
                academic_year_id=request.query_params["academic_year"]
            )
        return Response({"results": ManagedHolidaySerializer(holidays, many=True).data})

    @extend_schema(
        request=HolidayWriteSerializer,
        responses={201: ManagedHolidaySerializer},
        summary="Bayram qo'shish",
    )
    def post(self, request):
        serializer = HolidayWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        school = resolve_school(request.user, data.pop("school", None))
        year = self._resolve_year(school, data.pop("academic_year", None))
        if Holiday.objects.filter(school=school, date=data["date"]).exists():
            raise ConflictError("Bu sana uchun yozuv allaqachon bor.", code="HOLIDAY_EXISTS")

        holiday = Holiday.objects.create(school=school, academic_year=year, **data)
        log_action(
            AuditAction.SCHOOL_STRUCTURE_CHANGE,
            user=request.user,
            entity=holiday,
            request=request,
            new_data={"date": holiday.date.isoformat(), "name": holiday.name},
        )
        return Response(
            ManagedHolidaySerializer(holiday).data, status=status.HTTP_201_CREATED
        )

    @staticmethod
    def _resolve_year(school, year_id) -> AcademicYear:
        from .services.management import current_academic_year

        year = (
            AcademicYear.objects.filter(pk=year_id, school=school).first()
            if year_id
            else current_academic_year(school)
        )
        if year is None:
            raise ConflictError("Avval o'quv yilini yarating.", code="ACADEMIC_YEAR_MISSING")
        return year


@extend_schema(tags=["admin"])
class ManagedHolidayDetailView(ManagementView):
    read_permission = Perm.SCHOOL_VIEW
    write_permission = Perm.SCHOOL_MANAGE

    @extend_schema(
        responses={200: OpenApiResponse(description="O'chirildi")},
        summary="Bayramni o'chirish",
    )
    def delete(self, request, pk):
        holiday = Holiday.objects.filter(
            pk=pk, school_id__in=self.school_ids(request)
        ).first()
        if holiday is None:
            raise NotFoundError("Yozuv topilmadi.", code="HOLIDAY_NOT_FOUND")
        label = f"{holiday.date} {holiday.name}"
        holiday.delete()
        log_action(
            AuditAction.SCHOOL_STRUCTURE_CHANGE,
            user=request.user,
            entity_type=Holiday._meta.label,
            entity_id=str(pk),
            request=request,
            old_data={"holiday": label},
        )
        return Response({"deleted": True, "holiday": label})


# --------------------------------------------------------------------------- #
# Subjects
# --------------------------------------------------------------------------- #
def _resolve_class_group(school, class_group_id):
    """The class group a subject belongs to, checked against the same school."""
    if not class_group_id:
        return None
    group = ClassGroup.objects.filter(pk=class_group_id, school=school).first()
    if group is None:
        raise NotFoundError("Sinf guruhi topilmadi.", code="CLASS_GROUP_NOT_FOUND")
    return group


@extend_schema(tags=["admin"], parameters=[SCHOOL_PARAM])
class ManagedSubjectListView(ManagementView):
    read_permission = Perm.SUBJECTS_VIEW
    write_permission = Perm.SUBJECTS_MANAGE

    @extend_schema(
        parameters=[
            OpenApiParameter("class_group", str, description="Sinf guruhi bo'yicha filtr")
        ],
        responses={200: ManagedSubjectSerializer(many=True)},
        summary="Fanlar",
    )
    def get(self, request):
        subjects = Subject.objects.filter(
            school_id__in=self.school_ids(request)
        ).select_related("class_group__grade")
        class_group = request.query_params.get("class_group")
        if class_group:
            subjects = subjects.filter(class_group_id=class_group)
        return Response({"results": ManagedSubjectSerializer(subjects, many=True).data})

    @extend_schema(
        request=SubjectWriteSerializer,
        responses={201: ManagedSubjectSerializer},
        summary="Fan qo'shish",
    )
    def post(self, request):
        serializer = SubjectWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        school = resolve_school(request.user, data.pop("school", None))
        class_group = _resolve_class_group(school, data.pop("class_group", None))
        # A name only clashes inside one class group: Matematika 1-A and
        # Matematika 1-B are two different rows.
        if Subject.objects.filter(
            school=school, class_group=class_group, name__iexact=data["name"]
        ).exists():
            raise ConflictError("Bu fan allaqachon mavjud.", code="SUBJECT_EXISTS")

        subject = Subject.objects.create(school=school, class_group=class_group, **data)
        return Response(
            ManagedSubjectSerializer(subject).data, status=status.HTTP_201_CREATED
        )


@extend_schema(tags=["admin"])
class ManagedSubjectDetailView(ManagementView):
    read_permission = Perm.SUBJECTS_VIEW
    write_permission = Perm.SUBJECTS_MANAGE

    def get_object(self, request, pk) -> Subject:
        subject = Subject.objects.filter(
            pk=pk, school_id__in=self.school_ids(request)
        ).first()
        if subject is None:
            raise NotFoundError("Fan topilmadi.", code="SUBJECT_NOT_FOUND")
        return subject

    @extend_schema(
        request=SubjectWriteSerializer,
        responses={200: ManagedSubjectSerializer},
        summary="Fanni tahrirlash",
    )
    def patch(self, request, pk):
        subject = self.get_object(request, pk)
        serializer = SubjectWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        data.pop("school", None)
        if "class_group" in data:
            subject.class_group = _resolve_class_group(subject.school, data.pop("class_group"))
        for field, value in data.items():
            setattr(subject, field, value)
        subject.save()
        return Response(ManagedSubjectSerializer(subject).data)

    @extend_schema(
        responses={200: OpenApiResponse(description="O'chirildi")}, summary="Fanni o'chirish"
    )
    def delete(self, request, pk):
        subject = self.get_object(request, pk)
        name = subject.display_name
        subject.delete()  # soft delete
        return Response({"deleted": True, "subject": name})


# --------------------------------------------------------------------------- #
# Teachers
# --------------------------------------------------------------------------- #
def _check_teacher_identifiers(school, data: dict, *, exclude=None) -> None:
    """Refuse a document that already belongs to somebody else in this school.

    The database enforces this too, but only as a 500-shaped IntegrityError —
    the admin deserves to be told which field clashed.
    """
    passport = data.get("passport_id") or ""
    if passport:
        clash = Teacher.objects.filter(school=school, passport_id=passport)
        if exclude is not None:
            clash = clash.exclude(pk=exclude.pk)
        if clash.exists():
            raise ConflictError(
                "Bu passport ID boshqa o'qituvchida ro'yxatdan o'tgan.",
                code="TEACHER_PASSPORT_EXISTS",
            )

    jshshir = data.get("jshshir") or ""
    if jshshir:
        clash = Teacher.objects.filter(school=school, jshshir_hash=hash_value(jshshir))
        if exclude is not None:
            clash = clash.exclude(pk=exclude.pk)
        if clash.exists():
            raise ConflictError(
                "Bu JSHSHIR boshqa o'qituvchida ro'yxatdan o'tgan.",
                code="TEACHER_JSHSHIR_EXISTS",
            )


@extend_schema(tags=["admin"], parameters=[SCHOOL_PARAM])
class ManagedTeacherListView(ManagementView):
    read_permission = Perm.TEACHERS_VIEW
    write_permission = Perm.TEACHERS_MANAGE

    parser_classes = [MultiPartParser, FormParser, *ManagementView.parser_classes]

    @extend_schema(
        parameters=[OpenApiParameter("q", str, description="Ism bo'yicha qidiruv")],
        responses={200: ManagedTeacherSerializer(many=True)},
        summary="O'qituvchilar",
    )
    def get(self, request):
        teachers = (
            Teacher.objects.filter(school_id__in=self.school_ids(request))
            .select_related("user")
            .prefetch_related("subjects")
            .order_by("last_name", "first_name")
        )
        query = (request.query_params.get("q") or "").strip()
        if query:
            teachers = teachers.filter(
                Q(first_name__icontains=query) | Q(last_name__icontains=query)
            )
        return Response({"results": ManagedTeacherSerializer(teachers, many=True).data})

    @extend_schema(
        request=TeacherWriteSerializer,
        responses={201: ManagedTeacherSerializer},
        summary="O'qituvchi qo'shish",
    )
    def post(self, request):
        serializer = TeacherWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        school = resolve_school(request.user, data.pop("school", None))
        _check_teacher_identifiers(school, data)
        subject_ids = data.pop("subjects", [])
        # JSHSHIR is not a plain column: it fans out into hash/ciphertext/last4.
        jshshir = data.pop("jshshir", "")
        photo = data.pop("photo", None)
        username = data.pop("username", "")
        password = data.pop("password", "")

        with transaction.atomic():
            account = None
            if username:
                # The operator typed the login and the password, so there is no
                # forced change on first sign-in — the teacher already has them.
                account, _password = create_staff_user(
                    actor=request.user,
                    role=Role.TEACHER,
                    first_name=data["first_name"],
                    last_name=data["last_name"],
                    middle_name=data.get("middle_name", ""),
                    phone=data.get("phone", ""),
                    request=request,
                    username=username,
                    password=password,
                )
            teacher = Teacher(school=school, user=account, **data)
            teacher.set_jshshir(jshshir)
            if photo is not None:
                teacher.photo = photo
            teacher.save()
            if subject_ids:
                teacher.subjects.set(
                    Subject.objects.filter(pk__in=subject_ids, school=school)
                )
        # Adding a teacher is the whole action: the gate learns them straight
        # away, with no second trip through Sozlamalar → Face ID.
        queue_enrollment(teacher)
        return Response(
            ManagedTeacherSerializer(teacher).data, status=status.HTTP_201_CREATED
        )


@extend_schema(tags=["admin"])
class ManagedTeacherDetailView(ManagementView):
    read_permission = Perm.TEACHERS_VIEW
    write_permission = Perm.TEACHERS_MANAGE

    parser_classes = [MultiPartParser, FormParser, *ManagementView.parser_classes]

    def get_object(self, request, pk) -> Teacher:
        teacher = (
            Teacher.objects.filter(pk=pk, school_id__in=self.school_ids(request))
            .select_related("user")
            .first()
        )
        if teacher is None:
            raise NotFoundError("O'qituvchi topilmadi.", code="TEACHER_NOT_FOUND")
        return teacher

    @extend_schema(
        responses={200: OpenApiResponse(description="O'qituvchining to'liq profili")},
        summary="O'qituvchi profili",
    )
    def get(self, request, pk):
        """Всё, что открывается по клику на карточку, одним ответом."""
        from .services.profile import teacher_profile

        return Response(
            teacher_profile(
                self.get_object(request, pk),
                with_presence=request.user.has_permission(Perm.ATTENDANCE_VIEW),
            )
        )

    @extend_schema(
        request=TeacherWriteSerializer,
        responses={200: ManagedTeacherSerializer},
        summary="O'qituvchini tahrirlash",
    )
    def patch(self, request, pk):
        teacher = self.get_object(request, pk)
        serializer = TeacherWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        data.pop("school", None)
        # Credentials are set when the account is created; changing them lives
        # in Foydalanuvchilar, which audits the reset.
        data.pop("username", None)
        data.pop("password", None)
        _check_teacher_identifiers(teacher.school, data, exclude=teacher)
        subject_ids = data.pop("subjects", None)
        photo = data.pop("photo", None)
        if "jshshir" in data:
            teacher.set_jshshir(data.pop("jshshir"))
        for field, value in data.items():
            setattr(teacher, field, value)
        if photo is not None:
            teacher.photo = photo
        teacher.save()
        if photo is not None:
            # A new face has to reach the devices, not just the database.
            queue_enrollment(teacher)
        if subject_ids is not None:
            teacher.subjects.set(
                Subject.objects.filter(pk__in=subject_ids, school=teacher.school)
            )
        return Response(ManagedTeacherSerializer(teacher).data)

    @extend_schema(
        responses={200: OpenApiResponse(description="O'chirildi")},
        summary="O'qituvchini o'chirish",
    )
    def delete(self, request, pk):
        teacher = self.get_object(request, pk)
        name = teacher.full_name
        teacher.delete()  # soft delete
        return Response({"deleted": True, "teacher": name})


# --------------------------------------------------------------------------- #
# Positions
# --------------------------------------------------------------------------- #
@extend_schema(tags=["admin"], parameters=[SCHOOL_PARAM])
class ManagedPositionListView(ManagementView):
    read_permission = Perm.POSITIONS_VIEW
    write_permission = Perm.POSITIONS_MANAGE

    @extend_schema(
        responses={200: ManagedPositionSerializer(many=True)}, summary="Lavozimlar"
    )
    def get(self, request):
        positions = Position.objects.filter(
            school_id__in=self.school_ids(request)
        ).annotate(
            staff_count=Count(
                "staff_members", filter=Q(staff_members__deleted_at__isnull=True)
            )
        )
        return Response({"results": ManagedPositionSerializer(positions, many=True).data})

    @extend_schema(
        request=PositionWriteSerializer,
        responses={201: ManagedPositionSerializer},
        summary="Lavozim qo'shish",
    )
    def post(self, request):
        serializer = PositionWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        school = resolve_school(request.user, data.pop("school", None))
        _check_position_title(school, data["title_uz"])

        position = Position.objects.create(school=school, **data)
        log_action(
            AuditAction.SCHOOL_STRUCTURE_CHANGE,
            entity=position,
            new_data=position.titles,
            request=request,
        )
        return Response(
            ManagedPositionSerializer(position).data, status=status.HTTP_201_CREATED
        )


def _check_position_title(school, title: str, *, exclude=None) -> None:
    """One name per school. The database says so too, but not in words."""
    clash = Position.objects.filter(school=school, title_uz__iexact=(title or "").strip())
    if exclude is not None:
        clash = clash.exclude(pk=exclude.pk)
    if clash.exists():
        raise ConflictError(
            "Bunday lavozim allaqachon mavjud.", code="POSITION_EXISTS"
        )


@extend_schema(tags=["admin"])
class ManagedPositionDetailView(ManagementView):
    read_permission = Perm.POSITIONS_VIEW
    write_permission = Perm.POSITIONS_MANAGE

    def get_object(self, request, pk) -> Position:
        position = Position.objects.filter(
            pk=pk, school_id__in=self.school_ids(request)
        ).first()
        if position is None:
            raise NotFoundError("Lavozim topilmadi.", code="POSITION_NOT_FOUND")
        return position

    @extend_schema(
        request=PositionWriteSerializer,
        responses={200: ManagedPositionSerializer},
        summary="Lavozimni tahrirlash",
    )
    def patch(self, request, pk):
        position = self.get_object(request, pk)
        serializer = PositionWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        data.pop("school", None)
        if "title_uz" in data:
            _check_position_title(position.school, data["title_uz"], exclude=position)

        before = position.titles
        for field, value in data.items():
            setattr(position, field, value)
        position.save()
        log_action(
            AuditAction.SCHOOL_STRUCTURE_CHANGE,
            entity=position,
            old_data=before,
            new_data=position.titles,
            request=request,
        )
        return Response(ManagedPositionSerializer(position).data)

    @extend_schema(
        responses={200: OpenApiResponse(description="O'chirildi")},
        summary="Lavozimni o'chirish",
    )
    def delete(self, request, pk):
        position = self.get_object(request, pk)
        # A position in use is the label on somebody's record; removing it would
        # leave those rows unreadable, so say what is holding it instead.
        in_use = position.staff_members.count()
        if in_use:
            raise ConflictError(
                f"Bu lavozimda {in_use} ta xodim bor. Avval ularni boshqa lavozimga o'tkazing.",
                code="POSITION_IN_USE",
            )
        title = position.title_uz
        position.delete()  # soft delete
        return Response({"deleted": True, "position": title})


# --------------------------------------------------------------------------- #
# Staff
# --------------------------------------------------------------------------- #
def _check_staff_identifiers(school, data: dict, *, exclude=None) -> None:
    """Refuse a document that already belongs to another staff member here."""
    passport = data.get("passport_id") or ""
    if passport:
        clash = StaffMember.objects.filter(school=school, passport_id=passport)
        if exclude is not None:
            clash = clash.exclude(pk=exclude.pk)
        if clash.exists():
            raise ConflictError(
                "Bu passport ID boshqa xodimda ro'yxatdan o'tgan.",
                code="STAFF_PASSPORT_EXISTS",
            )

    jshshir = data.get("jshshir") or ""
    if jshshir:
        clash = StaffMember.objects.filter(school=school, jshshir_hash=hash_value(jshshir))
        if exclude is not None:
            clash = clash.exclude(pk=exclude.pk)
        if clash.exists():
            raise ConflictError(
                "Bu JSHSHIR boshqa xodimda ro'yxatdan o'tgan.",
                code="STAFF_JSHSHIR_EXISTS",
            )


def _resolve_position(school, position_id):
    """The position, or ``None`` when the field was sent empty on purpose."""
    if not position_id:
        return None
    position = Position.objects.filter(pk=position_id, school=school).first()
    if position is None:
        raise NotFoundError("Lavozim topilmadi.", code="POSITION_NOT_FOUND")
    return position


def _check_staff_roles(actor, roles) -> list[str]:
    """Refuse a role the staff register is not allowed to hand out.

    Two rules at once: nobody provisions above their own station, and nobody
    becomes a DEVELOPER by way of the staff register — that account is the
    platform owner's and lives outside the school's people entirely.

    Returns the cleaned list. Empty means "nothing was chosen", which is a
    perfectly good answer: the account, if one is created at all, falls back to
    STAFF in :func:`apps.accounts.services.provisioning.create_staff_user`.
    """
    cleaned: list[str] = []
    allowed = set(staff_roles_for(actor.role))
    for role in roles or ():
        role = (role or "").strip()
        if not role or role in cleaned:
            continue
        if role == Role.DEVELOPER:
            raise ConflictError(
                "DEVELOPER roli xodimlar reyestri orqali berilmaydi.",
                code="STAFF_ROLE_FORBIDDEN",
            )
        if role not in allowed:
            raise ConflictError(
                "Bu rolni berishga ruxsatingiz yo'q.", code="STAFF_ROLE_FORBIDDEN"
            )
        cleaned.append(role)
    return cleaned


@extend_schema(tags=["admin"], parameters=[SCHOOL_PARAM])
class ManagedStaffListView(ManagementView):
    read_permission = Perm.STAFF_VIEW
    write_permission = Perm.STAFF_MANAGE

    parser_classes = [MultiPartParser, FormParser, *ManagementView.parser_classes]

    @extend_schema(
        parameters=[OpenApiParameter("q", str, description="Ism bo'yicha qidiruv")],
        responses={200: ManagedStaffSerializer(many=True)},
        summary="Xodimlar",
    )
    def get(self, request):
        staff = (
            StaffMember.objects.filter(school_id__in=self.school_ids(request))
            .select_related("user", "position")
            .order_by("last_name", "first_name")
        )
        query = (request.query_params.get("q") or "").strip()
        if query:
            staff = staff.filter(
                Q(first_name__icontains=query) | Q(last_name__icontains=query)
            )
        return Response(
            {
                # What this particular caller may hand out, so the form offers
                # exactly that and nothing it would be refused for.
                # What this particular caller may hand out, so the form offers
                # exactly that and nothing it would be refused for.
                "assignable_roles": [
                    {"value": role, "label": Role(role).label}
                    for role in staff_roles_for(request.user.role)
                ],
                "results": ManagedStaffSerializer(staff, many=True).data,
            }
        )

    @extend_schema(
        request=StaffWriteSerializer,
        responses={201: ManagedStaffSerializer},
        summary="Xodim qo'shish",
    )
    def post(self, request):
        serializer = StaffWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        school = resolve_school(request.user, data.pop("school", None))
        _check_staff_identifiers(school, data)
        position = _resolve_position(school, data.pop("position", None))
        roles = _check_staff_roles(request.user, data.pop("roles", []))
        # JSHSHIR is not a plain column: it fans out into hash/ciphertext/last4.
        jshshir = data.pop("jshshir", "")
        photo = data.pop("photo", None)
        username = data.pop("username", "")
        password = data.pop("password", "")

        with transaction.atomic():
            account = None
            if username:
                # An account is optional: most of the staff — the kitchen, the
                # guards — never sign in, and the register holds them anyway.
                # When one is asked for, the operator typed the credentials, so
                # there is no forced change on first sign-in.
                account, _password = create_staff_user(
                    actor=request.user,
                    # Nothing ticked means an ordinary employee — which is what
                    # most of this register is — rather than an administrator.
                    roles=roles,
                    first_name=data["first_name"],
                    last_name=data["last_name"],
                    middle_name=data.get("middle_name", ""),
                    phone=data.get("phone", ""),
                    request=request,
                    username=username,
                    password=password,
                )
            staff = StaffMember(school=school, user=account, position=position, **data)
            staff.set_jshshir(jshshir)
            if photo is not None:
                staff.photo = photo
            staff.save()
        return Response(
            ManagedStaffSerializer(staff).data, status=status.HTTP_201_CREATED
        )


@extend_schema(tags=["admin"])
class ManagedStaffDetailView(ManagementView):
    read_permission = Perm.STAFF_VIEW
    write_permission = Perm.STAFF_MANAGE

    parser_classes = [MultiPartParser, FormParser, *ManagementView.parser_classes]

    def get_object(self, request, pk) -> StaffMember:
        staff = (
            StaffMember.objects.filter(pk=pk, school_id__in=self.school_ids(request))
            .select_related("user", "position")
            .first()
        )
        if staff is None:
            raise NotFoundError("Xodim topilmadi.", code="STAFF_NOT_FOUND")
        return staff

    @extend_schema(
        responses={200: OpenApiResponse(description="Xodimning to'liq profili")},
        summary="Xodim profili",
    )
    def get(self, request, pk):
        from .services.profile import staff_profile

        return Response(
            staff_profile(
                self.get_object(request, pk),
                with_presence=request.user.has_permission(Perm.ATTENDANCE_VIEW),
            )
        )

    @extend_schema(
        request=StaffWriteSerializer,
        responses={200: ManagedStaffSerializer},
        summary="Xodimni tahrirlash",
    )
    def patch(self, request, pk):
        staff = self.get_object(request, pk)
        serializer = StaffWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        data.pop("school", None)
        # Credentials are set when the account is created; changing them lives
        # in Foydalanuvchilar, which audits the reset.
        data.pop("username", None)
        data.pop("password", None)
        _check_staff_identifiers(staff.school, data, exclude=staff)
        if "position" in data:
            # Sending it empty is how a label is taken off again.
            staff.position = _resolve_position(staff.school, data.pop("position"))
        if "roles" in data:
            roles = _check_staff_roles(request.user, data.pop("roles"))
            if roles and staff.user_id is None:
                raise ConflictError(
                    "Avval xodimga kabinet akkaunti yarating.",
                    code="STAFF_HAS_NO_ACCOUNT",
                )
            if roles:
                # Changing what an existing account may do. Who may touch whom
                # is already settled by `_check_staff_roles`; the service
                # writes the role rows, repairs the active role and audits both
                # the grants and the revocations.
                update_staff_user(
                    actor=request.user,
                    target=staff.user,
                    roles=roles,
                    request=request,
                )
        photo = data.pop("photo", None)
        if "jshshir" in data:
            staff.set_jshshir(data.pop("jshshir"))
        for field, value in data.items():
            setattr(staff, field, value)
        if photo is not None:
            staff.photo = photo
        staff.save()
        return Response(ManagedStaffSerializer(staff).data)

    @extend_schema(
        responses={200: OpenApiResponse(description="O'chirildi")},
        summary="Xodimni o'chirish",
    )
    def delete(self, request, pk):
        staff = self.get_object(request, pk)
        name = staff.full_name
        staff.delete()  # soft delete
        return Response({"deleted": True, "staff": name})


# --------------------------------------------------------------------------- #
# Excel import
# --------------------------------------------------------------------------- #
@extend_schema(tags=["admin"])
class ImportTemplateView(ManagementView):
    read_permission = Perm.IMPORT_RUN
    write_permission = Perm.IMPORT_RUN

    @extend_schema(
        responses={200: OpenApiResponse(description="XLSX namuna")},
        summary="Import namunasini yuklab olish",
    )
    def get(self, request):
        from .services.template import build_template

        response = HttpResponse(
            build_template(),
            content_type=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
        )
        response["Content-Disposition"] = 'attachment; filename="namuna.xlsx"'
        return response


@extend_schema(tags=["admin"])
class StudentImportView(ManagementView):
    """Two-phase by design: validate and preview first, write only on request."""

    read_permission = Perm.IMPORT_RUN
    write_permission = Perm.IMPORT_RUN

    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        request=ImportRequestSerializer,
        responses={200: OpenApiResponse(description="Import hisoboti")},
        summary="Excel import (tekshirish yoki yozish)",
    )
    def post(self, request):
        serializer = ImportRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        school = resolve_school(request.user, data.get("school"))
        year = ManagedHolidayListView._resolve_year(school, data.get("academic_year"))

        from .services.imports import ImportError_, import_workbook

        upload = data["file"]
        if not upload.name.lower().endswith(".xlsx"):
            raise ConflictError("Faqat .xlsx fayl qabul qilinadi.", code="INVALID_FILE")

        try:
            report = import_workbook(
                upload, school=school, academic_year=year, dry_run=not data["commit"]
            )
        except ImportError_ as error:
            raise ConflictError(str(error), code="IMPORT_FAILED") from None

        if data["commit"] and report.ok:
            log_action(
                AuditAction.IMPORT_STUDENTS,
                user=request.user,
                request=request,
                metadata={
                    "school": str(school.id),
                    "students_created": report.students_created,
                    "guardians_created": report.guardians_created,
                },
            )
        return Response(report.to_dict())


# --------------------------------------------------------------------------- #
# Audit trail
# --------------------------------------------------------------------------- #
@extend_schema(tags=["admin"])
class AuditLogListView(ManagementView):
    """Reading the trail is a privileged action: it names people and actions."""

    permission_classes = [CanViewAudit]
    read_permission = Perm.AUDIT_VIEW

    @extend_schema(
        parameters=[
            OpenApiParameter("action", str, description="Amal turi"),
            OpenApiParameter("q", str, description="Login bo'yicha qidiruv"),
        ],
        responses={200: AuditLogSerializer(many=True)},
        summary="Audit jurnali",
    )
    def get(self, request):
        queryset = AuditLog.objects.select_related("user").order_by("-created_at")
        if request.query_params.get("action"):
            queryset = queryset.filter(action=request.query_params["action"])
        query = (request.query_params.get("q") or "").strip()
        if query:
            queryset = queryset.filter(username__icontains=query)

        paginator = DefaultPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        response = paginator.get_paginated_response(
            AuditLogSerializer(page, many=True).data
        )
        response.data["actions"] = [
            {"value": value, "label": label} for value, label in AuditAction.choices
        ]
        return response


# --------------------------------------------------------------------------- #
# Dars jadvali
# --------------------------------------------------------------------------- #
def _managed_class_group(request, view, class_group_id) -> ClassGroup:
    group = (
        ClassGroup.objects.filter(
            pk=class_group_id, school_id__in=view.school_ids(request)
        )
        .select_related("grade", "school")
        .first()
    )
    if group is None:
        raise NotFoundError("Sinf guruhi topilmadi.", code="CLASS_GROUP_NOT_FOUND")
    return group


@extend_schema(tags=["admin"], parameters=[SCHOOL_PARAM])
class ManagedScheduleListView(ManagementView):
    read_permission = Perm.TIMETABLE_VIEW
    write_permission = Perm.TIMETABLE_MANAGE

    @extend_schema(
        parameters=[
            OpenApiParameter("class_group", str, description="Sinf guruhi (majburiy)"),
            OpenApiParameter("weekday", int, description="Hafta kuni 1-7"),
        ],
        responses={200: ScheduleEntrySerializer(many=True)},
        summary="Dars jadvali",
    )
    def get(self, request):
        group = _managed_class_group(request, self, request.query_params.get("class_group"))
        weekday = request.query_params.get("weekday")
        entries = Schedule.objects.filter(class_group=group, is_active=True).select_related(
            "subject", "subject__class_group", "subject__class_group__grade", "teacher"
        )
        if weekday:
            entries = entries.filter(weekday=weekday)
        entries = entries.order_by("weekday", "lesson_number", "start_time")
        return Response({"results": [entry_payload(entry) for entry in entries]})

    @extend_schema(
        request=ScheduleEntryWriteSerializer,
        responses={201: ScheduleEntrySerializer},
        summary="Darsni jadvalga qo'shish",
    )
    def post(self, request):
        serializer = ScheduleEntryWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        group = _managed_class_group(request, self, data.pop("class_group"))
        entry = add_entry(group, data)
        return Response(entry_payload(entry), status=status.HTTP_201_CREATED)


@extend_schema(tags=["admin"])
class ManagedScheduleDetailView(ManagementView):
    read_permission = Perm.TIMETABLE_VIEW
    write_permission = Perm.TIMETABLE_MANAGE

    def get_object(self, request, pk) -> Schedule:
        entry = (
            Schedule.objects.filter(pk=pk, class_group__school_id__in=self.school_ids(request))
            .select_related("class_group", "class_group__grade", "subject", "teacher")
            .first()
        )
        if entry is None:
            raise NotFoundError("Dars topilmadi.", code="SCHEDULE_NOT_FOUND")
        return entry

    @extend_schema(
        responses={200: OpenApiResponse(description="O'chirildi")},
        summary="Darsni jadvaldan o'chirish",
    )
    def delete(self, request, pk):
        entry = self.get_object(request, pk)
        label = f"{entry.subject.display_name} · {entry.start_time:%H:%M}"
        remove_entry(entry)
        return Response({"deleted": True, "lesson": label})


# --------------------------------------------------------------------------- #
# The administrator's home screen, and taking the register back out
# --------------------------------------------------------------------------- #
@extend_schema(tags=["admin"], parameters=[SCHOOL_PARAM])
class SchoolOverviewView(ManagementView):
    """Register size, today at the gate, and the state of the devices."""

    read_permission = Perm.REPORTS_VIEW

    @extend_schema(summary="Maktab statistikasi")
    def get(self, request):
        from .services.overview import school_overview

        school = resolve_school(request.user, request.query_params.get("school"))
        return Response({"school": school.name, **school_overview(school)})


@extend_schema(tags=["admin"], parameters=[SCHOOL_PARAM])
class RegisterExportView(ManagementView):
    """The whole register as a workbook: pupils, staff and guardians."""

    read_permission = Perm.EXPORT_RUN
    write_permission = Perm.EXPORT_RUN

    @extend_schema(
        responses={200: OpenApiResponse(description="XLSX reyestr")},
        summary="Reyestrni yuklab olish",
    )
    def get(self, request):
        from .services.export import build_register, export_filename

        school = resolve_school(request.user, request.query_params.get("school"))
        response = HttpResponse(
            build_register(school),
            content_type=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
        )
        response["Content-Disposition"] = (
            f'attachment; filename="{export_filename(school)}"'
        )
        log_action(
            AuditAction.EXPORT_REGISTER,
            user=request.user,
            request=request,
            metadata={"school": school.name},
        )
        return response
