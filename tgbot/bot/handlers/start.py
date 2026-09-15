"""/start, account linking and help."""
from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.handlers.auth import begin_sign_in
from bot.keyboards import link_prompt, main_menu
from bot.services.api import ApiError, api
from bot.states import LinkStates

logger = logging.getLogger(__name__)
router = Router(name="start")

WELCOME_LINKED = (
    "Assalomu alaykum, <b>{name}</b>! 👋\n\n"
    "Bu bot orqali farzandingizning davomatini kuzatishingiz mumkin.\n"
    "Quyidagi menyudan kerakli bo'limni tanlang."
)



HELP_TEXT = (
    "ℹ️ <b>Yordam</b>\n\n"
    "/start — botni ishga tushirish yoki tizimga kirish\n"
    "/menu — asosiy menyu\n"
    "/bugun — bugungi davomat\n"
    "/hafta — haftalik davomat\n"
    "/oy — oylik davomat\n"
    "/yil — yillik davomat\n"
    "/farzandlar — farzandlarni tanlash\n"
    "/sozlamalar — bildirishnoma sozlamalari va telefon raqami\n"
    "/help — shu yordam\n\n"
    "Savollar bo'lsa maktab ma'muriyatiga murojaat qiling."
)


def _profile(message: Message) -> dict:
    user = message.from_user
    if user is None:
        return {}
    return {
        "username": user.username or "",
        "first_name": user.first_name or "",
        "last_name": user.last_name or "",
        "language_code": user.language_code or "uz",
    }


async def _link_with_token(message: Message, state: FSMContext, token: str) -> None:
    """Redeem a one-time code or deep-link token."""
    result = await api.link(message.from_user.id, token, _profile(message))
    await state.clear()
    await message.answer(
        WELCOME_LINKED.format(name=result["user"]["full_name"]), reply_markup=main_menu()
    )


@router.message(CommandStart(deep_link=True))
async def start_with_deep_link(message: Message, command: CommandObject, state: FSMContext):
    """`https://t.me/<bot>?start=<token>` — the one-click linking path."""
    token = (command.args or "").strip()
    try:
        await _link_with_token(message, state, token)
    except ApiError as error:
        if error.code in {"INVALID_LINK_TOKEN", "NOT_FOUND"}:
            await state.set_state(LinkStates.waiting_for_code)
            await message.answer(
                "⚠️ Ulanish havolasi eskirgan yoki allaqachon ishlatilgan.\n\n"
                "Shaxsiy kabinetdan yangi kod oling va shu yerga yuboring.",
                reply_markup=link_prompt(),
            )
            return
        raise


@router.message(CommandStart())
async def start(message: Message, state: FSMContext):
    """Already linked? Straight to the menu. Otherwise offer the contact button."""
    await state.clear()
    try:
        me = await api.me(message.from_user.id)
    except ApiError as error:
        if error.not_linked:
            await begin_sign_in(message, state)
            return
        raise

    await message.answer(
        WELCOME_LINKED.format(name=me["user"]["full_name"]), reply_markup=main_menu()
    )


@router.message(LinkStates.waiting_for_code, F.text.regexp(r"^\s*\d{4,8}\s*$"))
async def receive_code(message: Message, state: FSMContext):
    try:
        await _link_with_token(message, state, message.text.strip())
    except ApiError as error:
        if error.code in {"INVALID_LINK_TOKEN", "NOT_FOUND"}:
            await message.answer(
                "❌ Kod noto'g'ri yoki muddati tugagan. Kabinetdan yangi kod oling."
            )
            return
        raise


@router.message(LinkStates.waiting_for_code)
async def waiting_for_code_fallback(message: Message):
    await message.answer(
        "Iltimos, shaxsiy kabinetdan olingan <b>6 xonali kodni</b> yuboring.",
        reply_markup=link_prompt(),
    )


@router.message(Command("help"))
async def help_command(message: Message):
    await message.answer(HELP_TEXT)


@router.message(Command("menu"))
async def menu_command(message: Message):
    await api.me(message.from_user.id)  # raises if the chat is not linked
    await message.answer("Asosiy menyu:", reply_markup=main_menu())
