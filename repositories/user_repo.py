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
    ) -> None:
        """Insert or refresh a user record. Safe to call on every interaction."""
        now = datetime.utcnow().isoformat()
        await self._conn.execute(
            """
            INSERT INTO users (id, username, first_name, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name
            """,
            (user_id, username, first_name, now),
        )
        await self._conn.commit()
