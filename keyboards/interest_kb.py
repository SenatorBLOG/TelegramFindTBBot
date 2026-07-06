"""Inline keyboard for the 'I'm interested' button on profile cards."""
from __future__ import annotations

from typing import Optional

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def interest_kb(owner_id: int, count: int) -> Optional[InlineKeyboardMarkup]:
    """Build the interest button, or None for imported profiles.

    Imported profiles carry a synthetic negative owner_id and have no real
    Telegram account to notify, so they get no button (people use the contact
    shown in the card instead).
    """
    if owner_id < 0:
        return None
    label = f"👋 I'm interested ({count})" if count else "👋 I'm interested"
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=label, callback_data=f"interest:{owner_id}")
    ]])
