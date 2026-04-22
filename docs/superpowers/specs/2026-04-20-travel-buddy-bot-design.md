# Find the Travel Buddy — Telegram Bot MVP Design

Date: 2026-04-20
Status: approved, implementing

## Purpose

Telegram bot that helps users find travel companions. Works inside a single
forum-enabled supergroup; each user profile is published as a separate forum
topic (thread). The list of profiles ≈ list of chats; tapping a profile
opens its discussion thread.

## Key decisions

- **Search UX:** guided wizard (4 steps: destination → date range → budget → style). Each step has a Skip button.
- **Profile editing:** edit-in-place — same topic is reused; the profile post inside is refreshed (old post deleted, new one sent).
- **Profiles per user:** exactly one, enforced at DB level (`UNIQUE` on `user_id`).
- **FSM storage:** `MemoryStorage` (acceptable; profile is always in DB, only in-flight wizard state is volatile).
- **DB:** SQLite via `aiosqlite` with raw SQL, no ORM.
- **Modes:** `MODE=TEST` / `MODE=PROD` in `.env` picks between `TEST_GROUP_ID` and `PROD_GROUP_ID`.
- **Architecture:** handlers → services → repositories. No business logic in handlers.

## Schema

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, created_at TEXT NOT NULL
);
CREATE TABLE profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    topic_id INTEGER,            -- forum message_thread_id (NULL until first publish)
    last_message_id INTEGER,     -- id of profile post inside the topic
    name TEXT NOT NULL,
    from_location TEXT NOT NULL,
    destination TEXT NOT NULL,
    dates TEXT NOT NULL,
    budget TEXT NOT NULL,        -- low | medium | high
    style TEXT NOT NULL,         -- chill | active | party | workation
    language TEXT NOT NULL,
    bio TEXT,
    contact TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX idx_profiles_destination ON profiles(destination);
```

## Topic API contract (TopicService)

- `create_topic(title) -> int` — returns message_thread_id
- `send_profile(topic_id, text) -> int` — returns message_id
- `update_profile(topic_id, old_message_id, new_text) -> int` — delete + resend, returns new message_id
- `build_topic_link(topic_id) -> str` — `https://t.me/c/<internal>/<topic_id>`

## ProfileService orchestration

1. Upsert profile row in DB.
2. If `topic_id` is NULL → create forum topic, send post, persist `topic_id` + `last_message_id`.
3. Else → delete old post, send new one, persist new `last_message_id`.
4. Return `(profile, topic_link)`.

## Anti-spam

- `RateLimiter` (N calls / window per user, in-memory).
- `word_filter.is_spam(text)` — compiled regex over blocked-word list.
- Middleware drops messages that match; attempts `delete_message` if bot has rights.

## Admin

- `/release <text> [--pin]` — only `ADMIN_USER_ID` may run; sends to group; optional pin.
