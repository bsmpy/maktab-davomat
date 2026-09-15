"""Signing in by sharing a contact.

    /start  →  greeting + "share my number"  →  4-digit code  →  cabinet link

The number comes from Telegram's own ``request_contact`` button, so it is the
one Telegram holds for the account rather than something typed in. The code is
sent by the backend straight into this chat; the bot only forwards what the
user types back.

The password is never asked for here — anything typed into a chat stays in its
history. The bot hands over a one-time link and the browser takes it from there.
"""
from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Contact, Message

from bot.keyboards import (
    contact_request,
    main_menu,
    open_site,
    remove_keyboard,
)
from bot.services.api import ApiError, api
from bot.states import AuthStates, PhoneChangeStates

logger = logging.getLogger(__name__)
router = Router(name="auth")

GREETING = (
    "Assalomu alaykum! 👋\n\n"
    "Bu — <b>maktab davomati</b> boti. Farzandingiz maktabga qachon kirgani va "
    "qachon chiqqanini shu yerdan kuzatasiz.\n\n"
    "<b>Qanday boshlash kerak</b>\n"
    "1️⃣ Pastdagi <b>«📱 Raqamimni yuborish»</b> tugmasini bosing\n"
    "2️⃣ Saytda ro'yxatdan o'ting — tasdiqlash kodi shu yerga keladi\n"
    "3️⃣ Kodni <b>saytga</b> kiriting\n\n"
    "❗️ Faqat <b>o'z raqamingizni</b> yuboring. Boshqa odamning kontaktini "
    "yuborsangiz, ishlamaydi."
)

NOT_REGISTERED = (
    "❌ Bu raqam maktab ro'yxatida topilmadi.\n\n"
    "Maktabga qaysi raqamni bergan bo'lsangiz, o'sha raqam bilan kiring. "
    "Raqam o'zgargan bo'lsa — maktab ma'muriyatiga murojaat qiling."
)

FOREIGN_CONTACT = (
    "❗️ Bu sizning raqamingiz emas.\n\n"
    "Iltimos, <b>«📱 Raqamimni yuborish»</b> tugmasi orqali o'z raqamingizni "
    "yuboring."
)

CONTACT_ACCEPTED = (
    "✅ <b>{name}</b>, raqamingiz maktab ro'yxatida topildi.\n\n"
    "Endi <b>saytda</b> ro'yxatdan o'ting — tasdiqlash kodi shu chatga keladi, "
    "uni saytga kiritasiz.\n\n"
    "Ro'yxatdan o'tgach, bot ham avtomatik ulanadi."
)

ALREADY_REGISTERED_HINT = (
    "✅ <b>{name}</b>, raqamingiz topildi.\n\n"
    "Sizda akkaunt bor: <code>{username}</code>\n"
    "Saytga login va parolingiz bilan kiring."
)

SUCCESS = (
    "🎉 <b>Muvaffaqiyatli kirdingiz!</b>\n\n"
    "👤 Login: <code>{username}</code>\n"
    "👦 Biriktirilgan farzandlar: <b>{children}</b>\n\n"
    "Bot tayyor — pastdagi menyudan foydalaning."
)

SET_PASSWORD = (
    "\n🔐 <b>Saytga kirish uchun parol o'rnating</b>\n"
    "Quyidagi tugmani bosing — kabinet ochiladi va parol so'raydi.\n"
    "<i>Havola 5 daqiqa amal qiladi va bir marta ishlaydi.</i>"
)

OPEN_SITE = (
    "\n🌐 Saytga kirish uchun quyidagi tugmani bosing yoki login va "
    "parolingiz bilan kiring."
)


def profile_of(message: Message) -> dict:
    user = message.from_user
    if user is None:
        return {}
    return {
        "username": user.username or "",
        "first_name": user.first_name or "",
        "last_name": user.last_name or "",
        "language_code": user.language_code or "uz",
    }


def is_own_contact(message: Message, contact: Contact) -> bool:
    """Telegram tells us whose contact card this is; anyone else's is refused."""
    return bool(
        message.from_user and contact.user_id and contact.user_id == message.from_user.id
    )


async def begin_sign_in(message: Message, state: FSMContext) -> None:
    """Greet and ask for the contact, unless this chat already shared one."""
    known = await api.known_phone(message.from_user.id)
    if known.get("phone"):
        await state.clear()
        await message.answer(
            "Raqamingiz allaqachon qabul qilingan: "
            f"<b>{known['phone']}</b>\n\n"
            "Saytda ro'yxatdan o'ting yoki tizimga kiring — tasdiqlash kodi "
            "shu chatga keladi.",
            reply_markup=open_site(),
        )
        return

    await state.set_state(AuthStates.waiting_for_contact)
    await message.answer(GREETING, reply_markup=contact_request())


