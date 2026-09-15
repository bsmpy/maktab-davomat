from __future__ import annotations

from rest_framework import serializers

from .models import AcademicYear, ClassGroup, Grade, School, Subject, Teacher


class SchoolSerializer(serializers.ModelSerializer):
    class Meta:
        model = School
        fields = ("id", "name", "short_name", "region", "district")


class GradeSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(read_only=True)
    class_groups_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Grade
        fields = ("id", "level", "display_name", "school", "class_groups_count")


class ClassGroupSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(read_only=True)
    grade_level = serializers.IntegerField(source="grade.level", read_only=True)

    class Meta:
        model = ClassGroup
        fields = ("id", "name", "display_name", "grade", "grade_level", "school", "room")


class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = ("id", "name", "short_name", "color")


class TeacherSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    short_display = serializers.CharField(read_only=True)

    class Meta:
        model = Teacher
        fields = ("id", "full_name", "short_display")


class AcademicYearSerializer(serializers.ModelSerializer):
    class Meta:
        model = AcademicYear
        fields = ("id", "name", "start_date", "end_date", "is_current")
