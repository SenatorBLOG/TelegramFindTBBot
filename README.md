# Find the Travel Buddy — Telegram Bot

An MVP Telegram bot that helps travellers find companions. Each user's profile
is published as its own **forum topic** inside a single supergroup, so the list
of profiles works like a list of chats — and tapping a profile drops you into
its dedicated discussion thread.

---

## Features

- Step-by-step profile wizard (9 steps, FSM-driven, aiogram 3)
- Each profile is published as a dedicated forum topic
- Guided search wizard (destination / dates / budget / style)
- Exactly one profile per user — edits refresh the same topic in place
- `TEST` / `PROD` modes via `.env`
- SQLite storage, zero external services
- Basic anti-spam (rate limiting + blocked-word filter)
- Admin `/release` command for announcements (optional pin)
- Local polling mode — no webhook infra required

---

## Requirements

- Python 3.11+
- A Telegram bot token from [@BotFather](https://t.me/BotFather)
- A Telegram **supergroup with forum topics enabled**
- Bot added as an **admin** of the group with these rights:
  - ✅ Manage topics
  - ✅ Delete messages
  - ✅ Pin messages (only needed for `/release --pin`)

### Enabling forum topics in your group

1. Open the group in Telegram
2. Tap the group title → **Edit** → **Topics**
3. Toggle **Topics ON**

Each profile will then become its own topic automatically.

---

## How the system works

- **Each profile = one forum topic** (thread) inside the group
- Tapping a profile in search results opens that topic — that's the "chat"
- Editing a profile refreshes the post inside the same topic (preserves history)
- The group itself is the single source of truth for all profiles; the bot just
  orchestrates topic creation, post formatting, and search

---

## Setup

```bash
git clone <this repo>
cd TelegramFindTBBot

python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
# Open .env and fill in BOT_TOKEN, ADMIN_USER_ID, group IDs

python main.py
```

### Finding your group's chat_id

1. Add the bot to the group and promote it to admin
2. Inside the group's General topic, send `/chatid`
3. The bot replies with the chat_id (a negative number like `-1001234567890`)
4. Paste it into `TEST_GROUP_ID` (or `PROD_GROUP_ID`) in `.env`

---

## Commands

| Command | Purpose |
|---|---|
| `/start` | Welcome message |
| `/help` | Show all commands |
| `/profile` | Create or edit your travel profile |
| `/myprofile` | Show your current profile + its topic link |
| `/search` | Find travellers (guided wizard) |
| `/cancel` | Cancel the current wizard |
| `/chatid` | Print the current chat id (run inside a group) |
| `/release <text> [--pin]` | Admin-only announcement |

---

## Architecture

Clean layered MVP:

```
handlers/        thin — receive updates, delegate to services
services/        business logic + orchestration
  ├─ profile_service   orchestrates DB + Topic API
  ├─ search_service    DB queries + topic-link building
  └─ topic_service     wrapper over Telegram forum-topic API
repositories/    SQL CRUD only (no business logic)
utils/           rate_limiter, word_filter, formatters
states/          FSM state groups
keyboards/       inline keyboard factories
constants.py     enums (TravelStyle, Budget, DateRange)
```

See design notes in [docs/superpowers/specs/](docs/superpowers/specs/).

---

## TEST vs PROD

In `.env`:

```env
MODE=TEST   # bot uses TEST_GROUP_ID
# MODE=PROD # bot uses PROD_GROUP_ID
```

Both group IDs can coexist in `.env`, so switching between a dev group and a
production group is a one-line edit — no hardcoded values anywhere.

---

## Project layout

```
main.py              entry point (polling)
config.py            .env loader → typed Config
bot.py               Bot + Dispatcher factory
db.py                aiosqlite connection + schema init
models.py            dataclasses (UserProfile, …)
constants.py         domain enums
handlers/            /start, /profile, /search, /admin, common
states/              FSM state groups
keyboards/           inline keyboard factories
services/            business logic
repositories/        SQL CRUD
utils/               rate_limiter, word_filter, formatters
data/                SQLite DB file (gitignored)
docs/                design notes
```

---

## License

MIT — use freely.
