"""SQLite-backed FSM storage — replaces MemoryStorage for persistence across restarts."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

import aiosqlite
from aiogram.fsm.storage.base import BaseStorage, StorageKey

log = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS fsm_states (
    bot_id   INTEGER NOT NULL,
    chat_id  INTEGER NOT NULL,
    user_id  INTEGER NOT NULL,
    destiny  TEXT    NOT NULL DEFAULT '',
    state    TEXT,
    data     TEXT    NOT NULL DEFAULT '{}',
    PRIMARY KEY (bot_id, chat_id, user_id, destiny)
);
"""


class SQLiteStorage(BaseStorage):
    """Persistent FSM storage backed by a SQLite file."""

    def __init__(self, path: Path | str):
        self._path = str(path)
        self._conn: Optional[aiosqlite.Connection] = None

    async def _get_conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            self._conn = await aiosqlite.connect(self._path)
            await self._conn.executescript(_SCHEMA)
            await self._conn.commit()
        return self._conn

    @staticmethod
    def _key(k: StorageKey) -> tuple[int, int, int, str]:
        return (k.bot_id, k.chat_id, k.user_id, getattr(k, "destiny", ""))

    @staticmethod
    def _serialize_state(state) -> Optional[str]:
        """Convert a State object (or string or None) to a plain string for SQLite."""
        if state is None:
            return None
        if isinstance(state, str):
            return state
        # aiogram State object exposes its string form via .state attribute
        return state.state if hasattr(state, "state") else str(state)

    async def set_state(self, key: StorageKey, state=None) -> None:
        state = self._serialize_state(state)
        conn = await self._get_conn()
        b, c, u, d = self._key(key)
        await conn.execute(
            """
            INSERT INTO fsm_states (bot_id, chat_id, user_id, destiny, state)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(bot_id, chat_id, user_id, destiny) DO UPDATE SET state = excluded.state
            """,
            (b, c, u, d, state),
        )
        await conn.commit()

    async def get_state(self, key: StorageKey) -> Optional[str]:
        conn = await self._get_conn()
        b, c, u, d = self._key(key)
        async with conn.execute(
            "SELECT state FROM fsm_states WHERE bot_id=? AND chat_id=? AND user_id=? AND destiny=?",
            (b, c, u, d),
        ) as cur:
            row = await cur.fetchone()
        return row[0] if row else None

    async def set_data(self, key: StorageKey, data: dict[str, Any]) -> None:
        conn = await self._get_conn()
        b, c, u, d = self._key(key)
        await conn.execute(
            """
            INSERT INTO fsm_states (bot_id, chat_id, user_id, destiny, data)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(bot_id, chat_id, user_id, destiny) DO UPDATE SET data = excluded.data
            """,
            (b, c, u, d, json.dumps(data)),
        )
        await conn.commit()

    async def get_data(self, key: StorageKey) -> dict[str, Any]:
        conn = await self._get_conn()
        b, c, u, d = self._key(key)
        async with conn.execute(
            "SELECT data FROM fsm_states WHERE bot_id=? AND chat_id=? AND user_id=? AND destiny=?",
            (b, c, u, d),
        ) as cur:
            row = await cur.fetchone()
        return json.loads(row[0]) if row else {}

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None
