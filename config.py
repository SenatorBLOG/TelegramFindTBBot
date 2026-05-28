"""Typed configuration loaded from .env."""
from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


class Mode(str, Enum):
    TEST = "TEST"
    PROD = "PROD"


@dataclass(frozen=True)
class Config:
    bot_token: str
    mode: Mode
    group_id: int
    admin_user_id: int
    db_path: Path
    moderation: bool
    profiles_topic_id: Optional[int]
    webhook_url: Optional[str]
    webhook_path: str
    webhook_port: int

    @classmethod
    def load(cls) -> "Config":
        load_dotenv()

        bot_token = os.getenv("BOT_TOKEN", "").strip()
        if not bot_token:
            raise RuntimeError("BOT_TOKEN is required in .env")

        mode_raw = os.getenv("MODE", "TEST").strip().upper()
        try:
            mode = Mode(mode_raw)
        except ValueError as e:
            raise RuntimeError(f"MODE must be TEST or PROD, got: {mode_raw}") from e

        group_key = "TEST_GROUP_ID" if mode is Mode.TEST else "PROD_GROUP_ID"
        group_raw = os.getenv(group_key, "").strip()
        if not group_raw:
            raise RuntimeError(f"{group_key} is required when MODE={mode.value}")
        try:
            group_id = int(group_raw)
        except ValueError as e:
            raise RuntimeError(f"{group_key} must be an integer, got: {group_raw}") from e

        admin_raw = os.getenv("ADMIN_USER_ID", "").strip()
        if not admin_raw:
            raise RuntimeError("ADMIN_USER_ID is required in .env")
        try:
            admin_user_id = int(admin_raw)
        except ValueError as e:
            raise RuntimeError(f"ADMIN_USER_ID must be an integer, got: {admin_raw}") from e

        db_path = Path(os.getenv("DB_PATH", "data/bot.db"))
        try:
            db_path.parent.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            # Persistent disk not mounted yet (e.g. Render/Fly disk not attached).
            # Fall back to a local path so the bot starts rather than crashing.
            import logging as _log
            _log.warning(
                "Cannot create directory %s — disk not mounted. "
                "Falling back to data/bot.db (data will not persist across restarts).",
                db_path.parent,
            )
            db_path = Path("data/bot.db")
            db_path.parent.mkdir(parents=True, exist_ok=True)

        moderation = os.getenv("MODERATION", "false").strip().lower() == "true"

        profiles_topic_raw = os.getenv("PROFILES_TOPIC_ID", "").strip()
        profiles_topic_id: Optional[int] = int(profiles_topic_raw) if profiles_topic_raw else None

        webhook_url = os.getenv("WEBHOOK_URL", "").strip() or None
        webhook_path = os.getenv("WEBHOOK_PATH", "/webhook").strip()
        # Render injects PORT automatically; fall back to WEBHOOK_PORT for local/other hosts.
        port_raw = (os.getenv("PORT") or os.getenv("WEBHOOK_PORT", "10000")).strip()
        try:
            webhook_port = int(port_raw)
        except ValueError:
            webhook_port = 10000

        return cls(
            bot_token=bot_token,
            mode=mode,
            group_id=group_id,
            admin_user_id=admin_user_id,
            db_path=db_path,
            moderation=moderation,
            profiles_topic_id=profiles_topic_id,
            webhook_url=webhook_url,
            webhook_path=webhook_path,
            webhook_port=webhook_port,
        )
