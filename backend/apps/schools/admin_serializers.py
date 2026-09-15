"""Serializers for the admin console (Maktab, o'quv yili, fanlar, import, audit)."""
from __future__ import annotations

import uuid

from rest_framework import serializers

from apps.common.serializer_fields import JshshirField, PassportIdField, PhoneField

from .constants import Weekday
from .models import StaffGender


# --------------------------------------------------------------------------- #
# School
# --------------------------------------------------------------------------- #
class SchoolWriteSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    short_name = serializers.CharField(max_length=64, required=False, allow_blank=True)
    region = serializers.CharField(max_length=120, required=False, allow_blank=True)
    district = serializers.CharField(max_length=120, required=False, allow_blank=True)
    address = serializers.CharField(max_length=255, required=False, allow_blank=True)
    phone = PhoneField(required=False, allow_blank=True)
    #: ISO weekdays the school is open. Everything outside them is a weekend and
    #: never counts against a pupil.
    working_weekdays = serializers.ListField(
        child=serializers.ChoiceField(choices=Weekday.choices),
        required=False,
        allow_empty=False,
    )
    is_active = serializers.BooleanField(required=False)

    def validate_working_weekdays(self, value):
        return sorted(set(value))


class ManagedSchoolSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    name = serializers.CharField(read_only=True)
    short_name = serializers.CharField(read_only=True)
    region = serializers.CharField(read_only=True)
    district = serializers.CharField(read_only=True)
    address = serializers.CharField(read_only=True)
    phone = serializers.CharField(read_only=True)
    working_weekdays = serializers.ListField(read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    students_count = serializers.IntegerField(read_only=True, default=0)
    class_groups_count = serializers.IntegerField(read_only=True, default=0)


# --------------------------------------------------------------------------- #
# Academic years
# --------------------------------------------------------------------------- #
class AcademicYearWriteSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=32)
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    is_current = serializers.BooleanField(required=False, default=False)
    school = serializers.UUIDField(required=False, allow_null=True)

    def validate(self, attrs):
        start, end = attrs.get("start_date"), attrs.get("end_date")
        if start and end and end <= start:
            raise serializers.ValidationError(
                {"end_date": "Tugash sanasi boshlanish sanasidan keyin bo'lishi kerak."}
            )
        return attrs


class ManagedAcademicYearSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    name = serializers.CharField(read_only=True)
    start_date = serializers.DateField(read_only=True)
    end_date = serializers.DateField(read_only=True)
    is_current = serializers.BooleanField(read_only=True)


# --------------------------------------------------------------------------- #
# Holidays
# --------------------------------------------------------------------------- #
class HolidayWriteSerializer(serializers.Serializer):
    date = serializers.DateField()
    name = serializers.CharField(max_length=150)
    #: A working Saturday: the date is listed but still counts as a school day.
    is_working_day = serializers.BooleanField(required=False, default=False)
    academic_year = serializers.UUIDField(required=False, allow_null=True)
    school = serializers.UUIDField(required=False, allow_null=True)


class ManagedHolidaySerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    date = serializers.DateField(read_only=True)
    name = serializers.CharField(read_only=True)
    is_working_day = serializers.BooleanField(read_only=True)
    academic_year = serializers.CharField(read_only=True, source="academic_year.name")


# --------------------------------------------------------------------------- #
# Subjects
# --------------------------------------------------------------------------- #
class SubjectWriteSerializer(serializers.Serializer):
    #: The class group the subject is taught to, e.g. 1-A.
    class_group = serializers.UUIDField(required=False, allow_null=True)
    name = serializers.CharField(max_length=120)
    short_name = serializers.CharField(max_length=32, required=False, allow_blank=True)
    color = serializers.CharField(max_length=9, required=False, allow_blank=True)
    is_active = serializers.BooleanField(required=False)
    school = serializers.UUIDField(required=False, allow_null=True)


class ManagedSubjectSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    name = serializers.CharField(read_only=True)
    #: ``Matematika 1-A`` — what every list and picker shows.
    display_name = serializers.CharField(read_only=True)
    class_group = serializers.UUIDField(read_only=True, source="class_group_id")
    class_group_name = serializers.SerializerMethodField()
    grade_level = serializers.SerializerMethodField()
    short_name = serializers.CharField(read_only=True)
    color = serializers.CharField(read_only=True)
    is_active = serializers.BooleanField(read_only=True)

    def get_class_group_name(self, subject) -> str:
        return subject.class_group.display_name if subject.class_group_id else ""

    def get_grade_level(self, subject) -> int | None:
        return subject.class_group.grade.level if subject.class_group_id else None