@router.message(AuthStates.waiting_for_contact, F.contact)
async def receive_contact(message: Message, state: FSMContext):
    """Record that this chat owns the number. The code is entered on the site."""
    contact = message.contact
    if not is_own_contact(message, contact):
        await message.answer(FOREIGN_CONTACT, reply_markup=contact_request())
        return

    try:
        result = await api.auth_contact(message.from_user.id, contact.phone_number)
    except ApiError as error:
        if error.phone_unknown:
            await state.clear()
            await message.answer(NOT_REGISTERED, reply_markup=remove_keyboard())
            return
        await message.answer(f"⚠️ {error.message}", reply_markup=remove_keyboard())
        return

    await state.clear()
    name = result.get("guardian_name", "")
    text = (
        ALREADY_REGISTERED_HINT.format(name=name, username=result.get("username") or "")
        if result.get("has_account")
        else CONTACT_ACCEPTED.format(name=name)
    )
    await message.answer(text, reply_markup=remove_keyboard())
    await message.answer("👇", reply_markup=open_site())


@router.message(AuthStates.waiting_for_contact)
async def waiting_for_contact_fallback(message: Message):
    await message.answer(
        "Iltimos, pastdagi <b>«📱 Raqamimni yuborish»</b> tugmasini bosing.",
        reply_markup=contact_request(),
    )


# --------------------------------------------------------------------------- #
# Changing the number on file
# --------------------------------------------------------------------------- #
PHONE_PROMPT = (
    "📱 <b>Telefon raqamini o'zgartirish</b>\n\n"
    "Yangi raqamingiz bilan Telegramga kiring va pastdagi tugma orqali uni "
    "yuboring. Tasdiqlash uchun <b>4 xonali kod</b> shu chatga keladi.\n\n"
    "❗️ Faqat o'z raqamingizni yuboring."
)

PHONE_CHANGED = (
    "✅ Telefon raqamingiz yangilandi: <b>{phone}</b>\n\n"
    "Endi tizim shu raqamni ishlatadi."
)


@router.callback_query(F.data == "settings:phone")
async def ask_phone_change(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if callback.message is None:
        return
    await state.set_state(PhoneChangeStates.waiting_for_contact)
    await callback.message.answer(PHONE_PROMPT, reply_markup=contact_request())


@router.message(PhoneChangeStates.waiting_for_contact, F.contact)
async def receive_new_contact(message: Message, state: FSMContext):
    contact = message.contact
    if not is_own_contact(message, contact):
        await message.answer(FOREIGN_CONTACT, reply_markup=contact_request())
        return

    try:
        result = await api.phone_change_request(
            message.from_user.id, contact.phone_number
        )
    except ApiError as error:
        await state.clear()
        await message.answer(f"❌ {error.message}", reply_markup=remove_keyboard())
        return

    await state.set_state(PhoneChangeStates.waiting_for_code)
    await state.update_data(phone=contact.phone_number)
    await message.answer(
        "Shu chatga <b>4 xonali kod</b> yubordim. Uni menga qaytaring.\n"
        f"Kod {max(int(result.get('ttl_seconds', 300)) // 60, 1)} daqiqa amal qiladi.",
        reply_markup=remove_keyboard(),
    )


@router.message(PhoneChangeStates.waiting_for_code, F.text.regexp(r"^\s*\d{4}\s*$"))
async def receive_phone_code(message: Message, state: FSMContext):
    data = await state.get_data()
    try:
        result = await api.phone_change_verify(
            message.from_user.id, data.get("phone", ""), message.text.strip()
        )
    except ApiError as error:
        if error.bad_code:
            await message.answer(f"❌ {error.message}")
            return
        raise

    await state.clear()
    await message.answer(
        PHONE_CHANGED.format(phone=result["phone"]), reply_markup=main_menu()
    )


@router.message(PhoneChangeStates.waiting_for_contact)
async def phone_contact_fallback(message: Message):
    await message.answer(
        "Iltimos, pastdagi tugma orqali yangi raqamingizni yuboring.",
        reply_markup=contact_request(),
    )


@router.message(PhoneChangeStates.waiting_for_code)
async def phone_code_fallback(message: Message):
    await message.answer("Iltimos, menga kelgan <b>4 xonali kodni</b> yuboring.")
