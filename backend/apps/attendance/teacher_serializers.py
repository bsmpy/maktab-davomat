"""Write surface for the teacher's own profile."""
from __future__ import annotations

from rest_framework import serializers

from apps.common.serializer_fields import JshshirField, PassportIdField, PhoneField
from apps.schools.models import StaffGender


class TeacherProfileWriteSerializer(serializers.Serializer):
    """What a teacher may change about themselves.

    Not their login, not their subjects and not their school — those belong to
    the administrator. The password is optional and write-only: it is only
    present when the form's "Parolni o'zgartirish" box was ticked.
    """

    first_name = serializers.CharField(max_length=100, required=False)
    last_name = serializers.CharField(max_length=100, required=False)
    middle_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    birth_date = serializers.DateField(required=False, allow_null=True)
    passport_id = PassportIdField(required=False, allow_blank=True)
    jshshir = JshshirField(required=False, allow_blank=True, write_only=True)
    gender = serializers.ChoiceField(
        choices=StaffGender.choices, required=False, allow_blank=True
    )
    phone = PhoneField(required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    photo = serializers.ImageField(required=False, allow_null=True)

    password = serializers.CharField(
        max_length=128, required=False, allow_blank=True, write_only=True
    )
    password_confirm = serializers.CharField(
        max_length=128, required=False, allow_blank=True, write_only=True
    )

    def validate(self, attrs):
        password = attrs.get("password") or ""
        confirm = attrs.get("password_confirm") or ""
        if password and password != confirm:
            raise serializers.ValidationError({"password_confirm": "Parollar mos kelmadi."})
        if confirm and not password:
            raise serializers.ValidationError({"password": "Yangi parolni kiriting."})
        return attrs
