"""Group message handler.

Sole responsibility: guard the "Главная" (landing/index) topic —
delete any user message posted there so only the bot's pinned welcome
message with the "Заполнить анкету" button remains visible.

Owner-notification logic has been removed: destination topics are shared
among all travellers going to the same place, so per-user notifications
no longer make sense. Users contact each other via the @username shown
in each profile card.
"""
from __future__ import annotations

import logging
from typing import Optional

from aiogram import Bot, F, Router
from aiogram.types import Message

log = logging.getLogger(__name__)
router = Router(name="group")


@router.message(
    F.chat.type.in_({"group", "supergroup"}),
    F.message_thread_id.is_not(None),
)
async def group_topic_message(
    message: Message,
    bot: Bot,
    group_id: int,
    profiles_topic_id: Optional[int],
) -> None:
    """Delete user messages posted in the landing topic."""
    if message.chat.id != group_id:
        return
    if not message.from_user or message.from_user.is_bot:
        return

    # Guard the "Главная" index topic: bot-only zone.
    if profiles_topic_id and message.message_thread_id == profiles_topic_id:
        try:
            await bot.delete_message(group_id, message.message_id)
        except Exception as e:
            log.debug("Could not delete message in landing topic: %s", e)
