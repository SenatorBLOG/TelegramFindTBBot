"""Admin commands: /release, /stats, /moderation, /import + approve/reject callbacks."""
from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Optional

import aiohttp
from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from models import UserProfile
from repositories.moderation_repo import ModerationRepository
from repositories.profile_repo import ProfileRepository
from services.profile_service import ProfileService
from utils.formatters import esc

log = logging.getLogger(__name__)
router = Router(name="admin")

_IMPORT_HELP = (
    "📥 <b>Import a profile from Facebook</b>\n\n"
    "Usage:\n"
    "<code>/import Name | Destination | Dates | From | Budget | Style | Language | Bio | PhotoURL</code>\n\n"
    "Fields after <b>Dates</b> are optional.\n\n"
    "<b>Budget:</b> budget · medium · comfort · luxury\n"
    "<b>Style:</b> backpacker · adventure · culture · relaxed · party · mixed\n\n"
    "<b>Example:</b>\n"
    "<code>/import Anna | Thailand | June 2026 | Moscow | medium | backpacker | English, Russian | Looking for a travel buddy in Phuket | https://example.com/photo.jpg</code>"
)


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
    top = "\n".join(f"  • {esc(d)} ({c})" for d, c in s.get("top_destinations", []))
    styles = "  ".join(f"{esc(k)}: {v}" for k, v in s.get("by_style", {}).items())
    group_writers = s["total_users"] - s["dm_users"]
    await message.answer(
        f"📊 <b>Stats</b>\n\n"
        f"👤 Bot users (DM): <b>{s['dm_users']}</b>  (+{s['dm_users_7d']} this week)\n"
        f"👥 Seen in group only: <b>{group_writers}</b>\n\n"
        f"✅ Active profiles: <b>{s['active_profiles']}</b>\n"
        f"⏳ Pending: <b>{s['pending_profiles']}</b>\n"
        f"📥 Imported: <b>{s['imported_profiles']}</b>\n\n"
        f"🌍 <b>Top destinations:</b>\n{top or '  —'}\n\n"
        f"🧭 <b>Styles:</b> {styles or '—'}"
    )


# ─────────── /import ───────────

