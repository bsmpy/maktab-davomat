"""Log filter that scrubs credentials before anything reaches a handler."""
from __future__ import annotations

import logging
import re

_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # 14-digit JSHSHIR / PINFL
    (re.compile(r"\b\d{14}\b"), "[JSHSHIR]"),
    # Bearer / JWT
    (re.compile(r"\beyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+"), "[JWT]"),
    # key=value style secrets
    (
        re.compile(
            r"(?i)\b(password|passwd|pwd|otp|otp_code|code|token|secret|authorization|api_key)"
            r"(\"?\s*[:=]\s*\"?)([^\s,&\"'}]+)"
        ),
        r"\1\2[REDACTED]",
    ),
]


def redact(text: str) -> str:
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:  # pragma: no cover - malformed record
            return True
        cleaned = redact(message)
        if cleaned != message:
            record.msg = cleaned
            record.args = ()
        return True
