"""The 'I'm interested' button on profile cards.

Tapping it records the interest, bumps the live counter on the card, and DMs
the profile owner so they can reach out. Deduped per (owner, viewer).
"""
from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    User,
)

from keyboards.interest_kb import interest_kb
from repositories.interest_repo import InterestRepository
from repositories.profile_repo import ProfileRepository
from utils.formatters import esc

log = logging.getLogger(__name__)
router = Router(name="interest")


def _mention(user: User) -> str:
    """Clickable reference to a user that works inside HTML message text."""
    if user.username:
        return f"@{user.username}"
    return f'<a href="tg://user?id={user.id}">{esc(user.full_name)}</a>'


@router.callback_query(F.data.startswith("interest:"))
async def cb_interest(
    cb: CallbackQuery,
    bot: Bot,
    interest_repo: InterestRepository,
    profile_repo: ProfileRepository,
) -> None:
    owner_id = int(cb.data.split(":", 1)[1])
    viewer = cb.from_user

    if viewer.id == owner_id:
        await cb.answer("That's your own profile 🙂")
        return

    is_new = await interest_repo.add(owner_id, viewer.id)
    if not is_new:
        await cb.answer("You already showed interest 👌")
        return

    # Refresh the live counter on the card.
    count = await interest_repo.count(owner_id)
    try:
        await cb.message.edit_reply_markup(reply_markup=interest_kb(owner_id, count))
    except Exception as e:
        log.debug("Could not update interest counter: %s", e)

    # Notify the owner in DM (best-effort).
    owner = await profile_repo.get_by_user_id(owner_id)
    dest = owner.destination if owner else "your trip"
    notified = await _notify_owner(bot, owner_id, viewer, dest)

    if notified:
        await cb.answer("Sent! The traveller was notified 🎉", show_alert=True)
    else:
        await cb.answer(
            "Interest saved! They haven't opened the bot yet — "
            "reach out via the contact shown in their card.",
            show_alert=True,
        )


async def _notify_owner(bot: Bot, owner_id: int, viewer: User, dest: str) -> bool:
    text = (
        f"🎉 <b>{_mention(viewer)}</b> is interested in your <b>{esc(dest)}</b> trip!\n\n"
        "Tap to say hi 👇"
    )
    kb = None
    if viewer.username:
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text="💬 Message them", url=f"https://t.me/{viewer.username}"
            )
        ]])
    try:
        await bot.send_message(
            chat_id=owner_id, text=text, reply_markup=kb,
            disable_web_page_preview=True,
        )
        return True
    except Exception as e:
        log.info("Could not notify owner %s: %s", owner_id, e)
        return False
