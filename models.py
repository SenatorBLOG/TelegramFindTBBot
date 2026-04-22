"""Pure dataclass models mirroring DB rows."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class UserProfile:
    id: Optional[int]
    user_id: int
    topic_id: Optional[int]
    last_message_id: Optional[int]
    name: str
    from_location: str
    destination: str
    dates: str
    date_range: Optional[str]       # enum value: this_month / next_3_months / flexible
    budget: str
    style: str
    language: str
    bio: str
    photo_file_id: Optional[str]
    contact: str
    status: str                     # active | pending | rejected
    created_at: datetime
    updated_at: datetime
