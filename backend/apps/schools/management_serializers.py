"""Serializers for the ADMIN management screens (sinflar, guruhlar, o'quvchilar)."""
from __future__ import annotations

from datetime import datetime

from rest_framework import serializers

from apps.accounts.constants import PROVISIONABLE_ROLES
from apps.common.media import absolute_media_url
from apps.common.serializer_fields import JshshirField, PhoneField
from apps.guardians.constants import Relation

from .constants import GRADE_MAX, GRADE_MIN


# --------------------------------------------------------------------------- #
# Grades
# --------------------------------------------------------------------------- #
class GradeWriteSerializer(serializers.Serializer):
    level = serializers.IntegerField(min_value=GRADE_MIN, max_value=GRADE_MAX)
    school = serializers.UUIDField(required=False, allow_null=True)


class ManagedGradeSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    level = serializers.IntegerField(read_only=True)
    label = serializers.CharField(read_only=True)
    class_groups_count = serializers.IntegerField(read_only=True, default=0)
    students_count = serializers.IntegerField(read_only=True, default=0)


# --------------------------------------------------------------------------- #
# Class groups
# --------------------------------------------------------------------------- #
class ClassGroupWriteSerializer(serializers.Serializer):
    grade = serializers.UUIDField(required=False, allow_null=True)
    level = serializers.IntegerField(
        min_value=GRADE_MIN, max_value=GRADE_MAX, required=False, allow_null=True
    )
    name = serializers.CharField(max_length=8)
    room = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")
    school = serializers.UUIDField(required=False, allow_null=True)

    def validate(self, attrs):
        if not attrs.get("grade") and not attrs.get("level"):
            raise serializers.ValidationError(
                {"grade": "Sinf yoki sinf raqamini ko'rsating."}
            )
        return attrs

    def validate_name(self, value: str) -> str:
        name = (value or "").strip().upper()
        if not name.isalnum():
            raise serializers.ValidationError("Guruh nomi harf yoki raqamdan iborat bo'lsin.")
        return name


class ClassGroupPatchSerializer(serializers.Serializer):
    """Renaming or re-rooming a group. The grade it belongs to never moves."""

    name = serializers.CharField(max_length=8, required=False)
    room = serializers.CharField(max_length=32, required=False, allow_blank=True)

    def validate_name(self, value: str) -> str:
        name = (value or "").strip().upper()
        if not name.isalnum():
            raise serializers.ValidationError("Guruh nomi harf yoki raqamdan iborat bo'lsin.")
        return name


class ManagedClassGroupSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    name = serializers.CharField(read_only=True)
    display_name = serializers.CharField(read_only=True)
    room = serializers.CharField(read_only=True)
    grade_id = serializers.UUIDField(read_only=True)
    grade_level = serializers.IntegerField(read_only=True, source="grade.level")
    students_count = serializers.IntegerField(read_only=True, default=0)


# --------------------------------------------------------------------------- #
# Guardians attached to a pupil
# --------------------------------------------------------------------------- #
class GuardianWriteSerializer(serializers.Serializer):
    """One "yaqini" row from the + button on the pupil form.

    A row identifies an existing guardian either by ``id`` (editing: the stored
    JSHSHIR is never sent back to the browser, so it cannot be retyped) or by
    ``jshshir`` (adding: the register matches people by their identifier).
    """

    id = serializers.UUIDField(required=False, allow_null=True)
    last_name = serializers.CharField(max_length=100)
    first_name = serializers.CharField(max_length=100)
    middle_name = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    relation = serializers.ChoiceField(choices=Relation.choices)
    phone = PhoneField()
    jshshir = JshshirField(required=False, allow_blank=True, default="")
    is_primary = serializers.BooleanField(default=False)

    def validate(self, attrs):
        if not attrs.get("id") and not attrs.get("jshshir"):
            raise serializers.ValidationError(
                {"jshshir": "Yangi yaqini uchun JSHSHIR majburiy."}
            )
        return attrs


class ManagedGuardianSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    full_name = serializers.CharField(read_only=True)
    first_name = serializers.CharField(read_only=True)
    last_name = serializers.CharField(read_only=True)
    middle_name = serializers.CharField(read_only=True)
    relation = serializers.CharField(read_only=True)
    relation_label = serializers.CharField(read_only=True)
    phone = serializers.CharField(read_only=True)
    masked_jshshir = serializers.CharField(read_only=True)
    jshshir = serializers.CharField(read_only=True)
    is_primary = serializers.BooleanField(read_only=True)
    has_account = serializers.BooleanField(read_only=True)


