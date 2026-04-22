"""Text formatters for profile displays and topic titles."""
from __future__ import annotations

from constants import (
    BUDGET_LABELS,
    TRAVEL_STYLE_LABELS,
    Budget,
    TravelStyle,
)
from models import UserProfile


def _budget_label(value: str) -> str:
    try:
        return BUDGET_LABELS[Budget(value)]
    except (ValueError, KeyError):
        return value


def _style_label(value: str) -> str:
    try:
        return TRAVEL_STYLE_LABELS[TravelStyle(value)]
    except (ValueError, KeyError):
        return value


def format_profile(profile: UserProfile) -> str:
    """Human-readable HTML post for publishing inside a topic."""
    lines = [
        f"<b>✈️ {profile.name}</b>",
        "",
        f"📍 <b>From:</b> {profile.from_location}",
        f"🌍 <b>To:</b> {profile.destination}",
        f"📅 <b>Dates:</b> {profile.dates}",
        f"💰 <b>Budget:</b> {_budget_label(profile.budget)}",
        f"🧭 <b>Style:</b> {_style_label(profile.style)}",
        f"🗣 <b>Language:</b> {profile.language}",
    ]
    if profile.bio:
        lines.extend(["", f"📝 {profile.bio}"])
    if profile.contact:
        lines.extend(["", f"📨 <b>Contact:</b> {profile.contact}"])
    return "\n".join(lines)


def format_topic_title(profile: UserProfile) -> str:
    """Topic title — kept short, Telegram caps at 128 chars."""
    title = f"🌍 {profile.destination} | {profile.dates} | {profile.name}"
    return title[:128]
