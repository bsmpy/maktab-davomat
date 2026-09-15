from __future__ import annotations

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.common.crypto import mask_jshshir, mask_phone


class PasswordPairSerializer(serializers.Serializer):
    """Shared "enter + confirm password" block with full strength validation."""

    password = serializers.CharField(write_only=True, min_length=8, max_length=128, trim_whitespace=False)
    password_confirm = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({"password_confirm": ["Parollar mos kelmadi."]})
        try:
            validate_password(attrs["password"], self.context.get("user"))
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)}) from exc
        return attrs


class LoginSerializer(serializers.Serializer):
    login = serializers.CharField(
        max_length=64, help_text="Login (a.valiyev) yoki tasdiqlangan telefon raqami."
    )
    password = serializers.CharField(write_only=True, trim_whitespace=False)


class TokenResponseSerializer(serializers.Serializer):
    access = serializers.CharField()
    expires_in = serializers.IntegerField()
    csrf = serializers.CharField()


class UserSerializer(serializers.Serializer):
    """Who is signed in, and what that lets them do.

    The cabinet draws itself from this: which rail entries exist, which buttons
    render, which route a refresh lands on. None of it is trusted — every
    endpoint re-checks the same rules server-side — but all of it has to be
    here, or the browser would have to guess.
    """

    id = serializers.IntegerField(read_only=True)
    username = serializers.CharField(read_only=True)
    full_name = serializers.CharField(read_only=True)
    first_name = serializers.CharField(read_only=True)
    last_name = serializers.CharField(read_only=True)
    middle_name = serializers.CharField(read_only=True)
    #: The role being worked through right now. ``role`` and ``active_role``
    #: are the same value: the first is what older clients read, the second is
    #: what the switcher talks about.
    role = serializers.CharField(read_only=True)
    active_role = serializers.CharField(read_only=True)
    #: Every role granted to the account, most privileged first.
    roles = serializers.ListField(
        child=serializers.CharField(), read_only=True, source="role_codes"
    )
    #: Role codes are never translated — TEACHER reads as TEACHER in all three
    #: interface languages, so the label is the code.
    role_label = serializers.CharField(read_only=True, source="get_role_display")
    #: What the active role may do; the frontend's ``can()`` reads this list.
    permissions = serializers.ListField(
        child=serializers.CharField(), read_only=True, source="permission_codes"
    )
    scope = serializers.SerializerMethodField()
    #: Whether this account has a row in the teacher or staff register. The
    #: profile page is that row when there is one, and the guardian card when
    #: there is not — a platform owner with no register row would otherwise be
    #: sent to a 404.
    has_staff_record = serializers.SerializerMethodField()
    phone = serializers.SerializerMethodField()
    is_phone_verified = serializers.BooleanField(read_only=True)
    must_change_password = serializers.BooleanField(read_only=True)

    def get_phone(self, user) -> str:
        return mask_phone(user.phone)

    def get_scope(self, user) -> dict:
        from .rbac import session_scope

        return session_scope(user)

    def get_has_staff_record(self, user) -> bool:
        from .rbac import person_record

        return person_record(user) is not None


class ProfileSerializer(UserSerializer):
    """Profile page payload. JSHSHIR is only ever exposed masked."""

    masked_jshshir = serializers.SerializerMethodField()
    jshshir = serializers.SerializerMethodField()
    telegram = serializers.SerializerMethodField()
    children_count = serializers.SerializerMethodField()

    def get_jshshir(self, user) -> str:
        guardian = getattr(user, "guardian_profile", None)
        return guardian.jshshir if guardian else ""

    def get_masked_jshshir(self, user) -> str:
        guardian = getattr(user, "guardian_profile", None)
        return mask_jshshir(guardian.jshshir_last4) if guardian else mask_jshshir(None)

    def get_telegram(self, user) -> dict:
        account = getattr(user, "telegram_account", None)
        if account is None or not account.is_active:
            return {"linked": False, "username": "", "notifications_enabled": False}
        return {
            "linked": True,
            "username": account.telegram_username,
            "notifications_enabled": account.notifications_enabled,
            "linked_at": account.linked_at.isoformat(),
        }

    def get_children_count(self, user) -> int:
        guardian = getattr(user, "guardian_profile", None)
        if guardian is None:
            return 0
        return guardian.student_links.filter(verified=True).count()


