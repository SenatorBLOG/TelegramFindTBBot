"""SQL access for the "I'm interested" feature."""
from __future__ import annotations

from datetime import datetime

import aiosqlite


class InterestRepository:
    def __init__(self, conn: aiosqlite.Connection):
        self._conn = conn

    async def add(self, owner_id: int, from_id: int) -> bool:
        """Record interest. Returns True if new, False if it already existed."""
        cur = await self._conn.execute(
            "INSERT OR IGNORE INTO interests (owner_id, from_id, created_at) "
            "VALUES (?, ?, ?)",
            (owner_id, from_id, datetime.utcnow().isoformat()),
        )
        await self._conn.commit()
        return cur.rowcount > 0

    async def count(self, owner_id: int) -> int:
        async with self._conn.execute(
            "SELECT COUNT(*) FROM interests WHERE owner_id = ?", (owner_id,)
        ) as cur:
            row = await cur.fetchone()
        return row[0] if row else 0
