"""Anti-spam text analysis: banned words, obfuscation folding, link detection.

Public API:
    is_spam(text)        -> bool     hard spam (banned words / invite links) — delete for everyone
    contains_link(text)  -> bool     any external link / @mention — used for newcomer quarantine
    spam_reason(text)    -> str|None  short label of why it matched (for the spam log)

Design notes
------------
Spammers obfuscate to slip past naive word lists. We defend with three passes:
  1. `norm`    — NFKC + lowercase + collapsed repeats/whitespace, matched with
                 word boundaries for ambiguous words (invest, bet, nude…).
  2. `compact` — norm stripped to letters/digits (spaces & dots gone), so
                 "к а з и н о" -> "казино" and "c-a-s-i-n-o" -> "casino".
  3. `folded`  — compact with Cyrillic look-alikes mapped to Latin, so a Latin
                 word disguised with Cyrillic glyphs ("саsіno") is caught.
Distinctive words are matched as substrings on compact/folded; short ambiguous
words only on word boundaries to avoid false positives ("escorted tour").
Because every deletion is forwarded to the admin with a "False positive" button,
we can afford to lean slightly aggressive.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Optional

# ─────────── word lists ───────────

# Distinctive enough to match anywhere (substring on compact/folded text).
_SUBSTR_WORDS: list[str] = [
    # EN — adult / gambling / finance spam
    "casino", "onlyfans", "pornhub", "bitcoin", "ethereum", "usdt", "forex",
    "viagra", "cialis", "xxx",
    # RU — the usual group-spam vocabulary
    "казино", "порно", "вебкам", "интим", "эскорт", "биткоин", "бинанс",
    "форекс", "крипт", "ставки", "ставок", "заработок", "зарабат", "промокод",
    "вложени", "инвестиц",
]

# Short / ambiguous — only match as standalone words to avoid false positives.
_BOUNDARY_WORDS: list[str] = [
    "crypto", "btc", "invest", "trading", "bet", "betting", "porn", "nude",
    "nudes", "escort", "sex", "loan",
    "доход", "займ", "кредит", "секс",
]

# Telegram invite / channel-join links — near-certain spam in a group.
_INVITE_RE = re.compile(
    r"(t\.me/(joinchat|\+)|telegram\.(me|dog)/(joinchat|\+)|chat\.whatsapp\.com)",
    re.IGNORECASE,
)

# Any external link or Telegram deep-link or long @mention — a *soft* signal,
# only actioned for newcomers (see SpamMiddleware quarantine).
_LINK_RE = re.compile(
    r"(https?://|www\.[a-z0-9-]+\.[a-z]{2,}"
    r"|\b[a-z0-9-]+\.(com|net|org|ru|io|me|xyz|top|shop|link|info|site|online|vip)\b"
    r"|t\.me/|telegram\.(me|dog)|wa\.me/|instagram\.com/|@[a-z0-9_]{5,})",
    re.IGNORECASE,
)

# Cyrillic (and a few digit) look-alikes → Latin, for the folded pass.
_LOOKALIKE = str.maketrans({
    "а": "a", "е": "e", "о": "o", "с": "c", "р": "p", "х": "x", "у": "y",
    "к": "k", "м": "m", "т": "t", "н": "h", "в": "b", "і": "i", "ѕ": "s",
    "ј": "j", "ԁ": "d", "ո": "n", "г": "r", "п": "n",
    "0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "$": "s",
})


# ─────────── normalization ───────────

def _normalize(text: str) -> str:
    """Lowercase, unicode-normalize, and collapse repeats + whitespace."""
    t = unicodedata.normalize("NFKC", text).lower()
    t = re.sub(r"(.)\1{2,}", r"\1\1", t)   # "caaaasino" -> "caasino"
    t = re.sub(r"\s+", " ", t)             # collapse whitespace runs
    return t.strip()


def _compact(norm: str) -> str:
    """Strip to letters/digits only: kills spacing & punctuation obfuscation.

    Keeps ALL Unicode letters (not just a-z/а-я) so look-alike glyphs from other
    Cyrillic blocks — і ѕ ј ԁ ո — survive to be folded to Latin afterwards.
    """
    return re.sub(r"[\W_]", "", norm, flags=re.UNICODE)


def _fold(compact: str) -> str:
    """Map Cyrillic look-alikes to Latin, then keep latin/digits only."""
    return re.sub(r"[^0-9a-z]", "", compact.translate(_LOOKALIKE))


# ─────────── public API ───────────

def spam_reason(text: str | None) -> Optional[str]:
    """Return a short reason label if the text is hard spam, else None."""
    if not text:
        return None
    norm = _normalize(text)

    if _INVITE_RE.search(norm):
        return "invite-link"

    compact = _compact(norm)
    folded = _fold(compact)
    for w in _SUBSTR_WORDS:
        if w in compact or w in folded:
            return f"word:{w}"

    for w in _BOUNDARY_WORDS:
        if re.search(rf"\b{re.escape(w)}\b", norm):
            return f"word:{w}"

    return None


def is_spam(text: str | None) -> bool:
    """Hard spam — should be deleted for everyone regardless of tenure."""
    return spam_reason(text) is not None


def contains_link(text: str | None) -> bool:
    """Soft signal: any external link / deep-link / long @mention.

    Used only to quarantine brand-new members; established members may share
    links freely.
    """
    if not text:
        return False
    return bool(_LINK_RE.search(_normalize(text)))
