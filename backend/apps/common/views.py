"""Small cross-cutting endpoints that belong to no single domain."""
from __future__ import annotations

import logging

from django.core.cache import cache
from django.db import connection
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.catalog import Perm
from apps.audit.constants import AuditAction
from apps.audit.services import log_action

from .clock import is_shifted, offset
from .models import AppearanceSettings
from .permissions import IsAuthenticatedActive

logger = logging.getLogger(__name__)


def _database_ok() -> bool:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        logger.exception("Health check: database unreachable")
        return False
    return True


def _cache_ok() -> bool:
    try:
        cache.set("healthcheck", "ok", 5)
        return cache.get("healthcheck") == "ok"
    except Exception:
        logger.exception("Health check: cache unreachable")
        return False


@extend_schema(tags=["common"], summary="Health probe")
class HealthCheckView(APIView):
    """Liveness for the load balancer: are the database and the cache there?

    Answers 503 the moment one of them is not, so an unhealthy replica is
    taken out of rotation rather than serving errors.
    """

    permission_classes = [AllowAny]
    authentication_classes: list = []

    def get(self, request):
        checks = {"database": _database_ok(), "cache": _cache_ok()}
        healthy = all(checks.values())
        return Response(
            {"status": "ok" if healthy else "error", "checks": checks},
            status=status.HTTP_200_OK
            if healthy
            else status.HTTP_503_SERVICE_UNAVAILABLE,
        )


@extend_schema(tags=["common"], summary="Server vaqti")
class ClockView(APIView):
    """The time the application is running on.

    Normally this is simply the wall clock. When a demo clock is configured it
    is the shifted one, and the browser follows it — otherwise the site would
    disagree with itself about which day it is.
    """

    permission_classes = [AllowAny]
    authentication_classes: list = []

    def get(self, request):
        moment = timezone.localtime(timezone.now())
        return Response(
            {
                "now": moment.isoformat(timespec="seconds"),
                "date": moment.date().isoformat(),
                "weekday": moment.isoweekday(),
                "offset_seconds": int(offset().total_seconds()),
                "is_shifted": is_shifted(),
            }
        )


class AppearanceSerializer(serializers.ModelSerializer):
    """The two switches, and nothing else — ``updated_by`` is not public."""

    class Meta:
        model = AppearanceSettings
        fields = ("multi_theme", "particles")


@extend_schema(tags=["common"], summary="Ko'rinish sozlamalari")
class AppearanceView(APIView):
    """What the interface offers everyone: the palettes, and the particles.

    **Anyone signed in may read it** — a parent's browser has to know whether
    the extra themes are on offer before it draws the theme menu, and whether
    to run the particles at all. **Only the unscoped roles may change it**, and
    a change is immediately true for every person on the installation, which is
    the whole reason it is not a browser preference any more.
    """

    permission_classes = [IsAuthenticatedActive]

    def get(self, request):
        return Response(self._payload(request, AppearanceSettings.load()))

    def patch(self, request):
        if not request.user.has_permission(Perm.SETTINGS_APPEARANCE):
            return Response(
                {"detail": "Ko'rinish sozlamalarini o'zgartirishga ruxsatingiz yo'q."},
                status=status.HTTP_403_FORBIDDEN,
            )

        row = AppearanceSettings.load()
        before = {"multi_theme": row.multi_theme, "particles": row.particles}

        serializer = AppearanceSerializer(row, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        row = serializer.save(updated_by=request.user)

        after = {"multi_theme": row.multi_theme, "particles": row.particles}
        if after != before:
            # Worth a trail: one person turning these off changes what every
            # other person sees, so "who did that?" is a question that gets
            # asked.
            log_action(
                AuditAction.APPEARANCE_UPDATE,
                entity=row,
                old_data=before,
                new_data=after,
                request=request,
            )

        return Response(self._payload(request, row))

    @staticmethod
    def _payload(request, row: AppearanceSettings) -> dict:
        """The switches plus whether this viewer is allowed to move them.

        The flag saves the client from second-guessing the role rules; the
        server still refuses a write on its own authority either way.
        """
        return {
            "multi_theme": row.multi_theme,
            "particles": row.particles,
            "can_edit": request.user.has_permission(Perm.SETTINGS_APPEARANCE),
        }
