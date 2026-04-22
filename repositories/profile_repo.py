"""SQL access layer for the `profiles` table."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

import aiosqlite

from models import UserProfile


def _row_to_profile(row: aiosqlite.Row) -> UserProfile:
    return UserProfile(
        id=row["id"],
        user_id=row["user_id"],
        topic_id=row["topic_id"],
        last_message_id=row["last_message_id"],
        name=row["name"],
        from_location=row["from_location"],
        destination=row["destination"],
        dates=row["dates"],
        date_range=row["date_range"],
        budget=row["budget"],
        style=row["style"],
        language=row["language"],
        bio=row["bio"] or "",
        photo_file_id=row["photo_file_id"],
        contact=row["contact"] or "",
        status=row["status"] or "active",
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


class ProfileRepository:
    def __init__(self, conn: aiosqlite.Connection):
        self._conn = conn

    # ─────────── lookups ───────────

    async def get_by_user_id(self, user_id: int) -> Optional[UserProfile]:
        async with self._conn.execute(
            "SELECT * FROM profiles WHERE user_id = ?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
        return _row_to_profile(row) if row else None

    async def get_by_topic_id(self, topic_id: int) -> Optional[UserProfile]:
        async with self._conn.execute(
            "SELECT * FROM profiles WHERE topic_id = ?", (topic_id,)
        ) as cur:
            row = await cur.fetchone()
        return _row_to_profile(row) if row else None

    async def get_pending(self) -> list[UserProfile]:
        async with self._conn.execute(
            "SELECT * FROM profiles WHERE status = 'pending' ORDER BY created_at ASC"
        ) as cur:
            rows = await cur.fetchall()
        return [_row_to_profile(r) for r in rows]

    # ─────────── writes ───────────

    async def upsert(self, profile: UserProfile) -> UserProfile:
        now = datetime.utcnow().isoformat()
        existing = await self.get_by_user_id(profile.user_id)

        if existing:
            await self._conn.execute(
                """
                UPDATE profiles SET
                    name=?, from_location=?, destination=?, dates=?, date_range=?,
                    budget=?, style=?, language=?, bio=?, photo_file_id=?, contact=?,
                    updated_at=?
                WHERE user_id=?
                """,
                (
                    profile.name, profile.from_location, profile.destination,
                    profile.dates, profile.date_range, profile.budget, profile.style,
                    profile.language, profile.bio, profile.photo_file_id, profile.contact,
                    now, profile.user_id,
                ),
            )
        else:
            await self._conn.execute(
                """
                INSERT INTO profiles
                    (user_id, name, from_location, destination, dates, date_range,
                     budget, style, language, bio, photo_file_id, contact, status,
                     created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    profile.user_id, profile.name, profile.from_location,
                    profile.destination, profile.dates, profile.date_range,
                    profile.budget, profile.style, profile.language, profile.bio,
                    profile.photo_file_id, profile.contact, profile.status, now, now,
                ),
            )
        await self._conn.commit()
        result = await self.get_by_user_id(profile.user_id)
        assert result is not None
        return result

    async def update_topic(self, user_id: int, topic_id: int, last_message_id: int) -> None:
        await self._conn.execute(
            "UPDATE profiles SET topic_id=?, last_message_id=?, updated_at=? WHERE user_id=?",
            (topic_id, last_message_id, datetime.utcnow().isoformat(), user_id),
        )
        await self._conn.commit()

    async def update_last_message(self, user_id: int, last_message_id: int) -> None:
        await self._conn.execute(
            "UPDATE profiles SET last_message_id=?, updated_at=? WHERE user_id=?",
            (last_message_id, datetime.utcnow().isoformat(), user_id),
        )
        await self._conn.commit()

    async def update_status(self, user_id: int, status: str) -> None:
        await self._conn.execute(
            "UPDATE profiles SET status=?, updated_at=? WHERE user_id=?",
            (status, datetime.utcnow().isoformat(), user_id),
        )
        await self._conn.commit()

    async def delete(self, user_id: int) -> None:
        await self._conn.execute("DELETE FROM profiles WHERE user_id=?", (user_id,))
        await self._conn.commit()

    # ─────────── search ───────────

    async def search(
        self,
        destination: Optional[str] = None,
        date_range: Optional[str] = None,
        budget: Optional[str] = None,
        style: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[UserProfile]:
        conditions: list[str] = ["topic_id IS NOT NULL", "status = 'active'"]
        params: list[Any] = []

        if destination:
            conditions.append("LOWER(destination) LIKE LOWER(?)")
            params.append(f"%{destination}%")
        if date_range:
            conditions.append("date_range = ?")
            params.append(date_range)
        if budget:
            conditions.append("budget = ?")
            params.append(budget)
        if style:
            conditions.append("style = ?")
            params.append(style)

        sql = (
            f"SELECT * FROM profiles WHERE {' AND '.join(conditions)} "
            f"ORDER BY updated_at DESC LIMIT ? OFFSET ?"
        )
        params.extend([limit, offset])

        async with self._conn.execute(sql, params) as cur:
            rows = await cur.fetchall()
        return [_row_to_profile(r) for r in rows]

    # ─────────── stats ───────────

    async def get_stats(self) -> dict[str, Any]:
        stats: dict[str, Any] = {}

        async with self._conn.execute(
            "SELECT COUNT(*) FROM profiles WHERE status='active'"
        ) as cur:
            stats["active_profiles"] = (await cur.fetchone())[0]

        async with self._conn.execute(
            "SELECT COUNT(*) FROM profiles WHERE status='pending'"
        ) as cur:
            stats["pending_profiles"] = (await cur.fetchone())[0]

        async with self._conn.execute("SELECT COUNT(*) FROM users") as cur:
            stats["total_users"] = (await cur.fetchone())[0]

        async with self._conn.execute(
            "SELECT destination, COUNT(*) cnt FROM profiles WHERE status='active' "
            "GROUP BY LOWER(destination) ORDER BY cnt DESC LIMIT 5"
        ) as cur:
            stats["top_destinations"] = [(r[0], r[1]) for r in await cur.fetchall()]

        async with self._conn.execute(
            "SELECT style, COUNT(*) FROM profiles WHERE status='active' GROUP BY style"
        ) as cur:
            stats["by_style"] = {r[0]: r[1] for r in await cur.fetchall()}

        return stats
