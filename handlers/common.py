"""Basic user-facing commands (/start, /help, /cancel, /chatid)."""
from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from states.profile_states import ProfileFSM

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
    "/moderation — review pending profiles"
)


@router.message(CommandStart())
async def cmd_start(
    message: Message, state: FSMContext, command: CommandObject
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
