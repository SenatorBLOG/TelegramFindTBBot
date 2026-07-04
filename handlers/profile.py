"""Profile wizard (9 steps) + /myprofile + /deleteprofile.

The wizard runs only in private chat with the bot.
If a user types /profile in the group they get a deep-link redirect button instead.
Step 10 (contact) is removed — the bot auto-generates it from the user's Telegram account.
"""
from __future__ import annotations

import logging
from datetime import datetime
from html import escape
from typing import Optional

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    User,
)

from constants import DATE_RANGE_DISPLAY
from keyboards.profile_kb import (
    get_budget_kb,
    get_dates_kb,
    get_delete_confirm_kb,
    get_destination_kb,
    get_skip_photo_kb,
    get_style_kb,
)
from models import UserProfile
from services.profile_service import ProfileService
from states.profile_states import ProfileFSM
from utils.formatters import format_profile
from utils.rate_limiter import RateLimiter

log = logging.getLogger(__name__)
router = Router(name="profile")
_limiter = RateLimiter(max_calls=8, window_seconds=20.0)


def _auto_contact(user: User) -> str:
    """Build a contact string from Telegram user data (never asks the user for it).

    full_name is HTML-escaped because it renders inside a parse_mode=HTML card.
    """
    if user.username:
        return f"@{user.username}"
    return f'<a href="tg://user?id={user.id}">{escape(user.full_name)}</a>'


# ─────────── /profile ───────────

@router.message(Command("profile"))
async def cmd_profile(
    message: Message, state: FSMContext, bot_username: str
) -> None:
    if message.chat.type != "private":
        # Redirect to DM via deep link
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text="📝 Open profile wizard",
                url=f"https://t.me/{bot_username}?start=profile",
            )
        ]])
        await message.answer(
            "👆 Tap the button to fill in your profile in a private chat with the bot.",
            reply_markup=kb,
        )
        return

    if not _limiter.allow(message.from_user.id):
        await message.answer("⏳ Slow down a bit, please try again in a few seconds.")
        return
    await _begin_wizard(message, state)


async def _begin_wizard(message: Message, state: FSMContext) -> None:
    """Start the profile wizard (called from /profile and deep-link /start)."""
    await state.clear()
    await state.set_state(ProfileFSM.name)
    await message.answer(
        "📝 <b>Let's build your profile</b> (you can /cancel any time).\n\n"
        "<b>Step 1/9:</b> What's your name or nickname?"
    )


# ─────────── steps 1–3 (name, from, destination) ───────────

@router.message(ProfileFSM.name, F.text)
async def step_name(message: Message, state: FSMContext) -> None:
    name = message.text.strip()[:64]
    if not name:
        await message.answer("Please type a valid name.")
        return
    await state.update_data(name=name)
    await state.set_state(ProfileFSM.from_location)
    await message.answer("<b>Step 2/9:</b> Where are you from? (city or country)")


@router.message(ProfileFSM.from_location, F.text)
async def step_from(message: Message, state: FSMContext) -> None:
    await state.update_data(from_location=message.text.strip()[:64])
    await state.set_state(ProfileFSM.destination)
    await message.answer(
        "<b>Step 3/9:</b> Where are you going?",
        reply_markup=get_destination_kb(),
    )


@router.callback_query(ProfileFSM.destination, F.data.startswith("dest:"))
async def step_destination_cb(cb: CallbackQuery, state: FSMContext) -> None:
    value = cb.data.split(":", 1)[1]
    await cb.answer()
    if value == "manual":
        await cb.message.answer("✏️ Type the destination:")
        return
    await state.update_data(destination=value)
    await state.set_state(ProfileFSM.dates)
    await cb.message.answer(
        "<b>Step 4/9:</b> When are you going?",
        reply_markup=get_dates_kb(),
    )


@router.message(ProfileFSM.destination, F.text)
async def step_destination_text(message: Message, state: FSMContext) -> None:
    await state.update_data(destination=message.text.strip()[:64])
    await state.set_state(ProfileFSM.dates)
    await message.answer(
        "<b>Step 4/9:</b> When are you going?",
        reply_markup=get_dates_kb(),
    )


