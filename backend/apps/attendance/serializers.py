from __future__ import annotations

from rest_framework import serializers

from .constants import AttendanceStatus
from .models import AbsenceRequest, AttendanceReason


class AttendanceReasonSerializer(serializers.ModelSerializer):
    class Meta:
        model = AttendanceReason
        fields = ("id", "code", "name", "requires_comment", "requires_document", "order")


class AbsenceRequestSerializer(serializers.ModelSerializer):
    reason_name = serializers.CharField(source="reason.name", read_only=True)
    student_name = serializers.CharField(source="student.display_name", read_only=True)
    reviewed_by_name = serializers.CharField(
        source="reviewed_by.full_name", read_only=True, default=None
    )

    class Meta:
        model = AbsenceRequest
        fields = (
            "id",
            "student",
            "student_name",
            "date",
            "reason",
            "reason_name",
            "comment",
            "status",
            "submitted_at",
            "reviewed_at",
            "reviewed_by_name",
            "review_comment",
        )
        read_only_fields = fields


class AbsenceRequestCreateSerializer(serializers.Serializer):
    date = serializers.DateField()
    reason = serializers.UUIDField()
    comment = serializers.CharField(max_length=1000, required=False, allow_blank=True, default="")


class AbsenceRequestReviewSerializer(serializers.Serializer):
    comment = serializers.CharField(max_length=1000, required=False, allow_blank=True, default="")


# --------------------------------------------------------------------------- #
# Lesson attendance (Dars davomati)
# --------------------------------------------------------------------------- #
class LessonMarkSerializer(serializers.Serializer):
    """One pupil's row in the register. A blank status clears the mark."""

    student = serializers.UUIDField()
    status = serializers.ChoiceField(
        choices=AttendanceStatus.choices, required=False, allow_null=True, allow_blank=True
    )
    late_minutes = serializers.IntegerField(required=False, min_value=0, max_value=600)
    comment = serializers.CharField(
        max_length=255, required=False, allow_blank=True, default=""
    )


class LessonMarksWriteSerializer(serializers.Serializer):
    date = serializers.DateField()
    marks = serializers.ListField(child=LessonMarkSerializer(), allow_empty=False)


class LessonRosterStudentSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    full_name = serializers.CharField(read_only=True)
    display_name = serializers.CharField(read_only=True)
    initials = serializers.CharField(read_only=True)
    photo = serializers.CharField(read_only=True, allow_null=True)
    status = serializers.CharField(read_only=True, allow_null=True)
    status_label = serializers.CharField(read_only=True)
    late_minutes = serializers.IntegerField(read_only=True)
    comment = serializers.CharField(read_only=True)


class TeachingSubjectSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    name = serializers.CharField(read_only=True)
    display_name = serializers.CharField(read_only=True)
    class_group = serializers.UUIDField(read_only=True)
    class_group_name = serializers.CharField(read_only=True)
    grade_level = serializers.IntegerField(read_only=True)
    students_count = serializers.IntegerField(read_only=True)
    marked_count = serializers.IntegerField(read_only=True)
    teachers = serializers.ListField(child=serializers.CharField(), read_only=True)
