"""Unified API error envelope.

Every failure leaves the API in exactly one shape::

    {
      "success": false,
      "error": {"code": "INVALID_OTP", "message": "...", "fields": {}}
    }

Internal tracebacks are never propagated to clients.
"""
from __future__ import annotations

import logging
import uuid

from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)


class AppError(APIException):
    """Base class for domain errors carrying a stable machine-readable code."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "BAD_REQUEST"
    default_detail = "So'rovni bajarib bo'lmadi."

    def __init__(self, message: str | None = None, *, code: str | None = None, fields=None):
        self.code = code or self.default_code
        self.fields = fields or {}
        super().__init__(message or self.default_detail)


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    default_code = "NOT_FOUND"
    default_detail = "Ma'lumot topilmadi."


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    default_code = "CONFLICT"
    default_detail = "Amalni bajarib bo'lmadi."


class PermissionError_(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    default_code = "FORBIDDEN"
    default_detail = "Bu amal uchun ruxsat yo'q."


class ThrottledError(AppError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_code = "TOO_MANY_REQUESTS"
    default_detail = "Juda ko'p urinish. Birozdan so'ng qayta urinib ko'ring."


_STATUS_CODES = {
    400: "BAD_REQUEST",
    401: "UNAUTHENTICATED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    415: "UNSUPPORTED_MEDIA_TYPE",
    429: "TOO_MANY_REQUESTS",
    500: "INTERNAL_ERROR",
}


def _flatten_validation_detail(detail) -> tuple[str, dict]:
    """Split DRF's nested validation detail into a message + per-field map."""
    if isinstance(detail, dict):
        fields = {}
        for key, value in detail.items():
            if isinstance(value, (list, tuple)):
                fields[key] = [str(item) for item in value]
            elif isinstance(value, dict):
                _, nested = _flatten_validation_detail(value)
                fields[key] = nested or [str(value)]
            else:
                fields[key] = [str(value)]
        non_field = fields.get("non_field_errors") or fields.get("detail")
        message = non_field[0] if non_field else "Kiritilgan ma'lumotlarda xatolik bor."
        return message, fields
    if isinstance(detail, (list, tuple)):
        items = [str(item) for item in detail]
        return (items[0] if items else "Xatolik yuz berdi."), {}
    return str(detail), {}


def _as_otp_error(exc):
    """OTP failures are user errors, not crashes.

    They were caught view by view, so any endpoint that forgot to do it
    answered a cooldown with a 500. Mapping them centrally means a new caller
    cannot get it wrong.
    """
    from apps.common.otp import OTPCooldownError, OTPError

    if not isinstance(exc, OTPError):
        return None

    status_code = (
        status.HTTP_429_TOO_MANY_REQUESTS
        if isinstance(exc, OTPCooldownError)
        else status.HTTP_400_BAD_REQUEST
    )
    mapped = AppError(str(exc), code=exc.code)
    mapped.status_code = status_code
    return mapped


def error_response(code: str, message: str, *, fields=None, status_code: int = 400) -> Response:
    return Response(
        {"success": False, "error": {"code": code, "message": message, "fields": fields or {}}},
        status=status_code,
    )


def api_exception_handler(exc, context):
    if isinstance(exc, Http404):
        exc = NotFoundError()
    elif isinstance(exc, PermissionDenied):
        exc = PermissionError_()
    elif isinstance(exc, DjangoValidationError):
        exc = ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages)
    else:
        exc = _as_otp_error(exc) or exc

    response = drf_exception_handler(exc, context)

    if response is None:
        # Unhandled exception: log with a correlation id, return an opaque 500.
        incident = uuid.uuid4().hex[:12]
        logger.exception("Unhandled API exception [incident=%s]", incident)
        return error_response(
            "INTERNAL_ERROR",
            f"Ichki xatolik yuz berdi. Murojaat kodi: {incident}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    if isinstance(exc, AppError):
        code, fields = exc.code, exc.fields
        message = str(exc.detail)
    elif isinstance(exc, ValidationError):
        code = "VALIDATION_ERROR"
        message, fields = _flatten_validation_detail(exc.detail)
    else:
        code = getattr(exc, "default_code", None) or _STATUS_CODES.get(
            response.status_code, "ERROR"
        )
        code = str(code).upper()
        message, fields = _flatten_validation_detail(response.data)

    response.data = {
        "success": False,
        "error": {"code": code, "message": message, "fields": fields},
    }
    return response
