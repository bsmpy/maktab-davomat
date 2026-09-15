from __future__ import annotations

from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(
        source="student.display_name", read_only=True, default=None
    )
    student_class = serializers.CharField(
        source="student.class_group.display_name", read_only=True, default=None
    )

    class Meta:
        model = Notification
        fields = (
            "id",
            "type",
            "title",
            "message",
            "payload",
            "is_read",
            "read_at",
            "created_at",
            "student",
            "student_name",
            "student_class",
        )
        read_only_fields = fields


class MarkReadSerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.UUIDField(), allow_empty=False)