@router.message(Command("import"))
async def cmd_import(
    message: Message,
    command: CommandObject,
    bot: Bot,
    admin_user_id: int,
    profile_service: ProfileService,
) -> None:
    if not _guard(message.from_user.id, admin_user_id):
        return

    raw = (command.args or "").strip()
    if not raw:
        await message.answer(_IMPORT_HELP)
        return

    parts = [p.strip() for p in raw.split("|")]
    if len(parts) < 3:
        await message.answer("⚠️ Need at least: Name | Destination | Dates\n\n" + _IMPORT_HELP)
        return

    name        = parts[0] or "Unknown"
    destination = parts[1] or "Unknown"
    dates       = parts[2] or "Flexible"
    from_loc    = parts[3] if len(parts) > 3 else "Unknown"
    budget      = parts[4] if len(parts) > 4 else "medium"
    style       = parts[5] if len(parts) > 5 else "mixed"
    language    = parts[6] if len(parts) > 6 else "English"
    bio         = parts[7] if len(parts) > 7 else ""
    photo_url   = parts[8].strip() if len(parts) > 8 else None

    # ── Download & upload photo if URL provided ──────────────────────────────
    photo_file_id: Optional[str] = None
    if photo_url:
        status_msg = await message.answer("⏳ Downloading photo…")
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            async with aiohttp.ClientSession() as session:
                async with session.get(photo_url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status == 200:
                        photo_bytes = await resp.read()
                        tmp = await bot.send_photo(
                            chat_id=message.chat.id,
                            photo=BufferedInputFile(photo_bytes, filename="photo.jpg"),
                        )
                        photo_file_id = tmp.photo[-1].file_id
                        await bot.delete_message(chat_id=message.chat.id, message_id=tmp.message_id)
                    else:
                        await status_msg.edit_text(f"⚠️ Photo returned HTTP {resp.status} — importing without photo.")
        except Exception as e:
            log.warning("Photo download failed: %s", e)
            await status_msg.edit_text(f"⚠️ Could not download photo ({e}) — importing without photo.")
        else:
            await bot.delete_message(chat_id=message.chat.id, message_id=status_msg.message_id)

    # ── Build profile (fake NEGATIVE user_id so it never collides with a real
    #    Telegram id, which are always positive). Note the parentheses: Python's
    #    % on a negative operand yields a positive result, so the negation must
    #    wrap the whole modulo, not just the left operand. ──────────────────────
    fake_user_id = -(int(time.time() * 1000) % (10 ** 12))
    now = datetime.utcnow()
    profile = UserProfile(
        id=None,
        user_id=fake_user_id,
        topic_id=None,
        last_message_id=None,
        name=name,
        from_location=from_loc,
        destination=destination,
        dates=dates,
        date_range=None,
        budget=budget,
        style=style,
        language=language,
        bio=bio,
        photo_file_id=photo_file_id,
        contact="Imported from Facebook",
        status="active",
        created_at=now,
        updated_at=now,
    )

    try:
        saved, link = await profile_service.save_and_publish(profile)
    except Exception as e:
        log.exception("Import failed")
        await message.answer(f"❌ Import failed: {e}")
        return

    if link:
        await message.answer(
            f"✅ Imported: <b>{esc(saved.name)}</b> → {esc(saved.destination)}\n"
            f'<a href="{link}">View in group</a>',
            disable_web_page_preview=True,
        )
    else:
        await message.answer(
            f"✅ Imported: <b>{esc(saved.name)}</b> → {esc(saved.destination)}\n"
            "⚠️ Profile saved but topic creation failed — check bot admin rights."
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
            f"<b>{esc(p.name)}</b> → {esc(p.destination)} → {esc(p.dates)}",
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
            f"✅ Approved: <b>{esc(profile.name)}</b> → {esc(profile.destination)}{topic_note}",
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
        await cb.message.edit_text(f"❌ Rejected: <b>{esc(profile.name)}</b>")
        try:
            await bot.send_message(
                chat_id=user_id,
                text="😔 Your profile was not approved. You can update and resubmit with /profile.",
            )
        except Exception as e:
            log.warning("Could not notify user %s: %s", user_id, e)
    else:
        await cb.message.edit_text("⚠️ Profile not found.")


# ─────────── spam moderation (buttons on the "Spam deleted" alert) ───────────

@router.callback_query(F.data.startswith("spam_ban:"))
async def cb_spam_ban(cb: CallbackQuery, bot: Bot, admin_user_id: int) -> None:
    if not _guard(cb.from_user.id, admin_user_id):
        await cb.answer("Not authorised.", show_alert=True)
        return
    _, chat_id_s, user_id_s = cb.data.split(":")
    chat_id, user_id = int(chat_id_s), int(user_id_s)
    try:
        await bot.ban_chat_member(chat_id=chat_id, user_id=user_id)
        await cb.answer("Banned.")
        await cb.message.edit_text(cb.message.html_text + "\n\n🔨 <b>User banned.</b>")
    except Exception as e:
        await cb.answer("Ban failed.", show_alert=True)
        log.warning("Ban failed for user=%s: %s", user_id, e)


@router.callback_query(F.data.startswith("spam_ok:"))
async def cb_spam_ok(cb: CallbackQuery, admin_user_id: int) -> None:
    if not _guard(cb.from_user.id, admin_user_id):
        await cb.answer("Not authorised.", show_alert=True)
        return
    await cb.answer("Marked as not spam.")
    await cb.message.edit_text(
        cb.message.html_text
        + "\n\n✅ <b>Marked not spam.</b> <i>(message was already deleted — "
        "tune the filter in utils/word_filter.py if this recurs)</i>"
    )


# ─────────── /spamlog ───────────

@router.message(Command("spamlog"))
async def cmd_spamlog(
    message: Message, admin_user_id: int, mod_repo: ModerationRepository
) -> None:
    if not _guard(message.from_user.id, admin_user_id):
        return
    rows = await mod_repo.recent_spam(limit=20)
    if not rows:
        await message.answer("✅ No spam logged yet.")
        return
    lines = ["🧹 <b>Recent spam (last 20)</b>\n"]
    for r in rows:
        who = f"@{r['username']}" if r["username"] else f"id{r['user_id']}"
        when = (r["created_at"] or "")[:16].replace("T", " ")
        snippet = esc((r["text"] or "")[:60])
        lines.append(f"• <code>{esc(r['reason'])}</code> {esc(who)} {when}\n  {snippet}")
    await message.answer("\n".join(lines), disable_web_page_preview=True)
