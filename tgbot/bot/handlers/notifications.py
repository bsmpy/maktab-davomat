"""Notification list and per-chat settings."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.keyboards import (
    BTN_NOTIFICATIONS,
    BTN_SETTINGS,
    confirm_unlink_keyboard,
    main_menu,
    remove_keyboard,
    settings_keyboard,
)
from bot.services.api import api
from bot.services.formatting import format_notifications

router = Router(name="notifications")


@router.message(F.text == BTN_NOTIFICATIONS)
@router.message(Command("bildirishnomalar"))
async def notifications(message: Message):
    payload = await api.notifications(message.from_user.id, limit=8)
    await message.answer(format_notifications(payload), reply_markup=main_menu())


@router.message(F.text == BTN_SETTINGS)
@router.message(Command("sozlamalar"))
async def settings(message: Message):
    me = await api.me(message.from_user.id)
    enabled = me.get("notifications_enabled", True)
    await message.answer(
        "⚙️ <b>Sozlamalar</b>\n\n"
        f"Bildirishnomalar: <b>{'yoqilgan' if enabled else 'o‘chirilgan'}</b>\n"
        f"Akkaunt: <b>{me['user']['username']}</b>",
        reply_markup=settings_keyboard(enabled),
    )


@router.callback_query(F.data == "settings:toggle")
async def toggle_notifications(callback: CallbackQuery):
    me = await api.me(callback.from_user.id)
    enabled = not me.get("notifications_enabled", True)
    await api.set_notifications(callback.from_user.id, enabled)

    await callback.answer("Bildirishnomalar yoqildi" if enabled else "Bildirishnomalar o'chirildi")
    if callback.message:
        await callback.message.edit_text(
            "⚙️ <b>Sozlamalar</b>\n\n"
            f"Bildirishnomalar: <b>{'yoqilgan' if enabled else 'o‘chirilgan'}</b>\n"
            f"Akkaunt: <b>{me['user']['username']}</b>",
            reply_markup=settings_keyboard(enabled),
        )


@router.callback_query(F.data == "settings:unlink")
async def ask_unlink(callback: CallbackQuery):
    await callback.answer()
    if callback.message:
        await callback.message.answer(
            "Akkauntni uzsangiz, bu chatga bildirishnomalar kelmaydi. Davom etamizmi?",
            reply_markup=confirm_unlink_keyboard(),
        )


@router.callback_query(F.data == "unlink:yes")
async def do_unlink(callback: CallbackQuery):
    await api.unlink(callback.from_user.id)
    await callback.answer("Uzildi")
    if callback.message:
        await callback.message.edit_text(
            "🔌 Akkaunt uzildi.\n\nQayta ulash uchun kabinetdan yangi kod oling va /start bosing."
        )
        await callback.message.answer("Botdan chiqdingiz.", reply_markup=remove_keyboard())


@router.callback_query(F.data == "unlink:no")
async def cancel_unlink(callback: CallbackQuery):
    await callback.answer("Bekor qilindi")
    if callback.message:
        await callback.message.edit_text("Bekor qilindi. Akkaunt ulangan holicha qoldi.")
