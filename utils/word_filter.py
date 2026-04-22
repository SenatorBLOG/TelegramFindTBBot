"""Blocked-words filter for anti-spam."""
from __future__ import annotations

import re

BLOCKED_WORDS: list[str] = [
    "crypto",
    "bitcoin",
    "btc",
    "invest",
    "investment",
    "forex",
    "onlyfans",
    "nude",
    "casino",
    "porn",
    "escort",
]

# Single compiled case-insensitive pattern for speed.
_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(w) for w in BLOCKED_WORDS) + r")\b",
    re.IGNORECASE,
)


def is_spam(text: str | None) -> bool:
    if not text:
        return False
    return bool(_PATTERN.search(text))
