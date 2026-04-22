"""Bot and Dispatcher factories."""
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from utils.fsm_storage import SQLiteStorage


def make_bot(token: str) -> Bot:
    return Bot(
        token=token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def make_dispatcher(fsm_path: Path) -> Dispatcher:
    return Dispatcher(storage=SQLiteStorage(fsm_path))
