"""Entry point: wire up the bot, register routers, start polling or webhook."""
from __future__ import annotations

import asyncio
import logging
import sys
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware, Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, TelegramObject

from bot import make_bot, make_dispatcher
from config import Config
from db import Database
from handlers import admin, common, interest, profile, search
from handlers import group as group_handler
from repositories.destination_topic_repo import DestinationTopicRepository
from repositories.interest_repo import InterestRepository
from repositories.moderation_repo import ModerationRepository
from repositories.profile_repo import ProfileRepository
from repositories.user_repo import UserRepository
from services.index_service import IndexService
from services.profile_service import ProfileService
from services.search_service import SearchService
from services.topic_service import TopicService
from utils.formatters import esc
from utils.word_filter import contains_link, is_spam, spam_reason

log = logging.getLogger(__name__)


# ─────────── middlewares ───────────

class TrackUserMiddleware(BaseMiddleware):
    """Upsert the Telegram user record on every interaction."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user_repo: UserRepository | None = data.get("user_repo")
        user = getattr(event, "from_user", None)
        if user_repo and user and not user.is_bot:
            # Distinguish a real DM interaction from merely writing in the group.
            chat = getattr(event, "chat", None) or getattr(
                getattr(event, "message", None), "chat", None
            )
            is_private = bool(chat and chat.type == "private")
            try:
                await user_repo.upsert(
                    user.id, user.username, user.first_name, is_private=is_private
                )
            except Exception as e:
                log.warning("user_repo.upsert failed: %s", e)
        return await handler(event, data)


class SpamMiddleware(BaseMiddleware):
    """Delete spam in the group and alert the admin.

    Layers:
      1. Hard spam (banned words / invite links / money+link) — deleted for all.
      2. Forwarded + link — forwarded channel posts with a link are the classic
         "I withdrew $X, join t.me/…" scam; deleted for everyone regardless of
         tenure.
      3. Newcomer quarantine — a member in their first few messages / first 24h
         may not post links; established members can.
    Also runs on edited_message so "post benign, edit into spam" is caught.
    Only enforced inside the configured group; private chats are left alone.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not isinstance(event, Message):
            return await handler(event, data)

        group_id: int | None = data.get("group_id")
        user = event.from_user
        # Only police the configured group, and never the bot's own messages.
        if event.chat.id != group_id or not user or user.is_bot:
            return await handler(event, data)

        mod: ModerationRepository | None = data.get("mod_repo")
        text = event.text or event.caption

        reason = spam_reason(text)
        if reason is None:
            has_link = contains_link(text)
            # Forwarded message carrying a link → treat as spam for everyone.
            is_forwarded = bool(
                getattr(event, "forward_origin", None)
                or getattr(event, "forward_date", None)
                or getattr(event, "forward_from", None)
                or getattr(event, "forward_from_chat", None)
            )
            if has_link and is_forwarded:
                reason = "forwarded-link"
            elif mod is not None:
                try:
                    is_new = await mod.touch_member(event.chat.id, user.id)
                except Exception as e:
                    log.warning("touch_member failed: %s", e)
                    is_new = False
                if is_new and has_link:
                    reason = "newcomer-link"

        if reason is None:
            return await handler(event, data)

        # ── It's spam: delete, log, alert admin, halt the chain ──────────────
        bot: Bot = data["bot"]
        log.info("Spam blocked user=%s reason=%s", user.id, reason)
        try:
            await bot.delete_message(chat_id=event.chat.id, message_id=event.message_id)
        except Exception as e:
            log.warning("Could not delete spam message: %s", e)

        log_id: int | None = None
        if mod is not None:
            try:
                log_id = await mod.log_spam(
                    event.chat.id, user.id, user.username, text, reason
                )
            except Exception as e:
                log.warning("log_spam failed: %s", e)

        await self._alert_admin(bot, data, event, user, text, reason, log_id)
        return  # halt — do not pass spam to handlers

    async def _alert_admin(self, bot, data, event, user, text, reason, log_id) -> None:
        admin_id: int | None = data.get("admin_user_id")
        if not admin_id:
            return
        who = f"@{user.username}" if user.username else esc(user.full_name)
        preview = esc((text or "")[:300]) or "<i>(no text — media/caption)</i>"
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text="🔨 Ban user",
                callback_data=f"spam_ban:{event.chat.id}:{user.id}",
            ),
            InlineKeyboardButton(
                text="✅ Not spam",
                callback_data=f"spam_ok:{log_id or 0}",
            ),
        ]])
        try:
            await bot.send_message(
                chat_id=admin_id,
                text=(
                    f"🧹 <b>Spam deleted</b>\n\n"
                    f"👤 {who} (<code>{user.id}</code>)\n"
                    f"🏷 Reason: <code>{esc(reason)}</code>\n\n"
                    f"{preview}"
                ),
                reply_markup=kb,
                disable_web_page_preview=True,
            )
        except Exception as e:
            log.warning("Could not alert admin about spam: %s", e)


# ─────────── startup permission check ───────────

async def check_permissions(bot: Bot, group_id: int) -> None:
    try:
        chat = await bot.get_chat(group_id)
        if not getattr(chat, "is_forum", False):
            log.warning(
                "⚠️  Group %s does NOT have Topics enabled — "
                "go to group Settings → Topics to enable it.",
                group_id,
            )
        me = await bot.me()
        from aiogram.types import ChatMemberAdministrator
        member = await bot.get_chat_member(group_id, me.id)
        if isinstance(member, ChatMemberAdministrator):
            log.info("✅ Bot is admin in group %s", group_id)
        else:
            log.error(
                "❌ Bot is NOT an admin in group %s — "
                "topic creation will fail until this is fixed.",
                group_id,
            )
    except Exception as e:
        log.warning("Could not verify group permissions: %s", e)


