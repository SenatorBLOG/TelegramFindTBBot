"""Destination normaliser: maps free-text destination → (canonical_name, flag_emoji).

Also provides year extraction from the dates wizard step for topic naming.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

# (keyword_lowercase, canonical_name, flag_emoji)
# Ordered longest-first where ambiguity exists (e.g. "south korea" before "korea").
_DEST_MAP: list[tuple[str, str, str]] = [
    # ── Asia ──────────────────────────────────────────────────────────────
    ("thailand",       "Thailand",     "🇹🇭"),
    ("тайланд",        "Thailand",     "🇹🇭"),
    ("bali",           "Bali",         "🇮🇩"),
    ("бали",           "Bali",         "🇮🇩"),
    ("indonesia",      "Indonesia",    "🇮🇩"),
    ("индонезия",      "Indonesia",    "🇮🇩"),
    ("vietnam",        "Vietnam",      "🇻🇳"),
    ("вьетнам",        "Vietnam",      "🇻🇳"),
    ("japan",          "Japan",        "🇯🇵"),
    ("япония",         "Japan",        "🇯🇵"),
    ("south korea",    "South Korea",  "🇰🇷"),
    ("южная корея",    "South Korea",  "🇰🇷"),
    ("korea",          "South Korea",  "🇰🇷"),
    ("корея",          "South Korea",  "🇰🇷"),
    ("singapore",      "Singapore",    "🇸🇬"),
    ("сингапур",       "Singapore",    "🇸🇬"),
    ("malaysia",       "Malaysia",     "🇲🇾"),
    ("малайзия",       "Malaysia",     "🇲🇾"),
    ("philippines",    "Philippines",  "🇵🇭"),
    ("филиппины",      "Philippines",  "🇵🇭"),
    ("cambodia",       "Cambodia",     "🇰🇭"),
    ("камбоджа",       "Cambodia",     "🇰🇭"),
    ("sri lanka",      "Sri Lanka",    "🇱🇰"),
    ("шри-ланка",      "Sri Lanka",    "🇱🇰"),
    ("шри ланка",      "Sri Lanka",    "🇱🇰"),
    ("maldives",       "Maldives",     "🇲🇻"),
    ("мальдивы",       "Maldives",     "🇲🇻"),
    ("taiwan",         "Taiwan",       "🇹🇼"),
    ("тайвань",        "Taiwan",       "🇹🇼"),
    ("china",          "China",        "🇨🇳"),
    ("китай",          "China",        "🇨🇳"),
    ("india",          "India",        "🇮🇳"),
    ("goa",            "India",        "🇮🇳"),
    ("индия",          "India",        "🇮🇳"),
    ("гоа",            "India",        "🇮🇳"),
    # ── Middle East ───────────────────────────────────────────────────────
    ("dubai",          "UAE",          "🇦🇪"),
    ("дубай",          "UAE",          "🇦🇪"),
    ("uae",            "UAE",          "🇦🇪"),
    ("оаэ",            "UAE",          "🇦🇪"),
    ("jordan",         "Jordan",       "🇯🇴"),
    ("иордания",       "Jordan",       "🇯🇴"),
    ("israel",         "Israel",       "🇮🇱"),
    ("израиль",        "Israel",       "🇮🇱"),
    # ── Caucasus & Central Asia ───────────────────────────────────────────
    ("georgia",        "Georgia",      "🇬🇪"),
    ("грузия",         "Georgia",      "🇬🇪"),
    ("armenia",        "Armenia",      "🇦🇲"),
    ("армения",        "Armenia",      "🇦🇲"),
    ("azerbaijan",     "Azerbaijan",   "🇦🇿"),
    ("азербайджан",    "Azerbaijan",   "🇦🇿"),
    ("kazakhstan",     "Kazakhstan",   "🇰🇿"),
    ("казахстан",      "Kazakhstan",   "🇰🇿"),
    # ── Africa ────────────────────────────────────────────────────────────
    ("egypt",          "Egypt",        "🇪🇬"),
    ("египет",         "Egypt",        "🇪🇬"),
    ("morocco",        "Morocco",      "🇲🇦"),
    ("марокко",        "Morocco",      "🇲🇦"),
    ("kenya",          "Kenya",        "🇰🇪"),
    ("кения",          "Kenya",        "🇰🇪"),
    ("south africa",   "South Africa", "🇿🇦"),
    ("южная африка",   "South Africa", "🇿🇦"),
    ("tanzania",       "Tanzania",     "🇹🇿"),
    ("танзания",       "Tanzania",     "🇹🇿"),
    ("zanzibar",       "Tanzania",     "🇹🇿"),
    ("занзибар",       "Tanzania",     "🇹🇿"),
    # ── Europe ────────────────────────────────────────────────────────────
    ("turkey",         "Turkey",       "🇹🇷"),
    ("турция",         "Turkey",       "🇹🇷"),
    ("spain",          "Spain",        "🇪🇸"),
    ("испания",        "Spain",        "🇪🇸"),
    ("italy",          "Italy",        "🇮🇹"),
    ("италия",         "Italy",        "🇮🇹"),
    ("greece",         "Greece",       "🇬🇷"),
    ("греция",         "Greece",       "🇬🇷"),
    ("france",         "France",       "🇫🇷"),
    ("франция",        "France",       "🇫🇷"),
    ("paris",          "France",       "🇫🇷"),
    ("париж",          "France",       "🇫🇷"),
    ("germany",        "Germany",      "🇩🇪"),
    ("германия",       "Germany",      "🇩🇪"),
    ("berlin",         "Germany",      "🇩🇪"),
    ("берлин",         "Germany",      "🇩🇪"),
    ("portugal",       "Portugal",     "🇵🇹"),
    ("португалия",     "Portugal",     "🇵🇹"),
    ("netherlands",    "Netherlands",  "🇳🇱"),
    ("нидерланды",     "Netherlands",  "🇳🇱"),
    ("голландия",      "Netherlands",  "🇳🇱"),
    ("amsterdam",      "Netherlands",  "🇳🇱"),
    ("амстердам",      "Netherlands",  "🇳🇱"),
    ("czech",          "Czech Republic","🇨🇿"),
    ("prague",         "Czech Republic","🇨🇿"),
    ("чехия",          "Czech Republic","🇨🇿"),
    ("прага",          "Czech Republic","🇨🇿"),
    ("hungary",        "Hungary",      "🇭🇺"),
    ("венгрия",        "Hungary",      "🇭🇺"),
    ("budapest",       "Hungary",      "🇭🇺"),
    ("будапешт",       "Hungary",      "🇭🇺"),
    ("austria",        "Austria",      "🇦🇹"),
    ("австрия",        "Austria",      "🇦🇹"),
    ("vienna",         "Austria",      "🇦🇹"),
    ("вена",           "Austria",      "🇦🇹"),
    ("switzerland",    "Switzerland",  "🇨🇭"),
    ("швейцария",      "Switzerland",  "🇨🇭"),
    ("poland",         "Poland",       "🇵🇱"),
    ("польша",         "Poland",       "🇵🇱"),
    ("romania",        "Romania",      "🇷🇴"),
    ("румыния",        "Romania",      "🇷🇴"),
    ("bulgaria",       "Bulgaria",     "🇧🇬"),
    ("болгария",       "Bulgaria",     "🇧🇬"),
    ("croatia",        "Croatia",      "🇭🇷"),
    ("хорватия",       "Croatia",      "🇭🇷"),
    ("montenegro",     "Montenegro",   "🇲🇪"),
    ("черногория",     "Montenegro",   "🇲🇪"),
    ("serbia",         "Serbia",       "🇷🇸"),
    ("сербия",         "Serbia",       "🇷🇸"),
    ("albania",        "Albania",      "🇦🇱"),
    ("албания",        "Albania",      "🇦🇱"),
    ("slovenia",       "Slovenia",     "🇸🇮"),
    ("словения",       "Slovenia",     "🇸🇮"),
    ("iceland",        "Iceland",      "🇮🇸"),
    ("исландия",       "Iceland",      "🇮🇸"),
    ("norway",         "Norway",       "🇳🇴"),
    ("норвегия",       "Norway",       "🇳🇴"),
    ("sweden",         "Sweden",       "🇸🇪"),
    ("швеция",         "Sweden",       "🇸🇪"),
    ("finland",        "Finland",      "🇫🇮"),
    ("финляндия",      "Finland",      "🇫🇮"),
    ("denmark",        "Denmark",      "🇩🇰"),
    ("дания",          "Denmark",      "🇩🇰"),
    ("united kingdom", "UK",           "🇬🇧"),
    ("england",        "UK",           "🇬🇧"),
    ("london",         "UK",           "🇬🇧"),
    ("лондон",         "UK",           "🇬🇧"),
    ("uk",             "UK",           "🇬🇧"),
    ("великобритания", "UK",           "🇬🇧"),
    # ── Americas ──────────────────────────────────────────────────────────
    ("united states",  "USA",          "🇺🇸"),
    ("america",        "USA",          "🇺🇸"),
    ("usa",            "USA",          "🇺🇸"),
    ("сша",            "USA",          "🇺🇸"),
    ("new york",       "USA",          "🇺🇸"),
    ("нью-йорк",       "USA",          "🇺🇸"),
    ("canada",         "Canada",       "🇨🇦"),
    ("канада",         "Canada",       "🇨🇦"),
    ("mexico",         "Mexico",       "🇲🇽"),
    ("мексика",        "Mexico",       "🇲🇽"),
    ("colombia",       "Colombia",     "🇨🇴"),
    ("колумбия",       "Colombia",     "🇨🇴"),
    ("argentina",      "Argentina",    "🇦🇷"),
    ("аргентина",      "Argentina",    "🇦🇷"),
    ("brazil",         "Brazil",       "🇧🇷"),
    ("бразилия",       "Brazil",       "🇧🇷"),
    ("cuba",           "Cuba",         "🇨🇺"),
    ("куба",           "Cuba",         "🇨🇺"),
    ("peru",           "Peru",         "🇵🇪"),
    ("перу",           "Peru",         "🇵🇪"),
    # ── Catch-all regions ─────────────────────────────────────────────────
    ("europe",         "Europe",       "🇪🇺"),
    ("европа",         "Europe",       "🇪🇺"),
    ("asia",           "Asia",         "🌏"),
    ("азия",           "Asia",         "🌏"),
    ("africa",         "Africa",       "🌍"),
    ("африка",         "Africa",       "🌍"),
    ("latin america",  "Latin America","🌎"),
    ("латинская",      "Latin America","🌎"),
]


def normalize_destination(destination: str) -> tuple[str, str]:
    """Return (canonical_name, flag_emoji) for a free-text destination.

    Tries every keyword; first match wins.
    Falls back to title-cased input + 🌍 if nothing matches.
    """
    d = destination.lower().strip()
    for keyword, name, flag in _DEST_MAP:
        if keyword in d:
            return name, flag
    return destination.strip().title(), "🌍"


def extract_year_for_topic(dates: str, date_range: Optional[str] = None) -> str:
    """Extract a 4-digit travel year from the dates string.

    Priority:
    1. Explicit year found in text (e.g. "June 2027")
    2. date_range == "next_3_months" in Q4 → next calendar year
    3. Current year as fallback
    """
    match = re.search(r"\b(202[5-9]|203\d)\b", dates or "")
    if match:
        return match.group(1)
    now = datetime.utcnow()
    if date_range == "next_3_months" and now.month >= 10:
        return str(now.year + 1)
    return str(now.year)
