"""Entry point for the aiogram bot.

    python main.py

Architecture: Telegram → aiogram → Django REST API → PostgreSQL.
The bot holds no database credentials and no business logic; it renders what
the API returns.
"""
from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import config
from bot.handlers import build_router
from bot.middlewares import ErrorMiddleware, LoggingMiddleware
from bot.services.api import api

logger = logging.getLogger(__name__)

COMMANDS = [
    ("start", "Botni ishga tushirish"),
    ("menu", "Asosiy menyu"),
    ("bugun", "Bugungi davomat"),
    ("hafta", "Haftalik davomat"),
    ("oy", "Oylik davomat"),
    ("yil", "Yillik davomat"),
    ("farzandlar", "Farzandlarim"),
    ("bildirishnomalar", "Bildirishnomalar"),
    ("sozlamalar", "Sozlamalar"),
    ("help", "Yordam"),
]


def build_storage():
    """Redis-backed FSM when configured, so several bot replicas share state."""
    if not config.redis_url:
        logger.warning("REDIS_URL is not set — using in-memory FSM storage (single instance only).")
        return MemoryStorage()
    try:
        from aiogram.fsm.storage.redis import RedisStorage

        return RedisStorage.from_url(config.redis_url)
    except Exception as exc:  # pragma: no cover - optional dependency/connection
        logger.warning("Redis storage unavailable (%s) — falling back to memory.", exc)
        return MemoryStorage()


async def on_startup(bot: Bot) -> None:
    from aiogram.types import BotCommand

    await bot.set_my_commands(
        [BotCommand(command=name, description=description) for name, description in COMMANDS]
    )
    me = await bot.get_me()
    logger.info("Bot started as @%s (api=%s)", me.username, config.api_url)


async def on_shutdown() -> None:
    await api.close()
    logger.info("Bot stopped")


async def main() -> None:
    logging.basicConfig(
        level=config.log_level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        stream=sys.stdout,
    )

    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dispatcher = Dispatcher(storage=build_storage())

    # Outermost so it also catches errors raised inside other middlewares.
    dispatcher.update.outer_middleware(LoggingMiddleware())
    dispatcher.message.middleware(ErrorMiddleware())
    dispatcher.callback_query.middleware(ErrorMiddleware())

    dispatcher.include_router(build_router())
    dispatcher.startup.register(on_startup)
    dispatcher.shutdown.register(on_shutdown)

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dispatcher.start_polling(bot, allowed_updates=dispatcher.resolve_used_update_types())
    finally:
        await bot.session.close()
        await api.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Interrupted")
