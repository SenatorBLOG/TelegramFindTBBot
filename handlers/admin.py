"""Admin commands: /release, /stats, /moderation + approve/reject callbacks."""
from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from repositories.profile_repo import ProfileRepository
from services.profile_service import ProfileService

log = logging.getLogger(__name__)
router = Router(name="admin")


def _guard(user_id: int, admin_user_id: int) -> bool:
    return user_id == admin_user_id


# ─────────── /release ───────────

@router.message(Command("release"))
async def cmd_release(
    message: Message,
    command: CommandObject,
    bot: Bot,
    admin_user_id: int,
    group_id: int,
) -> None:
    if not _guard(message.from_user.id, admin_user_id):
        return
    raw = (command.args or "").strip()
    if not raw:
        await message.answer(
            "Usage: <code>/release Your text here</code>\n"
            "Append <code>--pin</code> to also pin the message."
        )
        return
    pin = raw.endswith("--pin")
    if pin:
        raw = raw[: -len("--pin")].strip()
    if not raw:
        await message.answer("Announcement text cannot be empty.")
        return
    sent = await bot.send_message(chat_id=group_id, text=raw)
    if pin:
        try:
            await bot.pin_chat_message(chat_id=group_id, message_id=sent.message_id)
        except Exception as e:
            await message.answer(f"✅ Sent, but pinning failed: {e}")
            return
    await message.answer(f"✅ Announcement sent{' and pinned' if pin else ''}.")


# ─────────── /stats ───────────

@router.message(Command("stats"))
async def cmd_stats(
    message: Message, admin_user_id: int, profile_repo: ProfileRepository
) -> None:
    if not _guard(message.from_user.id, admin_user_id):
        return
    s = await profile_repo.get_stats()
    top = "\n".join(f"  • {d} ({c})" for d, c in s.get("top_destinations", []))
    styles = "  ".join(f"{k}: {v}" for k, v in s.get("by_style", {}).items())
    await message.answer(
        f"📊 <b>Stats</b>\n\n"
        f"👤 Total users: <b>{s['total_users']}</b>\n"
        f"✅ Active profiles: <b>{s['active_profiles']}</b>\n"
        f"⏳ Pending: <b>{s['pending_profiles']}</b>\n\n"
        f"🌍 <b>Top destinations:</b>\n{top or '  —'}\n\n"
        f"🧭 <b>Styles:</b> {styles or '—'}"
    )


# ─────────── /moderation ───────────

@router.message(Command("moderation"))
async def cmd_moderation(
    message: Message, admin_user_id: int, profile_repo: ProfileRepository
) -> None:
    if not _guard(message.from_user.id, admin_user_id):
        return
    pending = await profile_repo.get_pending()
    if not pending:
        await message.answer("✅ No pending profiles.")
        return
    for p in pending:
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Approve", callback_data=f"mod_approve:{p.user_id}"),
            InlineKeyboardButton(text="❌ Reject",  callback_data=f"mod_reject:{p.user_id}"),
        ]])
        await message.answer(
            f"<b>{p.name}</b> → {p.destination} → {p.dates}",
            reply_markup=kb,
        )


# ─────────── moderation callbacks ───────────

@router.callback_query(F.data.startswith("mod_approve:"))
async def cb_approve(
    cb: CallbackQuery, bot: Bot, admin_user_id: int, profile_service: ProfileService
) -> None:
    if not _guard(cb.from_user.id, admin_user_id):
        await cb.answer("Not authorised.", show_alert=True)
        return
    await cb.answer("Approving…")
    user_id = int(cb.data.split(":", 1)[1])
    result = await profile_service.approve(user_id)
    if result:
        profile, link = result
        topic_note = f'\n<a href="{link}">View topic</a>' if link else "\n⚠️ Topic creation failed — check bot admin rights."
        await cb.message.edit_text(
            f"✅ Approved: <b>{profile.name}</b> → {profile.destination}{topic_note}",
            disable_web_page_preview=True,
        )
        try:
            user_text = (
                f'🎉 Your profile was approved!\n<a href="{link}">Open your destination chat</a>'
                if link else
                "🎉 Your profile was approved! It will appear in the group chat shortly."
            )
            await bot.send_message(
                chat_id=user_id,
                text=user_text,
                disable_web_page_preview=True,
            )
        except Exception as e:
            log.warning("Could not notify user %s: %s", user_id, e)
    else:
        await cb.message.edit_text("⚠️ Profile not found or already processed.")


@router.callback_query(F.data.startswith("mod_reject:"))
async def cb_reject(
    cb: CallbackQuery, bot: Bot, admin_user_id: int, profile_service: ProfileService
) -> None:
    if not _guard(cb.from_user.id, admin_user_id):
        await cb.answer("Not authorised.", show_alert=True)
        return
    await cb.answer("Rejecting…")
    user_id = int(cb.data.split(":", 1)[1])
    profile = await profile_service.reject(user_id)
    if profile:
        await cb.message.edit_text(f"❌ Rejected: <b>{profile.name}</b>")
        try:
            await bot.send_message(
                chat_id=user_id,
                text="😔 Your profile was not approved. You can update and resubmit with /profile.",
            )
        except Exception as e:
            log.warning("Could not notify user %s: %s", user_id, e)
    else:
        await cb.message.edit_text("⚠️ Profile not found.")
