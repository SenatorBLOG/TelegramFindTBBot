"""Group message handler.

Two responsibilities:
1. Guard the "Анкеты" (profiles index) topic — delete any user message posted there
   so only bot-generated profile posts appear.
2. Notify a profile owner when someone writes in their personal profile topic.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

from aiogram import Bot, F, Router
from aiogram.types import Message

from repositories.profile_repo import ProfileRepository

log = logging.getLogger(__name__)
router = Router(name="group")

# Rate-limit: notify owner once per (topic, visitor) pair per COOLDOWN seconds.
_COOLDOWN_S = 1800  # 30 minutes
_notified: dict[tuple[int, int], float] = {}   # (topic_id, visitor_id) → timestamp


@router.message(
    F.chat.type.in_({"group", "supergroup"}),
    F.message_thread_id.is_not(None),
)
async def group_topic_message(
    message: Message,
    bot: Bot,
    group_id: int,
    profile_repo: ProfileRepository,
    profiles_topic_id: Optional[int],
) -> None:
    # Only handle messages inside our registered group.
    if message.chat.id != group_id:
        return
    if not message.from_user or message.from_user.is_bot:
        return

    topic_id: int = message.message_thread_id

    # ── Guard: delete all user messages posted in the profiles index topic ──
    if profiles_topic_id and topic_id == profiles_topic_id:
        try:
            await bot.delete_message(group_id, message.message_id)
        except Exception as e:
            log.debug("Could not delete message in profiles topic: %s", e)
        return

    # ── Notify profile owner when someone visits their personal topic ──
    visitor_id: int = message.from_user.id

    profile = await profile_repo.get_by_topic_id(topic_id)
    if not profile or profile.user_id == visitor_id:
        return  # no profile for this topic, or owner wrote in their own thread

    now = time.monotonic()
    key = (topic_id, visitor_id)
    if now - _notified.get(key, 0.0) < _COOLDOWN_S:
        return
    _notified[key] = now

    raw = str(group_id)
    internal = raw[4:] if raw.startswith("-100") else raw.lstrip("-")
    link = f"https://t.me/c/{internal}/{topic_id}"
    visitor_name = message.from_user.full_name or f"User {visitor_id}"

    try:
        await bot.send_message(
            chat_id=profile.user_id,
            text=(
                f"👀 <b>{visitor_name}</b> just messaged in your travel topic!\n\n"
                f"🌍 {profile.destination} | {profile.dates}\n\n"
                f'<a href="{link}">Open your topic</a>'
            ),
            disable_web_page_preview=True,
        )
    except Exception as e:
        log.debug("Could not DM profile owner %s: %s", profile.user_id, e)
