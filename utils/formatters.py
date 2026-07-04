"""Text formatters for profile displays and topic titles."""
from __future__ import annotations

from html import escape

from constants import (
    BUDGET_LABELS,
    TRAVEL_STYLE_LABELS,
    Budget,
    TravelStyle,
)
from models import UserProfile


def esc(value: str | None) -> str:
    """Escape user-supplied text for safe inclusion in HTML-parse-mode messages.

    The bot runs with parse_mode=HTML, so raw '<', '>', '&' in user input would
    either break Telegram entity parsing (publish fails) or let a user inject
    tags such as <a href> to spoof links inside a bot-authored card.
    """
    return escape(value or "", quote=False)


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
    """Human-readable HTML post for publishing inside a topic.

    All free-text user fields are HTML-escaped. `contact` is intentionally NOT
    escaped: it is bot-generated (either a plain @username, a tg://user anchor
    whose display name is escaped at the source in _auto_contact, or a fixed
    literal like "Imported from Facebook").
    """
    lines = [
        f"<b>✈️ {esc(profile.name)}</b>",
        "",
        f"📍 <b>From:</b> {esc(profile.from_location)}",
        f"🌍 <b>To:</b> {esc(profile.destination)}",
        f"📅 <b>Dates:</b> {esc(profile.dates)}",
        f"💰 <b>Budget:</b> {_budget_label(profile.budget)}",
        f"🧭 <b>Style:</b> {_style_label(profile.style)}",
        f"🗣 <b>Language:</b> {esc(profile.language)}",
    ]
    if profile.bio:
        lines.extend(["", f"📝 {esc(profile.bio)}"])
    if profile.contact:
        lines.extend(["", f"📨 <b>Contact:</b> {profile.contact}"])
    return "\n".join(lines)


def format_topic_title(profile: UserProfile) -> str:
    """Topic title — kept short, Telegram caps at 128 chars.

    Topic titles are plain text (not HTML-parsed), so no escaping is needed.
    """
    title = f"🌍 {profile.destination} | {profile.dates} | {profile.name}"
    return title[:128]