# ─────────── step 4: dates ───────────

@router.callback_query(ProfileFSM.dates, F.data.startswith("pdate:"))
async def step_dates_cb(cb: CallbackQuery, state: FSMContext) -> None:
    value = cb.data.split(":", 1)[1]
    await cb.answer()
    if value == "manual":
        await cb.message.answer('✏️ Type specific dates (e.g. "June 2025"):')
        return
    label = DATE_RANGE_DISPLAY.get(value, value)
    await state.update_data(dates=label, date_range=value)
    await state.set_state(ProfileFSM.budget)
    await cb.message.answer("<b>Step 5/9:</b> What's your budget?", reply_markup=get_budget_kb())


@router.message(ProfileFSM.dates, F.text)
async def step_dates_text(message: Message, state: FSMContext) -> None:
    await state.update_data(dates=message.text.strip()[:64], date_range="flexible")
    await state.set_state(ProfileFSM.budget)
    await message.answer("<b>Step 5/9:</b> What's your budget?", reply_markup=get_budget_kb())


# ─────────── steps 5–7 (budget, style, language) ───────────

@router.callback_query(ProfileFSM.budget, F.data.startswith("budget:"))
async def step_budget(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    await state.update_data(budget=cb.data.split(":", 1)[1])
    await state.set_state(ProfileFSM.style)
    await cb.message.answer("<b>Step 6/9:</b> Travel style?", reply_markup=get_style_kb())


@router.callback_query(ProfileFSM.style, F.data.startswith("style:"))
async def step_style(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    await state.update_data(style=cb.data.split(":", 1)[1])
    await state.set_state(ProfileFSM.language)
    await cb.message.answer(
        '<b>Step 7/9:</b> What languages do you speak? (e.g. "English, Russian")'
    )


@router.message(ProfileFSM.language, F.text)
async def step_language(message: Message, state: FSMContext) -> None:
    await state.update_data(language=message.text.strip()[:64])
    await state.set_state(ProfileFSM.bio)
    await message.answer('<b>Step 8/9:</b> Short bio / about you. Send "-" to skip.')


# ─────────── step 8: bio ───────────

@router.message(ProfileFSM.bio, F.text)
async def step_bio(message: Message, state: FSMContext) -> None:
    bio = "" if message.text.strip() == "-" else message.text.strip()[:500]
    await state.update_data(bio=bio)
    await state.set_state(ProfileFSM.photo)
    await message.answer(
        "<b>Step 9/9:</b> 📸 Send a profile photo, or skip.",
        reply_markup=get_skip_photo_kb(),
    )


# ─────────── step 9: photo → finalize (contact auto-generated) ───────────

@router.message(ProfileFSM.photo, F.photo)
async def step_photo(
    message: Message,
    state: FSMContext,
    bot: Bot,
    profile_service: ProfileService,
    moderation: bool,
    admin_user_id: int,
) -> None:
    file_id = message.photo[-1].file_id
    await state.update_data(photo_file_id=file_id)
    await _finalize(message, message.from_user, state, bot, profile_service, moderation, admin_user_id)


@router.callback_query(ProfileFSM.photo, F.data == "skip_photo")
async def step_photo_skip(
    cb: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    profile_service: ProfileService,
    moderation: bool,
    admin_user_id: int,
) -> None:
    await cb.answer()
    await state.update_data(photo_file_id=None)
    await _finalize(cb.message, cb.from_user, state, bot, profile_service, moderation, admin_user_id)


async def _finalize(
    reply_target: Message,
    user: User,
    state: FSMContext,
    bot: Bot,
    profile_service: ProfileService,
    moderation: bool,
    admin_user_id: int,
) -> None:
    """Build the profile object (auto-filling contact) and publish or submit for moderation."""
    contact = _auto_contact(user)
    await state.update_data(contact=contact)
    data = await state.get_data()
    await state.clear()

    profile = UserProfile(
        id=None,
        user_id=user.id,
        topic_id=None,
        last_message_id=None,
        name=data["name"],
        from_location=data["from_location"],
        destination=data["destination"],
        dates=data["dates"],
        date_range=data.get("date_range"),
        budget=data["budget"],
        style=data["style"],
        language=data["language"],
        bio=data.get("bio", ""),
        photo_file_id=data.get("photo_file_id"),
        contact=contact,
        status="active",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    if moderation:
        await _submit_for_moderation(reply_target, bot, profile, profile_service, admin_user_id)
    else:
        await _publish_immediately(reply_target, profile, profile_service)


async def _publish_immediately(
    message: Message, profile: UserProfile, profile_service: ProfileService
) -> None:
    try:
        _, link = await profile_service.save_and_publish(profile)
    except Exception:
        log.exception("Failed to save profile")
        await message.answer("❌ Something went wrong saving your profile. Please try again.")
        return

    if link:
        await message.answer(
            "✅ <b>Profile saved!</b>\n\n"
            f'Find travel buddies: <a href="{link}">Open your destination chat</a>',
            disable_web_page_preview=True,
        )
    else:
        await message.answer(
            "✅ <b>Profile saved!</b>\n\n"
            "⏳ Your card will appear in the group chat shortly — "
            "the bot is setting up the destination topic.\n\n"
            "Use /myprofile to check your profile anytime."
        )


async def _submit_for_moderation(
    message: Message,
    bot: Bot,
    profile: UserProfile,
    profile_service: ProfileService,
    admin_user_id: int,
) -> None:
    try:
        saved = await profile_service.save_pending(profile)
    except Exception:
        log.exception("Failed to save pending profile")
        await message.answer("❌ Something went wrong. Please try again.")
        return

    await message.answer(
        "⏳ <b>Profile submitted for review!</b>\n\n"
        "It will be published once the admin approves it. You'll get a notification."
    )

    preview = format_profile(saved)
    buttons = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Approve", callback_data=f"mod_approve:{saved.user_id}"),
        InlineKeyboardButton(text="❌ Reject",  callback_data=f"mod_reject:{saved.user_id}"),
    ]])
    try:
        await bot.send_message(
            chat_id=admin_user_id,
            text=f"🔔 <b>New profile pending review:</b>\n\n{preview}",
            reply_markup=buttons,
        )
    except Exception as e:
        log.warning("Could not notify admin %s: %s", admin_user_id, e)


