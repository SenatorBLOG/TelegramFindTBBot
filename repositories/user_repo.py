"""Minimal user repository. Stub today, ready for v2 expansion."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

import aiosqlite


class UserRepository:
    def __init__(self, conn: aiosqlite.Connection):
        self._conn = conn

    async def upsert(
        self,
        user_id: int,
        username: Optional[str],
        first_name: Optional[str],
        is_private: bool = False,
    ) -> None:
        """Insert or refresh a user record. Safe to call on every interaction.

        `is_private` marks a real DM interaction with the bot (as opposed to
        merely writing in the group). Once set it is never cleared, so /stats
        can distinguish actual bot users from people who only posted in the group.
        """
        now = datetime.utcnow().isoformat()
        flag = 1 if is_private else 0
        await self._conn.execute(
            """
            INSERT INTO users (id, username, first_name, created_at, interacted_privately)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name,
                interacted_privately = MAX(users.interacted_privately, excluded.interacted_privately)
            """,
            (user_id, username, first_name, now, flag),
        )
        await self._conn.commit()
