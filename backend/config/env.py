"""Tiny typed helpers around ``os.environ`` + ``.env`` loading.

Everything configurable lives in the environment; nothing secret is ever
hardcoded in the settings modules.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env", override=False)


class ImproperlyConfigured(Exception):
    pass


_UNSET = object()


def env(name: str, default=_UNSET) -> str:
    value = os.environ.get(name, _UNSET)
    if value is _UNSET:
        if default is _UNSET:
            raise ImproperlyConfigured(f"Missing required environment variable: {name}")
        return default
    return value


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return int(raw)


def env_list(name: str, default: list[str] | None = None) -> list[str]:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return list(default or [])
    return [item.strip() for item in raw.split(",") if item.strip()]