# --------------------------------------------------------------------------- #
# Students
# --------------------------------------------------------------------------- #
class StudentWriteSerializer(serializers.Serializer):
    last_name = serializers.CharField(max_length=100)
    first_name = serializers.CharField(max_length=100)
    middle_name = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    class_group = serializers.UUIDField()
    birth_date = serializers.DateField(required=False, allow_null=True)
    gender = serializers.ChoiceField(
        choices=["MALE", "FEMALE"], required=False, allow_blank=True, default=""
    )
    student_code = serializers.CharField(
        max_length=32, required=False, allow_blank=True, default=""
    )
    guardians = GuardianWriteSerializer(many=True, required=False, default=list)

    def validate_guardians(self, value):
        seen = set()
        for entry in value:
            key = entry.get("jshshir") or str(entry.get("id"))
            if key in seen:
                raise serializers.ValidationError("Bir xil yaqini ikki marta kiritilgan.")
            seen.add(key)
        if sum(1 for entry in value if entry.get("is_primary")) > 1:
            raise serializers.ValidationError("Faqat bitta asosiy vakil bo'lishi mumkin.")
        return value


class StudentPatchSerializer(StudentWriteSerializer):
    """Same shape, everything optional — the edit form sends only what changed."""

    last_name = serializers.CharField(max_length=100, required=False)
    first_name = serializers.CharField(max_length=100, required=False)
    class_group = serializers.UUIDField(required=False)
    guardians = GuardianWriteSerializer(many=True, required=False)


class ManagedStudentSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    first_name = serializers.CharField(read_only=True)
    last_name = serializers.CharField(read_only=True)
    middle_name = serializers.CharField(read_only=True)
    full_name = serializers.CharField(read_only=True)
    display_name = serializers.CharField(read_only=True)
    initials = serializers.CharField(read_only=True)
    photo = serializers.SerializerMethodField()
    birth_date = serializers.DateField(read_only=True)
    gender = serializers.CharField(read_only=True)
    student_code = serializers.CharField(read_only=True)
    class_group = serializers.CharField(read_only=True, source="class_group.display_name")
    class_group_id = serializers.UUIDField(read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    guardians = serializers.SerializerMethodField()
    #: How many of the pupil's guardians have claimed an account.
    registered_guardians = serializers.SerializerMethodField()
    terminal = serializers.SerializerMethodField()

    def get_photo(self, student) -> str | None:
        return absolute_media_url(student.photo)

    def get_guardians(self, student) -> list[dict]:
        links = getattr(student, "_prefetched_links", None)
        if links is None:
            links = student.guardian_links.select_related("guardian").all()
        return [
            {
                "id": str(link.guardian_id),
                "link_id": str(link.id),
                "full_name": link.guardian.full_name,
                "first_name": link.guardian.first_name,
                "last_name": link.guardian.last_name,
                "middle_name": link.guardian.middle_name,
                "relation": link.relation,
                "relation_label": link.get_relation_display(),
                "phone": link.guardian.phone,
                "masked_jshshir": link.guardian.masked_jshshir,
                "jshshir": link.guardian.jshshir,
                "is_primary": link.is_primary,
                "verified": link.verified,
                "has_account": link.guardian.has_account,
            }
            for link in links
        ]

    def get_registered_guardians(self, student) -> int:
        return sum(1 for row in self.get_guardians(student) if row["has_account"])

    def get_terminal(self, student) -> dict | None:
        person = getattr(student, "terminal_person", None)
        if person is None:
            return None
        return {
            "person_code": person.person_code,
            "has_face": person.has_face,
            "sync_state": person.sync_state,
            "sync_error": person.sync_error,
            "terminals": person.synced_terminals.count(),
        }


class StudentPhotoSerializer(serializers.Serializer):
    photo = serializers.ImageField()


# --------------------------------------------------------------------------- #
# Staff accounts (Foydalanuvchilar)
# --------------------------------------------------------------------------- #
class RolesField(serializers.ListField):
    """The roles ticked on the form.

    A list, because one person is often several things at once — a teacher who
    also curates 7-A and is on the payroll as staff. Sending none is allowed
    and means "an ordinary employee": the service fills in ``STAFF`` rather
    than creating a login that can see nothing.
    """

    def __init__(self, **kwargs):
        kwargs.setdefault("child", serializers.ChoiceField(choices=PROVISIONABLE_ROLES))
        kwargs.setdefault("allow_empty", True)
        kwargs.setdefault("required", False)
        super().__init__(**kwargs)


class StaffUserWriteSerializer(serializers.Serializer):
    """Creating an account. The password is generated, never chosen here."""

    last_name = serializers.CharField(max_length=100)
    first_name = serializers.CharField(max_length=100)
    middle_name = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    #: Either spelling is accepted: ``roles`` is what the form sends now,
    #: ``role`` is the single-role shorthand older clients still use.
    roles = RolesField()
    role = serializers.ChoiceField(choices=PROVISIONABLE_ROLES, required=False)
    phone = PhoneField(required=False, allow_blank=True, default="")
    school = serializers.UUIDField(required=False, allow_null=True)

    def validate(self, attrs):
        roles = list(attrs.get("roles") or [])
        single = attrs.pop("role", None)
        if single and single not in roles:
            roles.append(single)
        attrs["roles"] = roles
        return attrs


class StaffUserPatchSerializer(serializers.Serializer):
    last_name = serializers.CharField(max_length=100, required=False)
    first_name = serializers.CharField(max_length=100, required=False)
    middle_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    #: Sent only when the roles are being changed; a patch that leaves it out
    #: leaves the role set exactly as it was.
    roles = RolesField(allow_empty=False)
    role = serializers.ChoiceField(choices=PROVISIONABLE_ROLES, required=False)
    phone = PhoneField(required=False, allow_blank=True)
    is_active = serializers.BooleanField(required=False)

    def validate(self, attrs):
        single = attrs.pop("role", None)
        if single and "roles" not in attrs:
            attrs["roles"] = [single]
        return attrs


class StaffUserSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    username = serializers.CharField(read_only=True)
    full_name = serializers.CharField(read_only=True)
    first_name = serializers.CharField(read_only=True)
    last_name = serializers.CharField(read_only=True)
    middle_name = serializers.CharField(read_only=True)
    #: The role they are working through, and every role they hold.
    role = serializers.CharField(read_only=True)
    active_role = serializers.CharField(read_only=True)
    roles = serializers.ListField(
        child=serializers.CharField(), read_only=True, source="role_codes"
    )
    role_label = serializers.CharField(read_only=True, source="get_role_display")
    phone = serializers.CharField(read_only=True, default="")
    is_active = serializers.BooleanField(read_only=True)
    #: True until the person has replaced the temporary password they were given.
    must_change_password = serializers.BooleanField(read_only=True)
    last_login = serializers.DateTimeField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    school = serializers.SerializerMethodField()
    #: Whether the caller may disable, reset or delete this particular account.
    can_manage = serializers.SerializerMethodField()
    #: Whether the row is the caller's own account.
    is_self = serializers.SerializerMethodField()
    #: Whether the caller may edit name, phone and roles — their own row included.
    can_edit = serializers.SerializerMethodField()
    #: The role the caller cannot remove from this row: their own highest one.
    locked_role = serializers.SerializerMethodField()

    def get_school(self, user) -> str | None:
        for attribute in ("teacher_profile", "staff_profile"):
            profile = getattr(user, attribute, None)
            if profile is not None:
                return str(profile.school)
        return None

    def get_can_manage(self, user) -> bool:
        from apps.accounts import rbac

        return rbac.can_manage_user(self.context.get("actor"), user)

    def get_is_self(self, user) -> bool:
        actor = self.context.get("actor")
        return actor is not None and actor.pk == user.pk

    def get_can_edit(self, user) -> bool:
        from apps.accounts import rbac

        if self.get_is_self(user):
            return rbac.can_edit_self(self.context.get("actor"))
        return self.get_can_manage(user)

    def get_locked_role(self, user) -> str | None:
        from apps.accounts import rbac

        if not self.get_is_self(user):
            return None
        return rbac._preferred_active(user.role_codes)


# --------------------------------------------------------------------------- #
# Guardians (Yaqinlar) — who has registered, and against which child
# --------------------------------------------------------------------------- #
class ManagedGuardianRowSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    full_name = serializers.CharField(read_only=True)
    phone = serializers.CharField(read_only=True)
    masked_jshshir = serializers.CharField(read_only=True)
    jshshir = serializers.CharField(read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    #: The account they registered, if they have been through the wizard.
    has_account = serializers.BooleanField(read_only=True)
    username = serializers.SerializerMethodField()
    registered_at = serializers.SerializerMethodField()
    last_login = serializers.SerializerMethodField()
    children = serializers.SerializerMethodField()

    def get_username(self, guardian) -> str | None:
        return guardian.user.username if guardian.user_id else None

    def get_registered_at(self, guardian) -> datetime | None:
        return guardian.user.created_at if guardian.user_id else None

    def get_last_login(self, guardian) -> datetime | None:
        return guardian.user.last_login if guardian.user_id else None

    def get_children(self, guardian) -> list[dict]:
        return [
            {
                "id": str(link.student_id),
                "full_name": link.student.full_name,
                "class_group": link.student.class_group.display_name,
                "relation": link.relation,
                "relation_label": link.get_relation_display(),
                "is_primary": link.is_primary,
                "verified": link.verified,
            }
            for link in guardian.student_links.all()
        ]
