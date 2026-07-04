"""SQL access for anti-spam: member tenure tracking + spam audit log."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Optional

import aiosqlite

# A member is considered "new" (and therefore quarantined from posting links)
# while EITHER of these holds.
NEWCOMER_MAX_MESSAGES = 3
NEWCOMER_MAX_AGE = timedelta(hours=24)


class ModerationRepository:
    def __init__(self, conn: aiosqlite.Connection):
        self._conn = conn

    async def touch_member(self, chat_id: int, user_id: int) -> bool:
        """Record this message from a member and return whether they were a
        *newcomer at the moment this message arrived* (i.e. before this one is
        counted). Newcomer = fewer than NEWCOMER_MAX_MESSAGES prior messages OR
        first seen less than NEWCOMER_MAX_AGE ago.
        """
        now = datetime.utcnow()
        async with self._conn.execute(
            "SELECT first_seen, msg_count FROM chat_members WHERE chat_id=? AND user_id=?",
            (chat_id, user_id),
        ) as cur:
            row = await cur.fetchone()

        if row is None:
            await self._conn.execute(
                "INSERT INTO chat_members (chat_id, user_id, first_seen, msg_count) "
                "VALUES (?, ?, ?, 1)",
                (chat_id, user_id, now.isoformat()),
            )
            await self._conn.commit()
            return True  # very first message — definitely a newcomer

        first_seen = datetime.fromisoformat(row[0])
        prior_count = row[1]
        await self._conn.execute(
            "UPDATE chat_members SET msg_count = msg_count + 1 WHERE chat_id=? AND user_id=?",
            (chat_id, user_id),
        )
        await self._conn.commit()

        is_new = prior_count < NEWCOMER_MAX_MESSAGES or (now - first_seen) < NEWCOMER_MAX_AGE
        return is_new

    async def log_spam(
        self,
        chat_id: int,
        user_id: int,
        username: Optional[str],
        text: Optional[str],
        reason: str,
    ) -> int:
        """Store a deleted-spam record; returns its row id."""
        cur = await self._conn.execute(
            "INSERT INTO spam_log (chat_id, user_id, username, text, reason, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (chat_id, user_id, username, (text or "")[:500], reason,
             datetime.utcnow().isoformat()),
        )
        await self._conn.commit()
        return cur.lastrowid

    async def recent_spam(self, limit: int = 20) -> list[dict[str, Any]]:
        async with self._conn.execute(
            "SELECT id, user_id, username, text, reason, created_at "
            "FROM spam_log ORDER BY id DESC LIMIT ?",
            (limit,),
        ) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]
