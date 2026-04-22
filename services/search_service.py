"""Search orchestration — DB query + topic-link enrichment + pagination."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from repositories.profile_repo import ProfileRepository
from services.topic_service import TopicService

PAGE_SIZE = 5


@dataclass
class SearchResult:
    name: str
    destination: str
    dates: str
    topic_link: str


class SearchService:
    def __init__(self, profiles: ProfileRepository, topics: TopicService):
        self._profiles = profiles
        self._topics = topics

    async def search(
        self,
        destination: Optional[str] = None,
        date_range: Optional[str] = None,
        budget: Optional[str] = None,
        style: Optional[str] = None,
        limit: int = PAGE_SIZE,
        offset: int = 0,
    ) -> list[SearchResult]:
        rows = await self._profiles.search(
            destination=destination,
            date_range=date_range,
            budget=budget,
            style=style,
            limit=limit,
            offset=offset,
        )
        return [
            SearchResult(
                name=p.name,
                destination=p.destination,
                dates=p.dates,
                topic_link=self._topics.build_topic_link(p.topic_id),
            )
            for p in rows
            if p.topic_id is not None
        ]