# ─────────── /myprofile ───────────

@router.message(Command("myprofile"))
async def cmd_myprofile(message: Message, profile_service: ProfileService) -> None:
    profile = await profile_service.get(message.from_user.id)
    if not profile:
        await message.answer("You don't have a profile yet. Use /profile to create one.")
        return
    text = format_profile(profile)
    link = profile_service.link_for(profile)
    if link:
        text += f'\n\n🔗 <a href="{link}">Open your chat</a>'
    if profile.status == "pending":
        text += "\n\n⏳ <i>Pending admin approval</i>"
    await message.answer(text, disable_web_page_preview=True)


# ─────────── /deleteprofile ───────────

@router.message(Command("deleteprofile"))
async def cmd_deleteprofile(message: Message, profile_service: ProfileService) -> None:
    profile = await profile_service.get(message.from_user.id)
    if not profile:
        await message.answer("You don't have a profile to delete.")
        return
    await message.answer(
        "⚠️ <b>Delete your profile?</b>\n\n"
        "Your topic will be closed and you'll be removed from search.",
        reply_markup=get_delete_confirm_kb(),
    )


@router.callback_query(F.data == "del_confirm")
async def del_confirm(cb: CallbackQuery, profile_service: ProfileService) -> None:
    await cb.answer()
    result = await profile_service.delete(cb.from_user.id)
    if result:
        await cb.message.edit_text(
            "🗑 Profile deleted. Create a new one anytime with /profile."
        )
    else:
        await cb.message.edit_text("No profile found.")


@router.callback_query(F.data == "del_cancel")
async def del_cancel(cb: CallbackQuery) -> None:
    await cb.answer("Cancelled.")
    await cb.message.edit_text("✅ Cancelled — your profile is still active.")
