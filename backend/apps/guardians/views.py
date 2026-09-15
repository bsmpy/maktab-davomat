"""Child switcher + dashboard endpoints for the parent cabinet."""
from __future__ import annotations

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.attendance.permissions import StudentScopedMixin
from apps.attendance.services import (
    build_dashboard,
    build_day_rows,
    student_card,
    totals_from_rows,
)
from apps.attendance.services.periods import DateRange, month_range, today
from apps.common.permissions import IsAuthenticatedActive

from .selectors import accessible_students, children_links


@extend_schema(tags=["children"])
class ChildrenListView(APIView):
    """Powers the child switcher: every verified child with month-to-date stats."""

    permission_classes = [IsAuthenticatedActive]

    @extend_schema(
        operation_id="children_list",
        responses={200: OpenApiResponse(description="Farzandlar va joriy oy statistikasi")},
        summary="Farzandlarim",
    )
    def get(self, request):
        user = request.user
        month = month_range(today().year, today().month)

        if user.is_parent:
            links = list(children_links(user))
            entries = [(link.student, link.relation, link.is_primary) for link in links]
        else:
            entries = [
                (student, None, False)
                for student in accessible_students(user).order_by("last_name")[:200]
            ]

        results = []
        for student, relation, is_primary in entries:
            days = build_day_rows(student, DateRange(month.start, month.end))
            totals = totals_from_rows([day for day in days if day["is_school_day"]])
            card = student_card(student, relation=relation)
            card["is_primary"] = is_primary
            card["current_month"] = totals.to_dict()
            results.append(card)

        return Response({"count": len(results), "results": results})


@extend_schema(tags=["children"])
class ChildDashboardView(StudentScopedMixin, APIView):
    """Aggregated home-screen payload — one request, no client-side fan-out."""

    @extend_schema(
        operation_id="child_dashboard",
        responses={200: OpenApiResponse(description="Dashboard uchun yig'ma ma'lumot")},
        summary="Farzand dashboardi",
    )
    def get(self, request, student_id):
        student = self.get_student()
        return Response(build_dashboard(student, request.user))


@extend_schema(tags=["children"])
class ChildDetailView(StudentScopedMixin, APIView):
    @extend_schema(
        operation_id="child_detail",
        responses={200: OpenApiResponse(description="Farzand kartochkasi")},
        summary="Farzand ma'lumotlari",
    )
    def get(self, request, student_id):
        student = self.get_student()
        relation = None
        if request.user.is_parent:
            link = children_links(request.user).filter(student_id=student.id).first()
            relation = link.relation if link else None
        return Response(student_card(student, relation=relation))
