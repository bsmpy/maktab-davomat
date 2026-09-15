"""Public catalogue endpoints.

The registration wizard needs grades and class groups *before* the applicant
has an account, so these are anonymous — but they expose nothing personal: only
the structure of the school (1-A, 1-B, ...), never a pupil.
"""
from __future__ import annotations

from django.db.models import Count, Q
from drf_spectacular.utils import extend_schema
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny

from apps.common.throttling import RegistrationThrottle

from .models import AcademicYear, ClassGroup, Grade, School
from .serializers import (
    AcademicYearSerializer,
    ClassGroupSerializer,
    GradeSerializer,
    SchoolSerializer,
)


class PublicCatalogueView(ListAPIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_classes = [RegistrationThrottle]
    pagination_class = None


@extend_schema(tags=["catalogue"], summary="Maktablar ro'yxati")
class SchoolListView(PublicCatalogueView):
    serializer_class = SchoolSerializer
    queryset = School.objects.filter(is_active=True)


@extend_schema(tags=["catalogue"], summary="Sinflar (1-11)")
class GradeListView(PublicCatalogueView):
    serializer_class = GradeSerializer

    def get_queryset(self):
        queryset = (
            Grade.objects.filter(school__is_active=True, school__deleted_at__isnull=True)
            .annotate(
                class_groups_count=Count(
                    "class_groups",
                    filter=Q(class_groups__is_active=True, class_groups__deleted_at__isnull=True),
                )
            )
            .order_by("level")
        )
        school = self.request.query_params.get("school")
        if school:
            queryset = queryset.filter(school_id=school)
        return queryset


@extend_schema(tags=["catalogue"], summary="Sinf guruhlari (masalan 7-A)")
class ClassGroupListView(PublicCatalogueView):
    serializer_class = ClassGroupSerializer

    def get_queryset(self):
        queryset = (
            ClassGroup.objects.filter(is_active=True)
            .select_related("grade")
            .order_by("grade__level", "name")
        )
        grade = self.request.query_params.get("grade")
        level = self.request.query_params.get("level")
        school = self.request.query_params.get("school")
        if grade:
            queryset = queryset.filter(grade_id=grade)
        if level:
            queryset = queryset.filter(grade__level=level)
        if school:
            queryset = queryset.filter(school_id=school)
        return queryset


@extend_schema(tags=["catalogue"], summary="O'quv yillari")
class AcademicYearListView(PublicCatalogueView):
    serializer_class = AcademicYearSerializer
    queryset = AcademicYear.objects.all()
