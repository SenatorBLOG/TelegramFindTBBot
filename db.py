"""SQLite connection manager using aiosqlite."""
from __future__ import annotations

import logging
from pathlib import Path

import aiosqlite

log = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY,
    username    TEXT,
    first_name  TEXT,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS profiles (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL UNIQUE,
    topic_id        INTEGER,
    last_message_id INTEGER,
    name            TEXT NOT NULL,
    from_location   TEXT NOT NULL,
    destination     TEXT NOT NULL,
    dates           TEXT NOT NULL,
    date_range      TEXT,
    budget          TEXT NOT NULL,
    style           TEXT NOT NULL,
    language        TEXT NOT NULL,
    bio             TEXT,
    photo_file_id   TEXT,
    contact         TEXT,
    status          TEXT NOT NULL DEFAULT 'active',
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_profiles_destination ON profiles(destination);
CREATE INDEX IF NOT EXISTS idx_profiles_topic_id    ON profiles(topic_id);

CREATE TABLE IF NOT EXISTS destination_topics (
    destination TEXT NOT NULL,
    year        TEXT NOT NULL,
    topic_id    INTEGER NOT NULL,
    PRIMARY KEY (destination, year)
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

# Columns added after initial release — applied idempotently to existing DBs.
_MIGRATIONS: list[tuple[str, str, str]] = [
    ("profiles", "date_range",    "ALTER TABLE profiles ADD COLUMN date_range TEXT"),
    ("profiles", "photo_file_id", "ALTER TABLE profiles ADD COLUMN photo_file_id TEXT"),
    ("profiles", "status",        "ALTER TABLE profiles ADD COLUMN status TEXT NOT NULL DEFAULT 'active'"),
]


class Database:
    def __init__(self, path: Path):
        self._path = path
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self._conn = await aiosqlite.connect(self._path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.executescript(SCHEMA)
        await self._conn.commit()
        await self._migrate()
        log.info("Database ready at %s", self._path)

    async def _migrate(self) -> None:
        for table, column, sql in _MIGRATIONS:
            if not await self._column_exists(table, column):
                await self._conn.execute(sql)
                await self._conn.commit()
                log.info("Migration applied: ADD COLUMN %s.%s", table, column)

    async def _column_exists(self, table: str, column: str) -> bool:
        async with self._conn.execute(f"PRAGMA table_info({table})") as cur:
            rows = await cur.fetchall()
        return any(r["name"] == column for r in rows)

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("Database is not connected. Call connect() first.")
        return self._conn
