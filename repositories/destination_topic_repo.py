"""SQL access layer for the `destination_topics` table.

Maps (canonical_destination, year) → Telegram forum topic_id so the bot
does not create duplicate topics for the same destination + year.
"""
from __future__ import annotations

from typing import Optional

import aiosqlite


class DestinationTopicRepository:
    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def get(self, destination: str, year: str) -> Optional[int]:
        """Return the topic_id for (destination, year), or None if not yet created."""
        async with self._conn.execute(
            "SELECT topic_id FROM destination_topics WHERE destination = ? AND year = ?",
            (destination, year),
        ) as cur:
            row = await cur.fetchone()
        return row["topic_id"] if row else None

    async def save(self, destination: str, year: str, topic_id: int) -> None:
        """Persist a new (destination, year) → topic_id mapping."""
        await self._conn.execute(
            """
            INSERT INTO destination_topics (destination, year, topic_id)
            VALUES (?, ?, ?)
            ON CONFLICT(destination, year) DO UPDATE SET topic_id = excluded.topic_id
            """,
            (destination, year, topic_id),
        )
        await self._conn.commit()
