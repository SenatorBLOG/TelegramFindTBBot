"""Guided search wizard with 4 filter steps and pagination."""
from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from keyboards.search_kb import (
    get_search_budget_kb,
    get_search_date_kb,
    get_search_destination_kb,
    get_search_style_kb,
)
from services.search_service import SearchService, PAGE_SIZE
from states.search_states import SearchFSM
from utils.dm import is_private, redirect_to_dm
from utils.formatters import esc

router = Router(name="search")

# In-memory cache: user_id → (destination, date_range, budget, style)
_search_cache: dict[int, tuple[str | None, str | None, str | None, str | None]] = {}


# ─────────── /search ───────────

@router.message(Command("search"))
async def cmd_search(
    message: Message, state: FSMContext, bot: Bot, bot_username: str
) -> None:
    if not is_private(message):
        await redirect_to_dm(
            message, bot, bot_username,
            payload="search",
            button_text="🔍 Open search",
            hint="👆 Tap to search for travel buddies in a private chat with the bot.",
        )
        return
    await _start_search(message, state)


async def _start_search(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(SearchFSM.destination)
    await message.answer(
        "🔍 <b>Find travel buddies</b>\n\n"
        "<b>Step 1/4:</b> 🌍 Where do you want to go?",
        reply_markup=get_search_destination_kb(),
    )


# ─────────── step 1: destination ───────────

@router.callback_query(SearchFSM.destination, F.data.startswith("sdest:"))
async def sdest_cb(cb: CallbackQuery, state: FSMContext) -> None:
    value = cb.data.split(":", 1)[1]
    await cb.answer()
    if value == "manual":
        await cb.message.answer("✏️ Type the destination keyword:")
        return
    await state.update_data(destination=value)
    await _go_to_dates(cb.message, state)


@router.callback_query(SearchFSM.destination, F.data == "skip")
async def sdest_skip(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    await _go_to_dates(cb.message, state)


@router.message(SearchFSM.destination, F.text)
async def sdest_text(message: Message, state: FSMContext) -> None:
    await state.update_data(destination=message.text.strip()[:64])
    await _go_to_dates(message, state)


async def _go_to_dates(message: Message, state: FSMContext) -> None:
    await state.set_state(SearchFSM.date_range)
    await message.answer("<b>Step 2/4:</b> 📅 When?", reply_markup=get_search_date_kb())


# ─────────── step 2: date range ───────────

@router.callback_query(SearchFSM.date_range, F.data.startswith("sdate:"))
async def sdate_cb(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    await state.update_data(date_range=cb.data.split(":", 1)[1])
    await _go_to_budget(cb.message, state)


@router.callback_query(SearchFSM.date_range, F.data == "skip")
async def sdate_skip(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    await _go_to_budget(cb.message, state)


async def _go_to_budget(message: Message, state: FSMContext) -> None:
    await state.set_state(SearchFSM.budget)
    await message.answer("<b>Step 3/4:</b> 💰 Budget?", reply_markup=get_search_budget_kb())


# ─────────── step 3: budget ───────────

@router.callback_query(SearchFSM.budget, F.data.startswith("sbudget:"))
async def sbudget_cb(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    await state.update_data(budget=cb.data.split(":", 1)[1])
    await _go_to_style(cb.message, state)


@router.callback_query(SearchFSM.budget, F.data == "skip")
async def sbudget_skip(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    await _go_to_style(cb.message, state)


async def _go_to_style(message: Message, state: FSMContext) -> None:
    await state.set_state(SearchFSM.style)
    await message.answer("<b>Step 4/4:</b> 🧭 Travel style?", reply_markup=get_search_style_kb())


# ─────────── step 4: style → run search ───────────

@router.callback_query(SearchFSM.style, F.data.startswith("sstyle:"))
async def sstyle_cb(
    cb: CallbackQuery, state: FSMContext, search_service: SearchService
) -> None:
    await cb.answer()
    await state.update_data(style=cb.data.split(":", 1)[1])
    await _run_search(cb.message, state, search_service, cb.from_user.id)


@router.callback_query(SearchFSM.style, F.data == "skip")
async def sstyle_skip(
    cb: CallbackQuery, state: FSMContext, search_service: SearchService
) -> None:
    await cb.answer()
    await _run_search(cb.message, state, search_service, cb.from_user.id)


async def _run_search(
    message: Message, state: FSMContext, search_service: SearchService, user_id: int
) -> None:
    data = await state.get_data()
    await state.clear()

    params = (
        data.get("destination"),
        data.get("date_range"),
        data.get("budget"),
        data.get("style"),
    )
    _search_cache[user_id] = params
    await _show_page(message, search_service, user_id, offset=0)


# ─────────── pagination ───────────

async def _show_page(
    message: Message,
    search_service: SearchService,
    user_id: int,
    offset: int,
) -> None:
    params = _search_cache.get(user_id)
    if params is None:
        await message.answer("Search session expired. Please /search again.")
        return

    destination, date_range, budget, style = params

    # Fetch one extra to detect whether there's a next page
    results = await search_service.search(
        destination=destination,
        date_range=date_range,
        budget=budget,
        style=style,
        limit=PAGE_SIZE + 1,
        offset=offset,
    )

    has_more = len(results) > PAGE_SIZE
    results = results[:PAGE_SIZE]

    if not results:
        msg = (
            "😕 No travelers matched your filters. Try broader filters or come back later!"
            if offset == 0 else "No more results."
        )
        await message.answer(msg)
        return

    end = offset + len(results)
    lines = [f"🔍 <b>Travelers {offset + 1}–{end}:</b>\n"]
    buttons: list[list[InlineKeyboardButton]] = []

    for r in results:
        lines.append(f"• <b>{esc(r.name)}</b> → {esc(r.destination)} → {esc(r.dates)}")
        buttons.append([
            InlineKeyboardButton(text=f"💬 Chat with {r.name}", url=r.topic_link)
        ])

    if has_more:
        buttons.append([InlineKeyboardButton(
            text=f"👉 Next {PAGE_SIZE}",
            callback_data=f"sp:{user_id}:{offset + PAGE_SIZE}",
        )])

    await message.answer(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        disable_web_page_preview=True,
    )


@router.callback_query(F.data.startswith("sp:"))
async def search_next_page(cb: CallbackQuery, search_service: SearchService) -> None:
    await cb.answer()
    parts = cb.data.split(":")
    user_id = int(parts[1])
    offset = int(parts[2])
    await _show_page(cb.message, search_service, user_id, offset)
