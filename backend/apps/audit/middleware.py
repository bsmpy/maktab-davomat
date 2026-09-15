"""Makes the current request available to service-layer audit calls.

Services deep in the call stack (and Celery-free signal handlers) need the
caller's IP and user agent without threading a ``request`` argument through
every function signature.
"""
from __future__ import annotations

import contextvars

_current_request: contextvars.ContextVar = contextvars.ContextVar("current_request", default=None)


def get_current_request():
    return _current_request.get()


class RequestContextMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = _current_request.set(request)
        try:
            return self.get_response(request)
        finally:
            _current_request.reset(token)
