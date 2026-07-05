"""Helper to bounce group commands into a private chat with the bot.

Commands like /profile, /search, /myprofile run a multi-step wizard or reveal
personal data — they belong in DM, not the group. When a user runs one in the
group we reply with a deep-link button and (best-effort) delete their command
so the topic stays clean.
"""
from __future__ import annotations

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message


def is_private(message: Message) -> bool:
    return message.chat.type == "private"


async def redirect_to_dm(
    message: Message,
    bot: Bot,
    bot_username: str,
    payload: str,
    button_text: str,
    hint: str,
) -> None:
    """Reply with a t.me deep-link button, then delete the group command."""
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text=button_text,
            url=f"https://t.me/{bot_username}?start={payload}",
        )
    ]])
    await message.answer(hint, reply_markup=kb)
    try:
        await bot.delete_message(message.chat.id, message.message_id)
    except Exception:
        pass  # bot may lack delete rights or message already gone
