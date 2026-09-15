from __future__ import annotations

from rest_framework import serializers

from .constants import IntegrationKind, TerminalDirection, TerminalVendor
from .models import DailyPresence, Integration, Terminal, TerminalEvent, TerminalPerson


class IntegrationSerializer(serializers.ModelSerializer):
    """Read view. Secrets are only ever reported as ``••••••1234``."""

    kind_display = serializers.CharField(source="get_kind_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    effective_status = serializers.CharField(read_only=True)
    secrets = serializers.SerializerMethodField()
    school_name = serializers.CharField(source="school.short_name", read_only=True, default=None)

    class Meta:
        model = Integration
        fields = (
            "id",
            "kind",
            "kind_display",
            "school",
            "school_name",
            "is_enabled",
            "config",
            "secrets",
            "status",
            "status_display",
            "effective_status",
            "last_checked_at",
            "last_error",
            "updated_at",
        )
        read_only_fields = ("status", "last_checked_at", "last_error", "updated_at")

    def get_secrets(self, obj) -> dict:
        return obj.masked_secrets()


class IntegrationUpdateSerializer(serializers.Serializer):
    """Write view. Sending a secret as ``""`` keeps it; ``null`` clears it."""

    is_enabled = serializers.BooleanField(required=False)
    config = serializers.DictField(required=False)
    secrets = serializers.DictField(
        required=False,
        child=serializers.CharField(allow_blank=True, allow_null=True, trim_whitespace=False),
        help_text="Faqat o'zgartirilgan maydonlarni yuboring.",
    )


class TerminalSerializer(serializers.ModelSerializer):
    direction_display = serializers.CharField(source="get_direction_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    school_name = serializers.CharField(source="school.short_name", read_only=True)
    base_url = serializers.CharField(read_only=True)
    has_password = serializers.SerializerMethodField()
    enrolled_count = serializers.SerializerMethodField()
    events_today = serializers.SerializerMethodField()
    ingest_url = serializers.SerializerMethodField()

    class Meta:
        model = Terminal
        fields = (
            "id",
            "school",
            "school_name",
            "name",
            "vendor",
            "model",
            "serial_number",
            "host",
            "port",
            "use_https",
            "username",
            "has_password",
            "direction",
            "direction_display",
            "location",
            "is_active",
            "base_url",
            "ingest_url",
            "firmware",
            "status",
            "status_display",
            "last_error",
            "last_seen_at",
            "last_event_at",
            "last_polled_at",
            "enrolled_count",
            "events_today",
            "created_at",
        )
        read_only_fields = (
            "serial_number",
            "firmware",
            "status",
            "last_error",
            "last_seen_at",
            "last_event_at",
            "last_polled_at",
            "created_at",
        )

    def get_has_password(self, obj) -> bool:
        return bool(obj.secret("password"))

    def get_enrolled_count(self, obj) -> int:
        return obj.enrolled_people.count()

    def get_events_today(self, obj) -> int:
        from apps.attendance.services.periods import today

        return obj.events.filter(date=today()).count()

    def get_ingest_url(self, obj) -> str:
        """Paste this into the device's HTTP Listening notification settings."""
        from django.conf import settings

        return f"{settings.BACKEND_URL}/api/v1/terminals/events/{obj.ingest_token}/"


class TerminalWriteSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True, required=False, allow_blank=True, trim_whitespace=False,
        help_text="Bo'sh qoldirilsa — joriy parol saqlanib qoladi.",
    )

    class Meta:
        model = Terminal
        fields = (
            "school",
            "name",
            "vendor",
            "model",
            "host",
            "port",
            "use_https",
            "username",
            "password",
            "direction",
            "location",
            "is_active",
        )

    def create(self, validated_data):
        password = validated_data.pop("password", "")
        terminal = Terminal(**validated_data)
        if password:
            terminal.set_secrets({"password": password})
        terminal.save()
        return terminal

    def update(self, instance, validated_data):
        password = validated_data.pop("password", "")
        for field, value in validated_data.items():
            setattr(instance, field, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class TerminalEventSerializer(serializers.ModelSerializer):
    terminal_name = serializers.CharField(source="terminal.name", read_only=True)
    student_name = serializers.CharField(
        source="student.display_name", read_only=True, default=None
    )
    student_class = serializers.CharField(
        source="student.class_group.display_name", read_only=True, default=None
    )
    direction_display = serializers.CharField(source="get_direction_display", read_only=True)
    verify_mode_display = serializers.CharField(source="get_verify_mode_display", read_only=True)

    class Meta:
        model = TerminalEvent
        fields = (
            "id",
            "terminal",
            "terminal_name",
            "occurred_at",
            "date",
            "direction",
            "direction_display",
            "verify_mode",
            "verify_mode_display",
            "person_code",
            "person_name",
            "student",
            "student_name",
            "student_class",
            "processed",
        )
        read_only_fields = fields


class DailyPresenceSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.display_name", read_only=True)
    student_class = serializers.CharField(
        source="student.class_group.display_name", read_only=True
    )
    duration_minutes = serializers.IntegerField(read_only=True)

    class Meta:
        model = DailyPresence
        fields = (
            "id",
            "student",
            "student_name",
            "student_class",
            "date",
            "first_in_at",
            "last_out_at",
            "entries_count",
            "exits_count",
            "inside_minutes",
            "outside_minutes",
            "is_inside",
            "sessions",
            "late_minutes",
            "left_early",
            "duration_minutes",
            "source",
        )
        read_only_fields = fields


class TerminalPersonSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.display_name", read_only=True)
    student_class = serializers.CharField(
        source="student.class_group.display_name", read_only=True
    )
    has_photo = serializers.SerializerMethodField()

    class Meta:
        model = TerminalPerson
        fields = (
            "id",
            "student",
            "student_name",
            "student_class",
            "person_code",
            "card_no",
            "has_face",
            "has_photo",
            "face_synced_at",
            "sync_state",
            "sync_error",
        )
        read_only_fields = ("has_face", "face_synced_at", "sync_state", "sync_error")

    def get_has_photo(self, obj) -> bool:
        return bool(obj.student.photo)


class TerminalTestSerializer(serializers.Serializer):
    """Ad-hoc connection test for a device that has not been saved yet."""

    host = serializers.CharField(max_length=255)
    port = serializers.IntegerField(min_value=1, max_value=65535, default=80)
    use_https = serializers.BooleanField(default=False)
    username = serializers.CharField(max_length=64, default="admin")
    password = serializers.CharField(trim_whitespace=False)


class EnrollSerializer(serializers.Serializer):
    """Who to push onto the devices.

    ``all`` has to be asked for by name: an empty body is still rejected, so a
    stray POST cannot enrol the whole school by accident.
    """

    students = serializers.ListField(child=serializers.UUIDField(), required=False, default=list)
    class_group = serializers.UUIDField(required=False, allow_null=True, default=None)
    all = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs):
        if not attrs.get("students") and not attrs.get("class_group") and not attrs.get("all"):
            raise serializers.ValidationError(
                "O'quvchilar ro'yxati, sinf guruhi yoki 'all' ni ko'rsating."
            )
        return attrs


class SyncEventsSerializer(serializers.Serializer):
    """Manual backfill from the device's own log."""

    start = serializers.DateTimeField()
    end = serializers.DateTimeField(required=False, allow_null=True, default=None)


class RecomputeSerializer(serializers.Serializer):
    date = serializers.DateField()
    class_group = serializers.UUIDField(required=False, allow_null=True, default=None)
    school = serializers.UUIDField(required=False, allow_null=True, default=None)


AVAILABLE_KINDS = [
    {"value": kind.value, "label": kind.label} for kind in IntegrationKind
]
TERMINAL_DIRECTIONS = [
    {"value": choice.value, "label": choice.label} for choice in TerminalDirection
]
TERMINAL_VENDORS = [{"value": choice.value, "label": choice.label} for choice in TerminalVendor]
