"""Inline keyboard factories for the guided search wizard."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from constants import (
    BUDGET_LABELS,
    CB_SEARCH_BUDGET,
    CB_SEARCH_DATE,
    CB_SEARCH_DEST,
    CB_SEARCH_STYLE,
    CB_SKIP,
    DATE_RANGE_LABELS,
    POPULAR_DESTINATIONS,
    TRAVEL_STYLE_LABELS,
    Budget,
    DateRange,
    TravelStyle,
)


def _skip_row() -> list[InlineKeyboardButton]:
    return [InlineKeyboardButton(text="⏭ Skip", callback_data=CB_SKIP)]


def get_search_destination_kb() -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for flag, name in POPULAR_DESTINATIONS:
        row.append(
            InlineKeyboardButton(
                text=f"{flag} {name}",
                callback_data=f"{CB_SEARCH_DEST}:{name}",
            )
        )
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([
        InlineKeyboardButton(
            text="✏️ Type manually",
            callback_data=f"{CB_SEARCH_DEST}:manual",
        )
    ])
    rows.append(_skip_row())
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_search_date_kb() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(
            text=DATE_RANGE_LABELS[DateRange.THIS_MONTH],
            callback_data=f"{CB_SEARCH_DATE}:{DateRange.THIS_MONTH.value}",
        )],
        [InlineKeyboardButton(
            text=DATE_RANGE_LABELS[DateRange.NEXT_3_MONTHS],
            callback_data=f"{CB_SEARCH_DATE}:{DateRange.NEXT_3_MONTHS.value}",
        )],
        [InlineKeyboardButton(
            text=DATE_RANGE_LABELS[DateRange.FLEXIBLE],
            callback_data=f"{CB_SEARCH_DATE}:{DateRange.FLEXIBLE.value}",
        )],
        _skip_row(),
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_search_budget_kb() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(
            text=BUDGET_LABELS[Budget.LOW],
            callback_data=f"{CB_SEARCH_BUDGET}:{Budget.LOW.value}",
        )],
        [InlineKeyboardButton(
            text=BUDGET_LABELS[Budget.MEDIUM],
            callback_data=f"{CB_SEARCH_BUDGET}:{Budget.MEDIUM.value}",
        )],
        [InlineKeyboardButton(
            text=BUDGET_LABELS[Budget.HIGH],
            callback_data=f"{CB_SEARCH_BUDGET}:{Budget.HIGH.value}",
        )],
        _skip_row(),
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_search_style_kb() -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=TRAVEL_STYLE_LABELS[TravelStyle.CHILL],
                callback_data=f"{CB_SEARCH_STYLE}:{TravelStyle.CHILL.value}",
            ),
            InlineKeyboardButton(
                text=TRAVEL_STYLE_LABELS[TravelStyle.ACTIVE],
                callback_data=f"{CB_SEARCH_STYLE}:{TravelStyle.ACTIVE.value}",
            ),
        ],
        [
            InlineKeyboardButton(
                text=TRAVEL_STYLE_LABELS[TravelStyle.PARTY],
                callback_data=f"{CB_SEARCH_STYLE}:{TravelStyle.PARTY.value}",
            ),
            InlineKeyboardButton(
                text=TRAVEL_STYLE_LABELS[TravelStyle.WORKATION],
                callback_data=f"{CB_SEARCH_STYLE}:{TravelStyle.WORKATION.value}",
            ),
        ],
        _skip_row(),
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)