# --------------------------------------------------------------------------- #
# Teachers
# --------------------------------------------------------------------------- #
class TeacherWriteSerializer(serializers.Serializer):
    """Fields are declared in the order the form presents them."""

    first_name = serializers.CharField(max_length=100)
    last_name = serializers.CharField(max_length=100)
    middle_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    passport_id = PassportIdField(required=False, allow_blank=True)
    #: Write-only: what comes back is the masked form, never the number itself.
    jshshir = JshshirField(required=False, allow_blank=True, write_only=True)
    birth_date = serializers.DateField(required=False, allow_null=True)
    gender = serializers.ChoiceField(
        choices=StaffGender.choices, required=False, allow_blank=True
    )
    phone = PhoneField(required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    #: Uploaded like a pupil's, and pushed to the turnstile the same way.
    photo = serializers.ImageField(required=False, allow_null=True)
    subjects = serializers.ListField(child=serializers.UUIDField(), required=False)
    is_active = serializers.BooleanField(required=False)
    school = serializers.UUIDField(required=False, allow_null=True)

    # Cabinet credentials, asked for at the foot of the form. All three go
    # together: either an account is created or none of them is sent.
    username = serializers.CharField(max_length=50, required=False, allow_blank=True)
    password = serializers.CharField(
        max_length=128, required=False, allow_blank=True, write_only=True
    )
    password_confirm = serializers.CharField(
        max_length=128, required=False, allow_blank=True, write_only=True
    )

    def validate(self, attrs):
        username = (attrs.get("username") or "").strip()
        password = attrs.get("password") or ""
        confirm = attrs.get("password_confirm") or ""

        if password and password != confirm:
            raise serializers.ValidationError(
                {"password_confirm": "Parollar mos kelmadi."}
            )
        if username and not password:
            raise serializers.ValidationError({"password": "Parolni kiriting."})
        if password and not username:
            raise serializers.ValidationError({"username": "Loginni kiriting."})

        roles = [role for role in (attrs.get("roles") or []) if role]
        single = (attrs.pop("role", "") or "").strip()
        if single and single not in roles:
            roles.append(single)
        if roles or "roles" in attrs:
            attrs["roles"] = roles

        attrs["username"] = username
        attrs.pop("password_confirm", None)
        return attrs


class ManagedTeacherSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    full_name = serializers.CharField(read_only=True)
    first_name = serializers.CharField(read_only=True)
    last_name = serializers.CharField(read_only=True)
    middle_name = serializers.CharField(read_only=True)
    passport_id = serializers.CharField(read_only=True)
    masked_jshshir = serializers.CharField(read_only=True)
    jshshir = serializers.CharField(read_only=True)
    #: Lets the form show the field as filled without exposing the number.
    has_jshshir = serializers.SerializerMethodField()
    birth_date = serializers.DateField(read_only=True)
    gender = serializers.CharField(read_only=True)
    gender_label = serializers.CharField(read_only=True, source="get_gender_display")
    phone = serializers.CharField(read_only=True)
    email = serializers.CharField(read_only=True)
    photo = serializers.SerializerMethodField()
    is_active = serializers.BooleanField(read_only=True)
    #: The login they use, when a staff account has been provisioned for them.
    username = serializers.SerializerMethodField()
    subjects = serializers.SerializerMethodField()

    def get_has_jshshir(self, teacher) -> bool:
        return bool(teacher.jshshir_last4)

    def get_photo(self, teacher) -> str | None:
        from apps.common.media import absolute_media_url

        return absolute_media_url(teacher.photo)

    def get_username(self, teacher) -> str | None:
        return teacher.user.username if teacher.user_id else None

    def get_subjects(self, teacher) -> list[dict]:
        return [
            {
                "id": str(subject.id),
                "name": subject.name,
                "display_name": subject.display_name,
            }
            for subject in teacher.subjects.all()
        ]


# --------------------------------------------------------------------------- #
# Excel import
# --------------------------------------------------------------------------- #
class ImportRequestSerializer(serializers.Serializer):
    file = serializers.FileField()
    #: False previews the whole workbook without writing a single row.
    commit = serializers.BooleanField(required=False, default=False)
    academic_year = serializers.UUIDField(required=False, allow_null=True)
    school = serializers.UUIDField(required=False, allow_null=True)


# --------------------------------------------------------------------------- #
# Audit
# --------------------------------------------------------------------------- #
class AuditLogSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    action = serializers.CharField(read_only=True)
    action_label = serializers.CharField(read_only=True, source="get_action_display")
    username = serializers.CharField(read_only=True)
    entity_type = serializers.CharField(read_only=True)
    entity_id = serializers.CharField(read_only=True)
    ip_address = serializers.IPAddressField(read_only=True)
    success = serializers.BooleanField(read_only=True)
    metadata = serializers.JSONField(read_only=True)
    old_data = serializers.JSONField(read_only=True)
    new_data = serializers.JSONField(read_only=True)


# --------------------------------------------------------------------------- #
# Dars jadvali
# --------------------------------------------------------------------------- #
class ScheduleEntryWriteSerializer(serializers.Serializer):
    """One lesson slot. The lesson number is derived from the times."""

    class_group = serializers.UUIDField()
    weekday = serializers.ChoiceField(choices=Weekday.choices)
    subject = serializers.UUIDField()
    #: Optional: defaults to the teacher already attached to the subject.
    teacher = serializers.UUIDField(required=False, allow_null=True)
    start_time = serializers.TimeField()
    end_time = serializers.TimeField()
    room = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")


class ScheduleEntrySerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    weekday = serializers.IntegerField(read_only=True)
    weekday_label = serializers.CharField(read_only=True)
    lesson_number = serializers.IntegerField(read_only=True)
    start_time = serializers.CharField(read_only=True)
    end_time = serializers.CharField(read_only=True)
    room = serializers.CharField(read_only=True)
    subject = serializers.UUIDField(read_only=True)
    subject_name = serializers.CharField(read_only=True)
    subject_display = serializers.CharField(read_only=True)
    teacher = serializers.UUIDField(read_only=True, allow_null=True)
    teacher_name = serializers.CharField(read_only=True)


# --------------------------------------------------------------------------- #
# Positions — a job title in the three interface languages
# --------------------------------------------------------------------------- #
class PositionWriteSerializer(serializers.Serializer):
    """A position is only its name, written once per language.

    Uzbek is required because it is the fallback every other language reads
    when its own column is empty; the other two may be filled in later.
    """

    title_uz = serializers.CharField(max_length=120)
    title_ru = serializers.CharField(max_length=120, required=False, allow_blank=True)
    title_en = serializers.CharField(max_length=120, required=False, allow_blank=True)
    school = serializers.UUIDField(required=False, allow_null=True)


class ManagedPositionSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    title_uz = serializers.CharField(read_only=True)
    title_ru = serializers.CharField(read_only=True)
    title_en = serializers.CharField(read_only=True)
    #: All three at once, so a client can label a row in whichever language it
    #: is running in without asking again.
    titles = serializers.DictField(read_only=True)
    staff_count = serializers.IntegerField(read_only=True, default=0)


# --------------------------------------------------------------------------- #
# Staff — the same person fields as a teacher, with a position instead of fans
# --------------------------------------------------------------------------- #
class StaffWriteSerializer(serializers.Serializer):
    """Fields are declared in the order the form presents them."""

    first_name = serializers.CharField(max_length=100)
    last_name = serializers.CharField(max_length=100)
    middle_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    passport_id = PassportIdField(required=False, allow_blank=True)
    #: Write-only: what comes back is the masked form, never the number itself.
    jshshir = JshshirField(required=False, allow_blank=True, write_only=True)
    birth_date = serializers.DateField(required=False, allow_null=True)
    gender = serializers.ChoiceField(
        choices=StaffGender.choices, required=False, allow_blank=True
    )
    phone = PhoneField(required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    photo = serializers.ImageField(required=False, allow_null=True)
    #: What they do. Optional: the person is entered first and labelled after,
    #: and plenty of rows stay unlabelled for a while. ``null`` clears it, and
    #: so does an empty string — a browser form sends one for "nothing chosen",
    #: and refusing it as a malformed UUID is a 400 nobody can act on.
    position = serializers.CharField(required=False, allow_null=True, allow_blank=True)

    def validate_position(self, value):
        if not value:
            return None
        try:
            return str(uuid.UUID(str(value)))
        except (ValueError, AttributeError, TypeError):
            raise serializers.ValidationError("Lavozim noto'g'ri ko'rsatilgan.") from None
    is_active = serializers.BooleanField(required=False)
    school = serializers.UUIDField(required=False, allow_null=True)

    #: The access roles their cabinet account holds. Optional in the same way a
    #: position is: most of the staff never sign in at all. One person may hold
    #: several — a teacher who also curates a class — so the form sends a list,
    #: and ``role`` remains as the single-value spelling. DEVELOPER is on
    #: neither list: the server refuses it however it is asked for.
    role = serializers.CharField(max_length=20, required=False, allow_blank=True)
    roles = serializers.ListField(
        child=serializers.CharField(max_length=20), required=False, allow_empty=True
    )

    # Cabinet credentials, asked for at the foot of the form. All three go
    # together: either an account is created or none of them is sent.
    username = serializers.CharField(max_length=50, required=False, allow_blank=True)
    password = serializers.CharField(
        max_length=128, required=False, allow_blank=True, write_only=True
    )
    password_confirm = serializers.CharField(
        max_length=128, required=False, allow_blank=True, write_only=True
    )

    def validate(self, attrs):
        username = (attrs.get("username") or "").strip()
        password = attrs.get("password") or ""
        confirm = attrs.get("password_confirm") or ""

        if password and password != confirm:
            raise serializers.ValidationError(
                {"password_confirm": "Parollar mos kelmadi."}
            )
        if username and not password:
            raise serializers.ValidationError({"password": "Parolni kiriting."})
        if password and not username:
            raise serializers.ValidationError({"username": "Loginni kiriting."})

        roles = [role for role in (attrs.get("roles") or []) if role]
        single = (attrs.pop("role", "") or "").strip()
        if single and single not in roles:
            roles.append(single)
        if roles or "roles" in attrs:
            attrs["roles"] = roles

        attrs["username"] = username
        attrs.pop("password_confirm", None)
        return attrs


class ManagedStaffSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    full_name = serializers.CharField(read_only=True)
    first_name = serializers.CharField(read_only=True)
    last_name = serializers.CharField(read_only=True)
    middle_name = serializers.CharField(read_only=True)
    passport_id = serializers.CharField(read_only=True)
    masked_jshshir = serializers.CharField(read_only=True)
    jshshir = serializers.CharField(read_only=True)
    #: Lets the form show the field as filled without exposing the number.
    has_jshshir = serializers.SerializerMethodField()
    birth_date = serializers.DateField(read_only=True)
    gender = serializers.CharField(read_only=True)
    gender_label = serializers.CharField(read_only=True, source="get_gender_display")
    phone = serializers.CharField(read_only=True)
    email = serializers.CharField(read_only=True)
    photo = serializers.SerializerMethodField()
    is_active = serializers.BooleanField(read_only=True)
    username = serializers.SerializerMethodField()
    position = serializers.SerializerMethodField()
    #: The access roles of their account, when they have one at all. ``role``
    #: is the one they are working through; ``roles`` is everything they hold.
    role = serializers.SerializerMethodField()
    roles = serializers.SerializerMethodField()
    role_label = serializers.SerializerMethodField()

    def get_has_jshshir(self, staff) -> bool:
        return bool(staff.jshshir_last4)

    def get_role(self, staff) -> str | None:
        return staff.user.role if staff.user_id else None

    def get_roles(self, staff) -> list[str]:
        return staff.user.role_codes if staff.user_id else []

    def get_role_label(self, staff) -> str | None:
        return staff.user.get_role_display() if staff.user_id else None

    def get_photo(self, staff) -> str | None:
        from apps.common.media import absolute_media_url

        return absolute_media_url(staff.photo)

    def get_username(self, staff) -> str | None:
        return staff.user.username if staff.user_id else None

    def get_position(self, staff) -> dict | None:
        """The position with every translation, so the client labels it itself."""
        if staff.position_id is None:
            return None
        return {
            "id": str(staff.position_id),
            "title_uz": staff.position.title_uz,
            "title_ru": staff.position.title_ru,
            "title_en": staff.position.title_en,
            "titles": staff.position.titles,
        }
