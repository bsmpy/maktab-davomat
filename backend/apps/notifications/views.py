from __future__ import annotations

from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.permissions import IsAuthenticatedActive

from .models import Notification
from .serializers import MarkReadSerializer, NotificationSerializer


@extend_schema(
    tags=["notifications"],
    parameters=[
        OpenApiParameter("is_read", bool, description="Faqat o'qilgan/o'qilmaganlar"),
        OpenApiParameter("student", str, description="Farzand bo'yicha filtr"),
    ],
    summary="Bildirishnomalar",
)
class NotificationListView(ListAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticatedActive]

    def get_queryset(self):
        queryset = (
            Notification.objects.for_user(self.request.user).with_student().order_by("-created_at")
        )
        is_read = self.request.query_params.get("is_read")
        if is_read is not None:
            queryset = queryset.filter(is_read=is_read.lower() in {"1", "true", "yes"})
        student = self.request.query_params.get("student")
        if student:
            queryset = queryset.filter(student_id=student)
        return queryset

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        response.data["unread_count"] = Notification.objects.for_user(request.user).unread().count()
        return response


@extend_schema(
    tags=["notifications"],
    responses={200: OpenApiResponse(description="O'qilmagan bildirishnomalar soni")},
    summary="O'qilmaganlar soni",
)
class NotificationUnreadCountView(APIView):
    permission_classes = [IsAuthenticatedActive]

    def get(self, request):
        return Response(
            {"unread_count": Notification.objects.for_user(request.user).unread().count()}
        )


@extend_schema(
    tags=["notifications"],
    request=MarkReadSerializer,
    responses={200: OpenApiResponse(description="Yangilangan yozuvlar soni")},
    summary="O'qilgan deb belgilash",
)
class NotificationMarkReadView(APIView):
    permission_classes = [IsAuthenticatedActive]

    def post(self, request):
        serializer = MarkReadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = (
            Notification.objects.for_user(request.user)
            .filter(id__in=serializer.validated_data["ids"], is_read=False)
            .update(is_read=True, read_at=timezone.now())
        )
        return Response({"updated": updated})


@extend_schema(
    tags=["notifications"],
    request=None,
    responses={200: OpenApiResponse(description="Yangilangan yozuvlar soni")},
    summary="Barchasini o'qilgan deb belgilash",
)
class NotificationMarkAllReadView(APIView):
    permission_classes = [IsAuthenticatedActive]

    def post(self, request):
        updated = (
            Notification.objects.for_user(request.user)
            .unread()
            .update(is_read=True, read_at=timezone.now())
        )
        return Response({"updated": updated})
