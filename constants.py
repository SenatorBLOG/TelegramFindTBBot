"""Domain enums and display labels shared across the project."""
from enum import Enum


class Budget(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TravelStyle(str, Enum):
    CHILL = "chill"
    ACTIVE = "active"
    PARTY = "party"
    WORKATION = "workation"


class DateRange(str, Enum):
    THIS_MONTH = "this_month"
    NEXT_3_MONTHS = "next_3_months"
    FLEXIBLE = "flexible"


BUDGET_LABELS: dict[Budget, str] = {
    Budget.LOW: "💸 Low",
    Budget.MEDIUM: "💰 Medium",
    Budget.HIGH: "💎 High",
}

TRAVEL_STYLE_LABELS: dict[TravelStyle, str] = {
    TravelStyle.CHILL: "🧘 Chill",
    TravelStyle.ACTIVE: "🏃 Active",
    TravelStyle.PARTY: "🎉 Party",
    TravelStyle.WORKATION: "💻 Workation",
}

DATE_RANGE_LABELS: dict[DateRange, str] = {
    DateRange.THIS_MONTH: "📅 This month",
    DateRange.NEXT_3_MONTHS: "📆 Next 3 months",
    DateRange.FLEXIBLE: "🌤 Flexible",
}

# Human-readable labels for date_range values (used in profile display + wizard)
DATE_RANGE_DISPLAY: dict[str, str] = {
    DateRange.THIS_MONTH.value: "📅 This month",
    DateRange.NEXT_3_MONTHS.value: "📆 Next 3 months",
    DateRange.FLEXIBLE.value: "🌤 Flexible",
}

# Popular destination quick-picks (flag, name)
POPULAR_DESTINATIONS: list[tuple[str, str]] = [
    ("🇯🇵", "Japan"),
    ("🇪🇺", "Europe"),
    ("🇨🇦", "Canada"),
    ("🇹🇭", "Thailand"),
    ("🇬🇪", "Georgia"),
    ("🇹🇷", "Turkey"),
]

# Callback data prefixes (≤ 64 bytes total per callback)
CB_DEST = "dest"
CB_BUDGET = "budget"
CB_STYLE = "style"
CB_PROFILE_DATE = "pdate"       # profile wizard date-range selection
CB_SEARCH_DEST = "sdest"
CB_SEARCH_DATE = "sdate"
CB_SEARCH_BUDGET = "sbudget"
CB_SEARCH_STYLE = "sstyle"
CB_SKIP = "skip"
