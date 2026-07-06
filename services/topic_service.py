"""Thin wrapper over Telegram forum-topic and message APIs."""
from __future__ import annotations

import logging
from typing import Optional

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InputMediaPhoto

log = logging.getLogger(__name__)


class TopicService:
    def __init__(self, bot: Bot, group_id: int):
        self._bot = bot
        self._group_id = group_id

    # ─────────── topic management ───────────

    async def create_topic(self, title: str) -> int:
        """Create a forum topic and return its message_thread_id."""
        topic = await self._bot.create_forum_topic(
            chat_id=self._group_id, name=title[:128]
        )
        log.info("Created topic %s (%r)", topic.message_thread_id, title)
        return topic.message_thread_id

    # ─────────── profile message CRUD ───────────

    async def send_profile(
        self,
        topic_id: int,
        text: str,
        photo_file_id: Optional[str] = None,
        reply_markup=None,
    ) -> int:
        """Post a profile card into a topic. Returns the new message_id."""
        if photo_file_id:
            msg = await self._bot.send_photo(
                chat_id=self._group_id,
                photo=photo_file_id,
                caption=text,
                message_thread_id=topic_id,
                reply_markup=reply_markup,
            )
        else:
            msg = await self._bot.send_message(
                chat_id=self._group_id,
                text=text,
                message_thread_id=topic_id,
                disable_web_page_preview=True,
                reply_markup=reply_markup,
            )
        return msg.message_id

    async def update_profile(
        self,
        topic_id: int,
        old_message_id: Optional[int],
        new_text: str,
        photo_file_id: Optional[str] = None,
        reply_markup=None,
    ) -> int:
        """Edit the existing card in place so it keeps its position and replies.

        Falls back to delete + resend only when the message type changes
        (text card ⇄ photo card) or the old message is gone. Returns the
        message_id of the (possibly new) card.
        """
        if old_message_id is None:
            return await self.send_profile(topic_id, new_text, photo_file_id, reply_markup)

        try:
            if photo_file_id:
                # Updates both the image and the caption in a single call, and
                # is a no-op-safe way to refresh a photo card.
                await self._bot.edit_message_media(
                    chat_id=self._group_id,
                    message_id=old_message_id,
                    media=InputMediaPhoto(media=photo_file_id, caption=new_text),
                    reply_markup=reply_markup,
                )
            else:
                await self._bot.edit_message_text(
                    chat_id=self._group_id,
                    message_id=old_message_id,
                    text=new_text,
                    disable_web_page_preview=True,
                    reply_markup=reply_markup,
                )
            return old_message_id
        except TelegramBadRequest as e:
            if "not modified" in str(e).lower():
                return old_message_id  # already identical — nothing to do
            # Message type changed (text⇄photo) or it was deleted — resend.
            log.info("In-place card edit failed (%s) — resending", e)
            await self.delete_message(old_message_id)
            return await self.send_profile(topic_id, new_text, photo_file_id, reply_markup)

    async def edit_markup(self, message_id: int, reply_markup) -> None:
        """Replace just the inline keyboard on a card (used for the live counter)."""
        await self._bot.edit_message_reply_markup(
            chat_id=self._group_id,
            message_id=message_id,
            reply_markup=reply_markup,
        )

    async def delete_message(self, message_id: int) -> None:
        """Delete any single message from the group (e.g. an old profile card)."""
        try:
            await self._bot.delete_message(
                chat_id=self._group_id, message_id=message_id
            )
        except Exception as e:
            log.warning("Could not delete message %s: %s", message_id, e)

    # ─────────── link helpers ───────────

    def build_topic_link(self, topic_id: int) -> str:
        """Deep-link to a destination forum topic (the whole thread)."""
        return f"https://t.me/c/{self._internal_id}/{topic_id}"

    def build_message_link(self, message_id: int) -> str:
        """Deep-link to a specific profile-card message."""
        return f"https://t.me/c/{self._internal_id}/{message_id}"

    @property
    def _internal_id(self) -> str:
        raw = str(self._group_id)
        return raw[4:] if raw.startswith("-100") else raw.lstrip("-")