class PasswordChangeSerializer(PasswordPairSerializer):
    """Changing a password, or setting the first one.

    An account created through the bot has no password at all — there is
    nothing to verify and nothing the person could type. Everyone who *has* one
    must still prove it, so the field is required exactly when it exists.
    """

    current_password = serializers.CharField(
        write_only=True, trim_whitespace=False, required=False, allow_blank=True
    )

    def validate(self, attrs):
        attrs = super().validate(attrs)
        user = self.context["user"]
        if not user.has_usable_password():
            return attrs

        current = attrs.get("current_password") or ""
        if not current:
            raise serializers.ValidationError(
                {"current_password": ["Joriy parolni kiriting."]}
            )
        if not user.check_password(current):
            raise serializers.ValidationError(
                {"current_password": ["Joriy parol noto'g'ri."]}
            )
        return attrs


class ActiveRoleSerializer(serializers.Serializer):
    """The switcher's whole request: which of my roles am I working through?"""

    role = serializers.CharField(max_length=20)


class PasswordResetRequestSerializer(serializers.Serializer):
    login = serializers.CharField(max_length=64)


class PasswordResetVerifySerializer(serializers.Serializer):
    session_token = serializers.CharField(max_length=128)
    code = serializers.CharField(max_length=12)


class PasswordResetConfirmSerializer(PasswordPairSerializer):
    session_token = serializers.CharField(max_length=128)


# --------------------------------------------------------------------------- #
# Registration
# --------------------------------------------------------------------------- #
class StudentSearchSerializer(serializers.Serializer):
    class_group = serializers.UUIDField()
    query = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    student_code = serializers.CharField(
        max_length=32, required=False, allow_blank=True, default=""
    )


class StudentSearchResultSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    display_name = serializers.CharField()
    full_name = serializers.CharField()
    class_group = serializers.CharField()
    birth_year = serializers.IntegerField(allow_null=True)
    photo = serializers.CharField(allow_null=True)
    has_registered_guardian = serializers.BooleanField()


class RegistrationIdentifySerializer(serializers.Serializer):
    from apps.guardians.constants import Relation

    student = serializers.UUIDField()
    relation = serializers.ChoiceField(choices=Relation.choices)
    jshshir = serializers.RegexField(
        r"^\d{14}$",
        write_only=True,
        error_messages={"invalid": "JSHSHIR 14 ta raqamdan iborat bo'lishi kerak."},
    )
    phone_last4 = serializers.RegexField(
        r"^\d{4}$",
        error_messages={"invalid": "Telefon raqamining oxirgi 4 ta raqamini kiriting."},
        help_text="Maktabda ro'yxatdan o'tgan telefon raqamining oxirgi 4 raqami.",
    )


class RegistrationSessionSerializer(serializers.Serializer):
    session_token = serializers.CharField()
    guardian_name = serializers.CharField()
    masked_phone = serializers.CharField()
    student_name = serializers.CharField()
    class_group = serializers.CharField()
    relation = serializers.CharField()
    phone_verified = serializers.BooleanField()


class RegistrationOTPRequestSerializer(serializers.Serializer):
    session_token = serializers.CharField(max_length=128)


class RegistrationOTPVerifySerializer(serializers.Serializer):
    session_token = serializers.CharField(max_length=128)
    code = serializers.CharField(max_length=12)


class RegistrationCompleteSerializer(PasswordPairSerializer):
    session_token = serializers.CharField(max_length=128)


class TelegramTicketSerializer(serializers.Serializer):
    """The one-time value the bot put behind its "open the cabinet" button."""

    ticket = serializers.CharField(max_length=128)