# ─────────── main ───────────

async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout,
    )

    cfg = Config.load()
    log.info("Starting bot | MODE=%s  group=%s", cfg.mode.value, cfg.group_id)

    # Database
    db = Database(cfg.db_path)
    await db.connect()

    # Repositories
    profile_repo = ProfileRepository(db.conn)
    user_repo = UserRepository(db.conn)
    dest_topic_repo = DestinationTopicRepository(db.conn)
    mod_repo = ModerationRepository(db.conn)
    interest_repo = InterestRepository(db.conn)

    # Bot + Dispatcher (FSM stored in a separate SQLite file)
    fsm_path = cfg.db_path.parent / "fsm.db"
    bot = make_bot(cfg.bot_token)
    dp = make_dispatcher(fsm_path)

    # Resolve bot username (needed for deep-link buttons)
    me = await bot.get_me()
    bot_username = me.username or ""

    # Services
    topic_service = TopicService(bot, cfg.group_id)
    profile_service = ProfileService(
        profile_repo, topic_service, dest_topic_repo, interest_repo, bot
    )
    search_service = SearchService(profile_repo, topic_service)
    index_service = IndexService(
        bot, cfg.group_id, cfg.profiles_topic_id, bot_username, db.conn
    )

    # Inject into handler context
    dp["profile_service"] = profile_service
    dp["search_service"] = search_service
    dp["profile_repo"] = profile_repo
    dp["admin_user_id"] = cfg.admin_user_id
    dp["group_id"] = cfg.group_id
    dp["user_repo"] = user_repo
    dp["moderation"] = cfg.moderation
    dp["bot_username"] = bot_username
    dp["profiles_topic_id"] = cfg.profiles_topic_id
    dp["mod_repo"] = mod_repo
    dp["index_service"] = index_service
    dp["interest_repo"] = interest_repo

    # Class-based middlewares.
    # Spam runs FIRST (outer) so spammers are dropped before TrackUser records
    # them, and it also guards edited_message ("post benign, edit into spam").
    dp.message.outer_middleware(SpamMiddleware())
    dp.edited_message.outer_middleware(SpamMiddleware())
    dp.message.outer_middleware(TrackUserMiddleware())
    dp.callback_query.outer_middleware(TrackUserMiddleware())

    # Routers
    dp.include_router(common.router)
    dp.include_router(profile.router)
    dp.include_router(search.router)
    dp.include_router(interest.router)
    dp.include_router(admin.router)
    dp.include_router(group_handler.router)

    try:
        if cfg.webhook_url and cfg.mode.value == "PROD":
            await _run_webhook(bot, dp, cfg, index_service)
        else:
            await bot.delete_webhook(drop_pending_updates=True)
            # Background startup tasks for polling mode
            asyncio.create_task(_startup_tasks(bot, cfg, index_service))
            await dp.start_polling(
                bot, allowed_updates=dp.resolve_used_update_types()
            )
    finally:
        await bot.session.close()
        await db.close()
        storage = dp.storage
        if hasattr(storage, "close"):
            await storage.close()


async def _startup_tasks(bot, cfg, index_service: IndexService) -> None:
    """Non-critical startup tasks — run after server is ready.

    Note: index_service.refresh_silent() only edits the existing pinned message
    in place; it never posts a new one, so restarts stay invisible to the group.
    """
    await check_permissions(bot, cfg.group_id)
    if cfg.profiles_topic_id:
        await index_service.refresh_silent()


async def _run_webhook(bot: Bot, dp, cfg: Config, index_service: IndexService) -> None:
    from aiohttp import web
    from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

    app = web.Application()
    SimpleRequestHandler(
        dispatcher=dp, bot=bot, secret_token=cfg.webhook_secret
    ).register(app, path=cfg.webhook_path)
    setup_application(app, dp, bot=bot)

    async def health(_: web.Request) -> web.Response:
        return web.Response(text="ok")

    app.router.add_get("/", health)
    app.router.add_get("/health", health)

    # ── Start HTTP server FIRST so Fly.io health checks pass immediately ──────
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=cfg.webhook_port)
    await site.start()
    log.info("HTTP server listening on 0.0.0.0:%s", cfg.webhook_port)

    # ── Then register webhook and run startup tasks in background ─────────────
    url = f"{cfg.webhook_url.rstrip('/')}{cfg.webhook_path}"
    await bot.set_webhook(
        url=url,
        secret_token=cfg.webhook_secret,
        allowed_updates=dp.resolve_used_update_types(),
        drop_pending_updates=True,
    )
    if cfg.webhook_secret:
        log.info("Webhook set (secured with secret_token) → %s", url)
    else:
        log.warning(
            "Webhook set WITHOUT secret_token → %s — set WEBHOOK_SECRET to "
            "reject forged updates. See docs/DEVELOPMENT_PLAN.md P0-1.",
            url,
        )

    asyncio.create_task(_startup_tasks(bot, cfg, index_service))

    await asyncio.Event().wait()  # run until interrupted


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log.info("Bot stopped.")
