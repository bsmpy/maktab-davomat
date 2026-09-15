"""Catch-all for text the bot does not understand."""
from __future__ import annotations

from aiogram import Router
from aiogram.types import Message

from bot.keyboards import main_menu
from bot.services.api import api

router = Router(name="fallback")


@router.message()
async def unknown(message: Message):
    # Raises TELEGRAM_NOT_LINKED (handled by the middleware) for unlinked chats.
    await api.me(message.from_user.id)
    await message.answer(
        "Tushunmadim 🤔\n\nQuyidagi menyudan bo'limni tanlang yoki /help buyrug'ini yuboring.",
        reply_markup=main_menu(),
    )
