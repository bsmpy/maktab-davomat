"""Bot configuration, loaded from the environment only."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env", override=False)


class ConfigError(Exception):
    pass


def _env(name: str, default: str | None = None, *, required: bool = False) -> str:
    value = os.environ.get(name, default)
    if required and not value:
        raise ConfigError(f"Missing required environment variable: {name}")
    return value or ""


@dataclass(frozen=True)
class Config:
    bot_token: str
    bot_username: str
    api_url: str
    service_token: str
    frontend_url: str
    redis_url: str
    http_timeout: int
    log_level: str

    @property
    def api_base(self) -> str:
        return f"{self.api_url}/api/v1"


def load_config() -> Config:
    return Config(
        bot_token=_env("BOT_TOKEN", required=True),
        bot_username=_env("BOT_USERNAME"),
        api_url=_env("BACKEND_API_URL", "http://127.0.0.1:8000").rstrip("/"),
        service_token=_env("BOT_SERVICE_TOKEN", required=True),
        frontend_url=_env("FRONTEND_URL", "http://localhost:5173").rstrip("/"),
        redis_url=_env("REDIS_URL"),
        http_timeout=int(_env("HTTP_TIMEOUT", "15")),
        log_level=_env("LOG_LEVEL", "INFO"),
    )


config = load_config()
