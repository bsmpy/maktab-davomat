"""Absolute URLs for uploaded files.

``FileField.url`` is a path — ``/media/students/…`` — which is fine when the
API and the pages share an origin. They do not have to: when the SPA is served
from one host and the files from another, a relative path resolves against the
wrong host, hits the SPA's catch-all route and comes back as ``index.html``
with a 200. The browser then has HTML where it expected a JPEG and simply shows
a broken image.

Every photo URL that leaves the API therefore goes through here.
"""
from __future__ import annotations

from django.conf import settings


def absolute_media_url(field) -> str | None:
    """``student.photo`` → ``http://192.168.0.100/media/…``, or ``None``."""
    if not field:
        return None

    url = field.url
    if url.startswith(("http://", "https://")):
        return url
    return f"{settings.BACKEND_URL.rstrip('/')}{url}"
