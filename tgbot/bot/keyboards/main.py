"""Reply and inline keyboards."""
from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from bot.config import config

BTN_TODAY = "📊 Bugungi davomat"
BTN_WEEK = "📅 Haftalik davomat"
BTN_MONTH = "📈 Oylik davomat"
BTN_YEAR = "📆 Yillik davomat"
BTN_CHILDREN = "👦 Farzandlarim"
BTN_NOTIFICATIONS = "🔔 Bildirishnomalar"
BTN_SETTINGS = "⚙️ Sozlamalar"


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_TODAY), KeyboardButton(text=BTN_WEEK)],
            [KeyboardButton(text=BTN_MONTH), KeyboardButton(text=BTN_YEAR)],
            [KeyboardButton(text=BTN_CHILDREN), KeyboardButton(text=BTN_NOTIFICATIONS)],
            [KeyboardButton(text=BTN_SETTINGS)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Bo'limni tanlang…",
    )


def remove_keyboard() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()


def link_prompt() -> InlineKeyboardMarkup:
    """Shown to a chat that has not been linked to an account yet."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🌐 Shaxsiy kabinetni ochish", url=config.frontend_url)]
        ]
    )


def children_keyboard(children: list[dict], active_id: str | None) -> InlineKeyboardMarkup:
    rows = []
    for child in children:
        icon = "✅" if child["id"] == active_id else "👤"
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{icon} {child['display_name']} · {child['class_group']}",
                    callback_data=f"child:{child['id']}",
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def settings_keyboard(notifications_enabled: bool) -> InlineKeyboardMarkup:
    toggle_text = (
        "🔕 Bildirishnomalarni o'chirish"
        if notifications_enabled
        else "🔔 Bildirishnomalarni yoqish"
    )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=toggle_text, callback_data="settings:toggle")],
            [
                InlineKeyboardButton(
                    text="📱 Telefon raqamini o'zgartirish",
                    callback_data="settings:phone",
                )
            ],
            [InlineKeyboardButton(text="🌐 Shaxsiy kabinet", url=config.frontend_url)],
            [InlineKeyboardButton(text="🔌 Akkauntni uzish", callback_data="settings:unlink")],
        ]
    )


def confirm_unlink_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Ha, uzilsin", callback_data="unlink:yes"),
                InlineKeyboardButton(text="Bekor qilish", callback_data="unlink:no"),
            ]
        ]
    )


BTN_SHARE_CONTACT = "📱 Raqamimni yuborish"


def contact_request() -> ReplyKeyboardMarkup:
    """Telegram's own contact button.

    ``request_contact`` returns the number Telegram itself holds for the
    account, so the user cannot type someone else's in.
    """
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=BTN_SHARE_CONTACT, request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
        input_field_placeholder="Raqamingizni yuboring…",
    )


def open_cabinet(url: str) -> InlineKeyboardMarkup:
    """One-time sign-in link — the password is set in the browser, not here."""
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔓 Kabinetni ochish", url=url)]]
    )


def open_site() -> InlineKeyboardMarkup:
    """Codes are typed on the website, so that is where the bot points."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🌐 Saytga o'tish", url=config.frontend_url)]
        ]
    )


def resend_code() -> InlineKeyboardMarkup:
    """Offered next to the code prompt so a lost code is one tap away."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Kodni qayta yuborish", callback_data="auth:resend")]
        ]
    )
