"""The pinned "Create my profile" index message in the group's landing topic.

Hard rule to avoid spamming the group on every deploy/restart:
  • Startup calls refresh_silent() — it ONLY edits the existing message in
    place (silent, no notification) and NEVER posts a new one.
  • A brand-new message is created ONLY when the admin explicitly runs
    /refreshindex, which calls post_fresh().
So a restart can never make a new group message appear.
"""
from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

log = logging.getLogger(__name__)

_INDEX_TEXT = (
    "✈️ <b>Find a Travel Buddy</b>\n\n"
    "Browse traveller profiles below and find your perfect trip companion.\n\n"
    "Ready to meet people? Tap the button to create your profile."
)
_INDEX_KEY = "profiles_index_msg_id"


class IndexService:
    def __init__(
        self,
        bot: Bot,
        group_id: int,
        profiles_topic_id: int | None,
        bot_username: str,
        db_conn,
    ):
        self._bot = bot
        self._group_id = group_id
        self._topic_id = profiles_topic_id
        self._bot_username = bot_username
        self._conn = db_conn

    def _kb(self) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text="📝 Create my profile",
                url=f"https://t.me/{self._bot_username}?start=profile",
            ),
        ]])

    async def _stored_id(self) -> int | None:
        async with self._conn.execute(
            "SELECT value FROM settings WHERE key = ?", (_INDEX_KEY,)
        ) as cur:
            row = await cur.fetchone()
        return int(row[0]) if row else None

    async def _store_id(self, message_id: int) -> None:
        await self._conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (_INDEX_KEY, str(message_id)),
        )
        await self._conn.commit()

    async def refresh_silent(self) -> None:
        """Startup path: edit the existing index in place, never post a new one.

        Editing sends no notification and creates no new message, so restarts
        are invisible to the group. If there is no stored message or the edit
        fails, we log and do nothing — the admin can run /refreshindex.
        """
        msg_id = await self._stored_id()
        if msg_id is None:
            log.info("No index message yet — admin can run /refreshindex to post one.")
            return
        try:
            await self._bot.edit_message_text(
                chat_id=self._group_id,
                message_id=msg_id,
                text=_INDEX_TEXT,
                reply_markup=self._kb(),
                disable_web_page_preview=True,
            )
            log.info("Silently refreshed index message %s", msg_id)
        except TelegramBadRequest as e:
            if "message is not modified" in str(e).lower():
                log.info("Index message %s already up to date", msg_id)
            else:
                # Do NOT repost on startup — that is exactly the spam we avoid.
                log.warning("Index edit skipped (%s); run /refreshindex to repost", e)
        except Exception as e:
            log.warning("Index edit error: %s", e)

    async def post_fresh(self) -> int | None:
        """Admin path (/refreshindex): unpin old, post a new index, pin it.

        Returns the new message_id, or None if posting failed.
        """
        if not self._topic_id:
            log.warning("post_fresh called but no profiles_topic_id configured")
            return None
        try:
            try:
                await self._bot.unpin_all_forum_topic_messages(
                    chat_id=self._group_id, message_thread_id=self._topic_id
                )
            except Exception:
                pass  # nothing pinned — fine

            msg = await self._bot.send_message(
                chat_id=self._group_id,
                message_thread_id=self._topic_id,
                text=_INDEX_TEXT,
                reply_markup=self._kb(),
                disable_web_page_preview=True,
            )
            await self._store_id(msg.message_id)
            try:
                await self._bot.pin_chat_message(
                    chat_id=self._group_id,
                    message_id=msg.message_id,
                    disable_notification=True,
                )
            except Exception as pin_err:
                log.warning("Could not pin index message: %s", pin_err)
            log.info("Posted fresh index message %s", msg.message_id)
            return msg.message_id
        except Exception as e:
            log.warning("Could not post fresh index message: %s", e)
            return None
