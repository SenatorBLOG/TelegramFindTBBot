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
from handlers import admin, common, profile, search
from handlers import group as group_handler
from repositories.destination_topic_repo import DestinationTopicRepository
from repositories.profile_repo import ProfileRepository
from repositories.user_repo import UserRepository
from services.profile_service import ProfileService
from services.search_service import SearchService
from services.topic_service import TopicService
from utils.word_filter import is_spam

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
            try:
                await user_repo.upsert(user.id, user.username, user.first_name)
            except Exception as e:
                log.warning("user_repo.upsert failed: %s", e)
        return await handler(event, data)


class SpamMiddleware(BaseMiddleware):
    """Drop messages that contain blocked words; delete if bot has rights."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if isinstance(event, Message) and is_spam(event.text or event.caption):
            bot: Bot = data["bot"]
            log.info(
                "Spam blocked user=%s",
                event.from_user.id if event.from_user else "?",
            )
            try:
                await bot.delete_message(
                    chat_id=event.chat.id, message_id=event.message_id
                )
            except Exception:
                pass
            return  # halt the handler chain
        return await handler(event, data)


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


# ─────────── profiles tab index message ───────────

_INDEX_TEXT = (
    "✈️ <b>Find a Travel Buddy</b>\n\n"
    "Browse traveller profiles below and find your perfect trip companion.\n\n"
    "Ready to meet people? Tap the button to create your profile."
)
_INDEX_KEY = "profiles_index_msg_id"


async def post_profiles_index(
    bot: Bot,
    group_id: int,
    profiles_topic_id: int,
    bot_username: str,
    db_conn,
) -> None:
    """On startup: edit the existing index message if possible, otherwise post a new one.

    Storing the message_id in the `settings` table prevents duplicate messages
    every time Render restarts the process.
    """
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="📝 Create my profile",
            url=f"https://t.me/{bot_username}?start=profile",
        ),
    ]])

    # ── Try to edit the previously posted message ──────────────────────────
    async with db_conn.execute(
        "SELECT value FROM settings WHERE key = ?", (_INDEX_KEY,)
    ) as cur:
        row = await cur.fetchone()

    if row:
        try:
            await bot.edit_message_text(
                chat_id=group_id,
                message_id=int(row[0]),
                text=_INDEX_TEXT,
                reply_markup=kb,
                disable_web_page_preview=True,
            )
            log.info("Edited profiles index message %s", row[0])
            return
        except Exception:
            pass  # message was deleted — fall through and post a fresh one

    # ── Post a brand-new message and remember its ID ───────────────────────
    try:
        # Unpin everything in this topic first so we don't accumulate pinned messages
        try:
            await bot.unpin_all_forum_topic_messages(
                chat_id=group_id,
                message_thread_id=profiles_topic_id,
            )
        except Exception:
            pass  # might fail if no messages pinned — that's fine

        msg = await bot.send_message(
            chat_id=group_id,
            message_thread_id=profiles_topic_id,
            text=_INDEX_TEXT,
            reply_markup=kb,
            disable_web_page_preview=True,
        )
        await db_conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (_INDEX_KEY, str(msg.message_id)),
        )
        await db_conn.commit()
        # Pin only this one message
        try:
            await bot.pin_chat_message(
                chat_id=group_id,
                message_id=msg.message_id,
                disable_notification=True,
            )
        except Exception as pin_err:
            log.warning("Could not pin index message: %s", pin_err)
        log.info("Posted new profiles index message %s", msg.message_id)
    except Exception as e:
        log.warning("Could not post profiles index message: %s", e)


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

    # Bot + Dispatcher (FSM stored in a separate SQLite file)
    fsm_path = cfg.db_path.parent / "fsm.db"
    bot = make_bot(cfg.bot_token)
    dp = make_dispatcher(fsm_path)

    # Resolve bot username (needed for deep-link buttons)
    me = await bot.get_me()
    bot_username = me.username or ""

    # Services
    topic_service = TopicService(bot, cfg.group_id)
    profile_service = ProfileService(profile_repo, topic_service, dest_topic_repo)
    search_service = SearchService(profile_repo, topic_service)

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

    # Class-based middlewares
    dp.message.outer_middleware(TrackUserMiddleware())
    dp.callback_query.outer_middleware(TrackUserMiddleware())
    dp.message.outer_middleware(SpamMiddleware())

    # Routers
    dp.include_router(common.router)
    dp.include_router(profile.router)
    dp.include_router(search.router)
    dp.include_router(admin.router)
    dp.include_router(group_handler.router)

    # Startup permission check (non-fatal — just logs warnings)
    await check_permissions(bot, cfg.group_id)

    # Post profiles-tab index message (if the topic is configured)
    if cfg.profiles_topic_id:
        await post_profiles_index(
            bot, cfg.group_id, cfg.profiles_topic_id, bot_username, db.conn
        )

    try:
        if cfg.webhook_url and cfg.mode.value == "PROD":
            await _run_webhook(bot, dp, cfg)
        else:
            await bot.delete_webhook(drop_pending_updates=True)
            await dp.start_polling(
                bot, allowed_updates=dp.resolve_used_update_types()
            )
    finally:
        await bot.session.close()
        await db.close()
        storage = dp.storage
        if hasattr(storage, "close"):
            await storage.close()


async def _keepalive(webhook_url: str) -> None:
    """Ping our own health endpoint every 10 min to prevent Render free-tier spindown."""
    import aiohttp
    base = webhook_url.rstrip("/")
    while True:
        await asyncio.sleep(600)  # 10 minutes
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{base}/health", timeout=aiohttp.ClientTimeout(total=10)):
                    pass
            log.debug("Keepalive ping sent")
        except Exception as e:
            log.warning("Keepalive ping failed: %s", e)


async def _run_webhook(bot: Bot, dp, cfg: Config) -> None:
    from aiohttp import web
    from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

    url = f"{cfg.webhook_url.rstrip('/')}{cfg.webhook_path}"
    await bot.set_webhook(url=url, drop_pending_updates=True)
    log.info("Webhook set → %s", url)

    app = web.Application()
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=cfg.webhook_path)
    setup_application(app, dp, bot=bot)

    # Health-check endpoint — Render pings this to confirm the service is alive.
    async def health(_: web.Request) -> web.Response:
        return web.Response(text="ok")

    app.router.add_get("/", health)
    app.router.add_get("/health", health)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=cfg.webhook_port)
    await site.start()
    log.info("Webhook server on port %s", cfg.webhook_port)

    # Keep Render free tier alive by self-pinging every 10 min
    asyncio.create_task(_keepalive(cfg.webhook_url))

    await asyncio.Event().wait()  # run until interrupted


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log.info("Bot stopped.")
