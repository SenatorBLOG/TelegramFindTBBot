"""Basic user-facing commands (/start, /help, /cancel, /chatid)."""
from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from handlers.profile import render_my_profile
from keyboards.search_kb import get_search_destination_kb
from services.profile_service import ProfileService
from states.profile_states import ProfileFSM
from states.search_states import SearchFSM

router = Router(name="common")

WELCOME = (
    "👋 <b>Welcome to Find The Travel Buddy!</b>\n\n"
    "Here you can find travel companions for your next adventure 🌍\n\n"
    "<b>Quick start:</b>\n"
    "• /profile — create or edit your travel profile\n"
    "• /search — find other travelers\n"
    "• /myprofile — view your profile\n"
    "• /help — full command list"
)

HELP = (
    "<b>📚 Commands</b>\n\n"
    "/start — welcome message\n"
    "/profile — create or edit your travel profile\n"
    "/myprofile — view your profile + topic link\n"
    "/deleteprofile — delete your profile\n"
    "/search — find travel buddies (guided wizard)\n"
    "/cancel — cancel the current wizard\n"
    "/chatid — show this chat's id\n"
    "/help — this message\n\n"
    "<i>Admin only:</i>\n"
    "/release — post an announcement\n"
    "/stats — usage statistics\n"
    "/moderation — review pending profiles\n"
    "/spamlog — recently deleted spam\n"
    "/import — import a profile from Facebook"
)


@router.message(CommandStart())
async def cmd_start(
    message: Message,
    state: FSMContext,
    command: CommandObject,
    profile_service: ProfileService,
) -> None:
    # Deep link: t.me/bot?start=profile  →  start the profile wizard in DM
    if command.args == "profile" and message.chat.type == "private":
        await state.clear()
        await state.set_state(ProfileFSM.name)
        await message.answer(
            "📝 <b>Let's build your profile</b> (you can /cancel any time).\n\n"
            "<b>Step 1/9:</b> What's your name or nickname?"
        )
        return
    # Deep link: t.me/bot?start=search  →  start the search wizard in DM
    if command.args == "search" and message.chat.type == "private":
        await state.clear()
        await state.set_state(SearchFSM.destination)
        await message.answer(
            "🔍 <b>Find travel buddies</b>\n\n"
            "<b>Step 1/4:</b> 🌍 Where do you want to go?",
            reply_markup=get_search_destination_kb(),
        )
        return
    # Deep link: t.me/bot?start=myprofile  →  show the user's own profile
    if command.args == "myprofile" and message.chat.type == "private":
        await state.clear()
        await render_my_profile(message, profile_service)
        return
    await state.clear()
    await message.answer(WELCOME)


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP)


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    current = await state.get_state()
    await state.clear()
    if current:
        await message.answer("❌ Canceled.")
    else:
        await message.answer("Nothing to cancel.")


@router.message(Command("chatid"))
async def cmd_chatid(message: Message) -> None:
    thread = getattr(message, "message_thread_id", None)
    reply = f"<b>chat_id:</b> <code>{message.chat.id}</code>"
    if thread:
        reply += f"\n<b>message_thread_id:</b> <code>{thread}</code>"
    await message.answer(reply)
