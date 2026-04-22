"""Inline keyboard factories for the profile wizard."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from constants import (
    BUDGET_LABELS,
    CB_BUDGET,
    CB_DEST,
    CB_PROFILE_DATE,
    CB_STYLE,
    DATE_RANGE_LABELS,
    POPULAR_DESTINATIONS,
    TRAVEL_STYLE_LABELS,
    Budget,
    DateRange,
    TravelStyle,
)


def get_destination_kb() -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for flag, name in POPULAR_DESTINATIONS:
        row.append(InlineKeyboardButton(
            text=f"{flag} {name}", callback_data=f"{CB_DEST}:{name}"
        ))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="✏️ Type manually", callback_data=f"{CB_DEST}:manual")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_dates_kb() -> InlineKeyboardMarkup:
    """Quick-pick date-range buttons; user can also type specific dates as text."""
    rows = [
        [InlineKeyboardButton(
            text=DATE_RANGE_LABELS[DateRange.THIS_MONTH],
            callback_data=f"{CB_PROFILE_DATE}:{DateRange.THIS_MONTH.value}",
        )],
        [InlineKeyboardButton(
            text=DATE_RANGE_LABELS[DateRange.NEXT_3_MONTHS],
            callback_data=f"{CB_PROFILE_DATE}:{DateRange.NEXT_3_MONTHS.value}",
        )],
        [InlineKeyboardButton(
            text=DATE_RANGE_LABELS[DateRange.FLEXIBLE],
            callback_data=f"{CB_PROFILE_DATE}:{DateRange.FLEXIBLE.value}",
        )],
        [InlineKeyboardButton(
            text="✏️ Specific dates (type below)",
            callback_data=f"{CB_PROFILE_DATE}:manual",
        )],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_budget_kb() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=BUDGET_LABELS[Budget.LOW],    callback_data=f"{CB_BUDGET}:{Budget.LOW.value}")],
        [InlineKeyboardButton(text=BUDGET_LABELS[Budget.MEDIUM], callback_data=f"{CB_BUDGET}:{Budget.MEDIUM.value}")],
        [InlineKeyboardButton(text=BUDGET_LABELS[Budget.HIGH],   callback_data=f"{CB_BUDGET}:{Budget.HIGH.value}")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_style_kb() -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text=TRAVEL_STYLE_LABELS[TravelStyle.CHILL],    callback_data=f"{CB_STYLE}:{TravelStyle.CHILL.value}"),
            InlineKeyboardButton(text=TRAVEL_STYLE_LABELS[TravelStyle.ACTIVE],   callback_data=f"{CB_STYLE}:{TravelStyle.ACTIVE.value}"),
        ],
        [
            InlineKeyboardButton(text=TRAVEL_STYLE_LABELS[TravelStyle.PARTY],    callback_data=f"{CB_STYLE}:{TravelStyle.PARTY.value}"),
            InlineKeyboardButton(text=TRAVEL_STYLE_LABELS[TravelStyle.WORKATION],callback_data=f"{CB_STYLE}:{TravelStyle.WORKATION.value}"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_skip_photo_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⏭ Skip photo", callback_data="skip_photo")
    ]])


def get_delete_confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Yes, delete", callback_data="del_confirm"),
        InlineKeyboardButton(text="❌ Cancel",       callback_data="del_cancel"),
    ]])
