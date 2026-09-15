"""School structure management for the ADMIN cabinet.

Grades, class groups and pupils are *soft* deleted, always: a school's history
(who passed the turnstile, when) must survive an administrator removing a
parallel that has finished. Deleting grade 11 therefore retires the grade, its
class groups and the pupils in them — and every one of those rows can be
restored, because nothing is ever removed from the database.

Removing a pupil also pulls them off the access terminals, so a pupil who has
left the school cannot open the turnstile the next morning.
"""
from __future__ import annotations

import logging

from django.db import transaction

from apps.accounts.constants import Role
from apps.common.exceptions import ConflictError, NotFoundError

from ..models import ClassGroup, Grade, School

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Scope
# --------------------------------------------------------------------------- #
def accessible_schools(user):
    """Schools the user may work in.

    DEVELOPER, SUPER_ADMIN and MODERATOR are never scoped — the first two run
    the platform, the third only watches it. Everybody else is pinned to the
    school their register row belongs to; an administrator who has no row yet
    is mid-setup rather than untrusted, so they get the only school there is
    instead of an empty list they could never escape.
    """
    from apps.accounts.rbac import user_school_ids

    queryset = School.objects.filter(is_active=True)
    if user.role in Role.unrestricted_roles():
        return queryset

    school_ids = user_school_ids(user)
    if not school_ids:
        return queryset
    return queryset.filter(id__in=school_ids)


def resolve_school(user, school_id=None) -> School:
    """The school a management write applies to.

    Asking for a school that is not yours is a 404 — indistinguishable from one
    that does not exist, as everywhere else. Having no school *at all* is a
    different thing: it is the first step of setting the platform up, so it
    says so instead of pretending the record is missing.
    """
    schools = accessible_schools(user)
    if school_id:
        school = schools.filter(pk=school_id).first()
        if school is None:
            raise NotFoundError("Maktab topilmadi.", code="SCHOOL_NOT_FOUND")
        return school
    school = schools.first()
    if school is None:
        raise ConflictError(
            "Avval maktab yarating: Boshqaruv → Maktab.", code="SCHOOL_MISSING"
        )
    return school


def current_academic_year(school):
    from ..models import AcademicYear

    return (
        AcademicYear.objects.filter(school=school, is_current=True).first()
        or AcademicYear.objects.filter(school=school).order_by("-start_date").first()
    )


# --------------------------------------------------------------------------- #
# Grades
# --------------------------------------------------------------------------- #
@transaction.atomic
def create_grade(*, school, level: int) -> Grade:
    if Grade.objects.filter(school=school, level=level).exists():
        raise ConflictError(f"{level}-sinf allaqachon mavjud.", code="GRADE_EXISTS")

    # A grade deleted earlier is revived rather than duplicated, so its class
    # groups and pupils can be restored alongside it.
    retired = Grade.all_objects.filter(school=school, level=level).first()
    if retired is not None:
        retired.restore()
        return retired
    return Grade.objects.create(school=school, level=level)


@transaction.atomic
def delete_grade(grade: Grade) -> dict:
    """Retire a whole parallel: the grade, its class groups and their pupils."""
    groups = list(ClassGroup.objects.filter(grade=grade))
    students = 0
    for group in groups:
        students += delete_class_group(group)["students"]
    grade.delete()
    return {"grade": grade.level, "class_groups": len(groups), "students": students}


# --------------------------------------------------------------------------- #
# Class groups
# --------------------------------------------------------------------------- #
@transaction.atomic
def create_class_group(*, school, grade: Grade, name: str, academic_year=None, room: str = ""):
    academic_year = academic_year or current_academic_year(school)
    if academic_year is None:
        raise ConflictError(
            "Avval o'quv yilini yarating.", code="ACADEMIC_YEAR_MISSING"
        )
    name = (name or "").strip().upper()
    if not name:
        raise ConflictError("Guruh nomini kiriting.", code="NAME_REQUIRED")

    existing = ClassGroup.all_objects.filter(
        grade=grade, academic_year=academic_year, name__iexact=name
    ).first()
    if existing is not None:
        if existing.deleted_at is None:
            raise ConflictError(
                f"{grade.level}-{name} guruhi allaqachon mavjud.", code="CLASS_GROUP_EXISTS"
            )
        existing.restore()
        return existing

    return ClassGroup.objects.create(
        school=school, grade=grade, academic_year=academic_year, name=name, room=room
    )


@transaction.atomic
def delete_class_group(group: ClassGroup) -> dict:
    """Retire a group and everyone in it, and unenrol them from the devices."""
    from apps.students.models import Student

    students = list(Student.objects.filter(class_group=group))
    for student in students:
        retire_student(student)
    group.delete()
    return {"class_group": group.display_name, "students": len(students)}


# --------------------------------------------------------------------------- #
# Students
# --------------------------------------------------------------------------- #
@transaction.atomic
def retire_student(student) -> None:
    """Soft-delete a pupil and take them off every access terminal."""
    student.is_active = False
    student.save(update_fields=["is_active", "updated_at"])
    student.delete()  # soft delete — attendance history survives

    def _unenroll():
        from apps.integrations.tasks import remove_student_from_terminals

        remove_student_from_terminals.delay(str(student.id))

    transaction.on_commit(_unenroll)


@transaction.atomic
def restore_student(student) -> None:
    student.restore()
    student.is_active = True
    student.save(update_fields=["is_active", "updated_at"])
