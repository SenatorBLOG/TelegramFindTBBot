"""Orchestrator for profile creation, editing, deletion, and moderation."""
from __future__ import annotations

import logging

from models import UserProfile
from repositories.profile_repo import ProfileRepository
from services.topic_service import TopicService
from utils.formatters import format_profile, format_topic_title

log = logging.getLogger(__name__)


class ProfileService:
    def __init__(self, profiles: ProfileRepository, topics: TopicService):
        self._profiles = profiles
        self._topics = topics

    async def get(self, user_id: int) -> UserProfile | None:
        return await self._profiles.get_by_user_id(user_id)

    def link_for(self, profile: UserProfile) -> str | None:
        if profile.topic_id is None:
            return None
        return self._topics.build_topic_link(profile.topic_id)

    # ─────────── publish flow ───────────

    async def save_and_publish(self, profile: UserProfile) -> tuple[UserProfile, str]:
        """
        Upsert profile → create or refresh topic → return (saved_profile, topic_link).
        """
        saved = await self._profiles.upsert(profile)
        text = format_profile(saved)

        if saved.topic_id is None:
            title = format_topic_title(saved)
            topic_id = await self._topics.create_topic(title)
            msg_id = await self._topics.send_profile(topic_id, text, saved.photo_file_id)
            await self._profiles.update_topic(saved.user_id, topic_id, msg_id)
            saved.topic_id = topic_id
            saved.last_message_id = msg_id
            log.info("Published profile user=%s topic=%s", saved.user_id, topic_id)
        else:
            new_msg_id = await self._topics.update_profile(
                saved.topic_id, saved.last_message_id, text, saved.photo_file_id
            )
            await self._profiles.update_last_message(saved.user_id, new_msg_id)
            saved.last_message_id = new_msg_id
            log.info("Refreshed profile user=%s topic=%s", saved.user_id, saved.topic_id)

        return saved, self._topics.build_topic_link(saved.topic_id)

    # ─────────── moderation flow ───────────

    async def save_pending(self, profile: UserProfile) -> UserProfile:
        """Save profile with status=pending. No topic is created yet."""
        profile.status = "pending"
        return await self._profiles.upsert(profile)

    async def approve(self, user_id: int) -> tuple[UserProfile, str] | None:
        """Approve a pending profile: publish to topic, return (profile, link)."""
        profile = await self._profiles.get_by_user_id(user_id)
        if not profile or profile.status != "pending":
            return None
        await self._profiles.update_status(user_id, "active")
        profile.status = "active"
        return await self.save_and_publish(profile)

    async def reject(self, user_id: int) -> UserProfile | None:
        """Reject a pending profile."""
        profile = await self._profiles.get_by_user_id(user_id)
        if not profile:
            return None
        await self._profiles.update_status(user_id, "rejected")
        profile.status = "rejected"
        return profile

    # ─────────── deletion ───────────

    async def delete(self, user_id: int) -> UserProfile | None:
        """Close the profile's topic and remove the DB record."""
        profile = await self._profiles.get_by_user_id(user_id)
        if not profile:
            return None
        if profile.topic_id is not None:
            await self._topics.close_topic(profile.topic_id)
        await self._profiles.delete(user_id)
        log.info("Deleted profile user=%s", user_id)
        return profile
