"""Attendance report handlers — one code path per period."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.keyboards import BTN_MONTH, BTN_TODAY, BTN_WEEK, BTN_YEAR, main_menu
from bot.services.api import api
from bot.services.formatting import format_report

router = Router(name="attendance")


async def _send_report(message: Message, period: str) -> None:
    payload = await api.attendance(message.from_user.id, period)
    await message.answer(format_report(payload), reply_markup=main_menu())


@router.message(F.text == BTN_TODAY)
@router.message(Command("bugun"))
async def daily(message: Message):
    await _send_report(message, "daily")


@router.message(F.text == BTN_WEEK)
@router.message(Command("hafta"))
async def weekly(message: Message):
    await _send_report(message, "weekly")


@router.message(F.text == BTN_MONTH)
@router.message(Command("oy"))
async def monthly(message: Message):
    await _send_report(message, "monthly")


@router.message(F.text == BTN_YEAR)
@router.message(Command("yil"))
async def yearly(message: Message):
    await _send_report(message, "yearly")
