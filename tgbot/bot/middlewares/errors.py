"""Turns backend/API failures into a friendly reply instead of a silent drop."""
from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from bot.keyboards import link_prompt
from bot.services.api import ApiError

logger = logging.getLogger(__name__)

NOT_LINKED_TEXT = (
    "🔐 Bu Telegram akkaunt hech qaysi foydalanuvchiga ulanmagan.\n\n"
    "Shaxsiy kabinetga kiring → <b>Profil</b> → <b>Telegram ulash</b> tugmasini bosing "
    "va olingan 6 xonali kodni shu yerga yuboring."
)

NO_CHILDREN_TEXT = (
    "Sizga hali biror o'quvchi biriktirilmagan. "
    "Iltimos, maktab ma'muriyatiga murojaat qiling."
)


class ErrorMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        try:
            return await handler(event, data)
        except ApiError as error:
            await self._reply(event, error)
        except Exception:  # pragma: no cover - last resort
            logger.exception("Unhandled error while processing an update")
            await self._reply(
                event,
                ApiError("INTERNAL", "Kutilmagan xatolik yuz berdi. Qayta urinib ko'ring."),
            )

    async def _reply(self, event: TelegramObject, error: ApiError) -> None:
        if error.not_linked:
            text, markup = NOT_LINKED_TEXT, link_prompt()
        elif error.no_children:
            text, markup = NO_CHILDREN_TEXT, None
        else:
            text, markup = f"⚠️ {error.message}", None

        if isinstance(event, Message):
            await event.answer(text, reply_markup=markup)
        elif isinstance(event, CallbackQuery):
            await event.answer()
            if event.message:
                await event.message.answer(text, reply_markup=markup)
