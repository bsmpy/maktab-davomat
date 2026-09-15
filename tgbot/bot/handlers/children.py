"""Child switcher: which pupil the bot's answers are about."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.keyboards import BTN_CHILDREN, children_keyboard, main_menu
from bot.services.api import api
from bot.services.formatting import format_children, format_report

router = Router(name="children")


@router.message(F.text == BTN_CHILDREN)
@router.message(Command("farzandlar"))
async def list_children(message: Message):
    payload = await api.children(message.from_user.id)
    children = payload.get("results", [])
    await message.answer(
        format_children(children, payload.get("active_student_id")),
        reply_markup=children_keyboard(children, payload.get("active_student_id")),
    )


@router.callback_query(F.data.startswith("child:"))
async def choose_child(callback: CallbackQuery):
    student_id = (callback.data or "").split(":", 1)[1]
    result = await api.set_active_child(callback.from_user.id, student_id)
    student = result["active_student"]

    await callback.answer(f"{student['display_name']} tanlandi")

    if callback.message:
        payload = await api.children(callback.from_user.id)
        children = payload.get("results", [])
        await callback.message.edit_text(
            format_children(children, student["id"]),
            reply_markup=children_keyboard(children, student["id"]),
        )
        report = await api.attendance(callback.from_user.id, "daily")
        await callback.message.answer(format_report(report), reply_markup=main_menu())
