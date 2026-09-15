"""Structured update logging that never records message contents.

A linking message contains a one-time code, so only metadata is logged.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        started = time.perf_counter()
        kind = "unknown"
        user_id = None

        if isinstance(event, Message):
            kind = "message"
            user_id = event.from_user.id if event.from_user else None
        elif isinstance(event, CallbackQuery):
            kind = f"callback:{(event.data or '').split(':')[0]}"
            user_id = event.from_user.id if event.from_user else None

        try:
            return await handler(event, data)
        finally:
            logger.info(
                "handled %s user=%s in %.0fms", kind, user_id, (time.perf_counter() - started) * 1000
            )
