"""Thin wrapper over Telegram forum-topic API."""
from __future__ import annotations

import logging
from typing import Optional

from aiogram import Bot

log = logging.getLogger(__name__)


class TopicService:
    def __init__(self, bot: Bot, group_id: int):
        self._bot = bot
        self._group_id = group_id

    async def create_topic(self, title: str) -> int:
        """Create a forum topic and return its message_thread_id."""
        topic = await self._bot.create_forum_topic(
            chat_id=self._group_id, name=title[:128]
        )
        log.info("Created topic %s (%r)", topic.message_thread_id, title)
        return topic.message_thread_id

    async def send_profile(
        self,
        topic_id: int,
        text: str,
        photo_file_id: Optional[str] = None,
    ) -> int:
        """Send a profile post into a topic. Returns message_id."""
        if photo_file_id:
            msg = await self._bot.send_photo(
                chat_id=self._group_id,
                photo=photo_file_id,
                caption=text,
                message_thread_id=topic_id,
            )
        else:
            msg = await self._bot.send_message(
                chat_id=self._group_id,
                text=text,
                message_thread_id=topic_id,
                disable_web_page_preview=True,
            )
        return msg.message_id

    async def update_profile(
        self,
        topic_id: int,
        old_message_id: Optional[int],
        new_text: str,
        photo_file_id: Optional[str] = None,
    ) -> int:
        """Delete the old profile post and send a fresh one in the same topic."""
        if old_message_id is not None:
            try:
                await self._bot.delete_message(
                    chat_id=self._group_id, message_id=old_message_id
                )
            except Exception as e:
                log.warning("Could not delete old message %s: %s", old_message_id, e)
        return await self.send_profile(topic_id, new_text, photo_file_id)

    async def close_topic(self, topic_id: int) -> None:
        """Close (lock) a forum topic."""
        try:
            await self._bot.close_forum_topic(
                chat_id=self._group_id, message_thread_id=topic_id
            )
        except Exception as e:
            log.warning("Could not close topic %s: %s", topic_id, e)

    def build_topic_link(self, topic_id: int) -> str:
        raw = str(self._group_id)
        internal = raw[4:] if raw.startswith("-100") else raw.lstrip("-")
        return f"https://t.me/c/{internal}/{topic_id}"
