"""Orchestrator for profile creation, editing, deletion, and moderation."""
from __future__ import annotations

import asyncio
import logging

from aiogram import Bot

from keyboards.interest_kb import interest_kb
from models import UserProfile
from repositories.destination_topic_repo import DestinationTopicRepository
from repositories.interest_repo import InterestRepository
from repositories.profile_repo import ProfileRepository
from services.topic_service import TopicService
from utils.flags import extract_year_for_topic, normalize_destination
from utils.formatters import esc, format_profile, format_topic_title

log = logging.getLogger(__name__)


class ProfileService:
    def __init__(
        self,
        profiles: ProfileRepository,
        topics: TopicService,
        dest_topics: DestinationTopicRepository,
        interests: InterestRepository,
        bot: Bot,
    ):
        self._profiles = profiles
        self._topics = topics
        self._dest_topics = dest_topics
        self._interests = interests
        self._bot = bot

    async def get(self, user_id: int) -> UserProfile | None:
        return await self._profiles.get_by_user_id(user_id)

    def link_for(self, profile: UserProfile) -> str | None:
        """Return a direct link to the user's profile card message."""
        if profile.last_message_id is None:
            return None
        return self._topics.build_message_link(profile.last_message_id)

    # ─────────── destination-topic resolution ───────────

    async def _resolve_topic(self, profile: UserProfile) -> int:
        """Find or create the destination forum topic for this profile."""
        canonical, flag = normalize_destination(profile.destination)
        year = extract_year_for_topic(profile.dates, profile.date_range)

        topic_id = await self._dest_topics.get(canonical, year)
        if topic_id is None:
            title = f"{flag} {canonical} {year}"[:128]
            topic_id = await self._topics.create_topic(title)
            await self._dest_topics.save(canonical, year, topic_id)
            log.info("Created destination topic %r → %s", title, topic_id)
        return topic_id

    # ─────────── publish flow ───────────

    async def save_and_publish(self, profile: UserProfile) -> tuple[UserProfile, str | None]:
        """Upsert profile → post/update card in destination topic → return (saved, link).

        The profile is always saved to the database first.
        If posting to the group topic fails (bot not admin, topics disabled, etc.),
        the profile remains saved with status='active' but topic_id=None.
        In this case link is returned as None instead of raising.
        """
        saved = await self._profiles.upsert(profile)

        try:
            topic_id = await self._resolve_topic(saved)
        except Exception as e:
            log.error(
                "Could not resolve/create destination topic for user=%s: %s",
                saved.user_id, e,
            )
            return saved, None

        text = format_profile(saved)
        kb = interest_kb(saved.user_id, await self._interests.count(saved.user_id))

        try:
            # Same destination topic → edit the card in place (keeps position &
            # replies). New profile or changed destination → delete old, post fresh.
            if saved.topic_id == topic_id and saved.last_message_id is not None:
                msg_id = await self._topics.update_profile(
                    topic_id, saved.last_message_id, text, saved.photo_file_id, kb
                )
                is_new_card = False
            else:
                if saved.last_message_id is not None:
                    await self._topics.delete_message(saved.last_message_id)
                msg_id = await self._topics.send_profile(
                    topic_id, text, saved.photo_file_id, kb
                )
                is_new_card = True
        except Exception as e:
            log.error(
                "Could not post profile card for user=%s to topic=%s: %s",
                saved.user_id, topic_id, e,
            )
            return saved, None

        await self._profiles.update_topic(saved.user_id, topic_id, msg_id)
        saved.topic_id = topic_id
        saved.last_message_id = msg_id
        log.info("Published profile user=%s topic=%s msg=%s", saved.user_id, topic_id, msg_id)

        # Only a brand-new appearance in a topic triggers match alerts (not edits).
        if is_new_card:
            asyncio.create_task(self._alert_topic_mates(saved))

        return saved, self._topics.build_topic_link(topic_id)

    async def _alert_topic_mates(self, newcomer: UserProfile) -> None:
        """DM the other active travellers in this destination topic (best-effort)."""
        if newcomer.topic_id is None or newcomer.last_message_id is None:
            return
        try:
            mates = await self._profiles.list_active_by_topic(
                newcomer.topic_id, exclude_user_id=newcomer.user_id
            )
        except Exception as e:
            log.warning("Match-alert lookup failed: %s", e)
            return

        link = self._topics.build_message_link(newcomer.last_message_id)
        text = (
            f"🔥 <b>New traveller to {esc(newcomer.destination)}!</b>\n\n"
            f"✈️ <b>{esc(newcomer.name)}</b> — {esc(newcomer.dates)}\n\n"
            f'<a href="{link}">View their profile</a>'
        )
        sent = 0
        for mate in mates:
            try:
                await self._bot.send_message(
                    chat_id=mate.user_id, text=text, disable_web_page_preview=True
                )
                sent += 1
            except Exception:
                pass  # owner never opened the bot / blocked it — skip silently
        if sent:
            log.info("Match alert: notified %s traveller(s) in topic %s",
                     sent, newcomer.topic_id)

    # ─────────── moderation flow ───────────

    async def save_pending(self, profile: UserProfile) -> UserProfile:
        """Save profile with status=pending. No topic/message is created yet."""
        profile.status = "pending"
        return await self._profiles.upsert(profile)

    async def approve(self, user_id: int) -> tuple[UserProfile, str | None] | None:
        """Approve a pending profile: publish card to destination topic."""
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
        """Remove profile card from the destination topic and delete the DB record."""
        profile = await self._profiles.get_by_user_id(user_id)
        if not profile:
            return None
        # Delete just the profile message — do NOT close the destination topic
        # (it is shared among all travellers going to the same place).
        if profile.last_message_id is not None:
            await self._topics.delete_message(profile.last_message_id)
        await self._profiles.delete(user_id)
        log.info("Deleted profile user=%s", user_id)
        return profile
