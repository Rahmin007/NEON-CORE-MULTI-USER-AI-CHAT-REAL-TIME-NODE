# Activity Log: SQLite → MongoDB Migration (Polyglot Persistence)

Date: 2026-08-25
Status: Approved for planning
Scope: Personal / demo project — not production-hardened

## Problem

Activity logs are currently stored as a SQLAlchemy/SQLite table (`ActivityLog`),
sharing a single-writer SQLite file with `User` and `ChatMessage`. The intended
use of the activity log is growing beyond a handful of fixed audit actions
(register, login, mod actions, admin actions) into a broader "everything the
user clicked/did" event stream with per-action-type metadata shapes. SQLite's
single-writer lock and fixed-column `details: str` field are a poor fit for
that: high write frequency and heterogeneous payload shapes.

## Decision

Adopt polyglot persistence:

- **SQL (SQLite, unchanged)** continues to hold `User` and `ChatMessage`,
  which need uniqueness constraints (username/email) and relational joins
  (message → username).
- **MongoDB (Atlas, managed, free-tier M0)** holds a single `activity_logs`
  collection for all audit/event data — both existing server-side actions
  and new lightweight frontend interaction events.

Rejected alternatives:
- **DynamoDB** — the app's only log-read query is a *global* "most recent 500
  across all users" feed, which is DynamoDB's classic weak spot (it wants a
  partition key to query by, not a global scan). Would require extra modeling
  (date-bucketed GSI) disproportionate to actual scale.
- **Just move SQLite → Postgres, stay relational** — legitimate lower-effort
  fix for the write-concurrency problem specifically, but doesn't give the
  per-action flexible metadata shape the user wants for the expanded
  click/event tracking. Rejected in favor of getting schema flexibility too.

## Architecture

```
FastAPI app
├── SQL (SQLite via SQLAlchemy) ── User, ChatMessage (unchanged)
└── MongoDB (Atlas)             ── activity_logs collection (new)
```

The rest of the app is unaware Mongo exists beyond the `log_activity()` call
sites, which keep their existing call signature minus the now-unused `db`
(SQLAlchemy session) argument.

## Components

- **Config** (`app/core/config.py`): add `MONGODB_URI`, `MONGODB_DB_NAME`,
  loaded via the existing `.env` loader.
- **`app/db/mongo.py`** (new, parallel to `app/db/session.py`): single
  `pymongo.MongoClient` instance, exposes the `activity_logs` collection.
  Uses sync `pymongo` (not `motor`) — some routes are `def` (sync), some are
  `async def` (chat/websocket); one sync client avoids maintaining two DB
  access styles. Blocking I/O inside async handlers is an acceptable
  trade-off at demo scale. On startup, ensure a descending index on
  `created_at` (mirrors the "clean init" spirit of `init_db()`, optional at
  this scale but cheap).
- **`app/services/activity_service.py`** (rewritten): `log_activity()`
  inserts a document into Mongo instead of a SQLAlchemy row. Wrapped in
  try/except — Mongo write failures are logged to console and swallowed;
  they must never break the calling request (chat send, login, etc.).
- **`app/models/activity_log.py`** — removed. `ActivityLog` also removed from
  `init_db()`'s model imports and required-table check in
  `app/db/session.py`.
- **`app/schemas/activity_log.py`** (rewritten): `id: str` (Mongo `_id`),
  `details: dict | str | None` (flexible shape instead of fixed string).
- **`app/api/v1/activity_logs.py`**: `GET /logs/` becomes **ADMIN-only**
  (dropping MODERATOR from this specific route — moderators keep their
  delete/warn/mute powers, just lose visibility into the raw log feed).
  Queries Mongo: `find().sort("created_at", -1).limit(500)`.
- **New route**: `POST /api/v1/logs/event` — any authenticated user, body
  `{action: str, details: dict | None}`. Calls the same `log_activity()`.
  This lets the frontend log meaningful interactions without a new backend
  route per event type.
- **Frontend** (`static/index.html`): a small `trackEvent(action, details)`
  JS helper wired to existing meaningful interaction points only — login,
  register, send message, delete/warn/mute, role/status change, logout, tab
  switches. No global click listener (rejected as noise, not insight, for a
  demo). New admin-only "ACTIVITY LOG" panel in `adminDash` that fetches
  `GET /api/v1/logs/` and renders a simple table (time, username, action,
  details).

## Data model

`activity_logs` collection, one document per event:

```json
{
  "_id": ObjectId(...),
  "user_id": 42,
  "username": "rahmin",
  "action": "CHAT_MESSAGE",
  "details": { "any": "shape appropriate to the action" },
  "ip_address": "127.0.0.1",
  "created_at": ISODate(...)
}
```

`username` is denormalized at write time since Mongo has no join — the admin
log view doesn't need a lookup back into SQL.

## Data flow

- **Write**: existing server-side call sites (auth, chat, moderation, admin)
  and the new `POST /api/v1/logs/event` frontend calls both funnel into
  `log_activity()` → one Mongo insert. Frontend events capture UI-level
  intent (which button/tab); server-side logs capture actual outcomes. Both
  can exist for the same user action (e.g. sending a chat message logs once
  server-side already; a frontend click event may also fire for actions with
  no existing server-side log, like switching to the register tab).
- **Read**: `GET /api/v1/logs/` (ADMIN-only) → Mongo query → rendered in the
  new admin dashboard panel.

## Error handling

`log_activity()` never propagates a Mongo failure to the caller — catches
the exception, logs to console, returns. A brief Mongo outage must not break
chat, login, or moderation actions.

## Testing

No existing automated test suite in this repo; given the demo scope, none is
being introduced for this change. Verification is manual:

1. Register/login/chat/mute a couple of test users.
2. Confirm entries land in the Mongo collection (Atlas web UI or the new
   admin log panel).
3. Confirm a MODERATOR now gets `403` on `GET /api/v1/logs/`, and a USER
   still cannot reach it either (unchanged).
4. Confirm a brief Mongo misconfiguration (e.g. wrong URI) does not prevent
   login/chat from working — only activity logging silently fails.

## Out of scope

- Any production hardening (retry queues, log shipping, alerting).
- Automated tests.
- Global click-capture instrumentation.
- Migrating `User` or `ChatMessage` off SQL.
- Backfilling existing SQLite `activity_logs` rows into Mongo (none of
  meaningful volume exist yet in this demo).

## Incidental cleanup

`.env.example` is referenced by the README's setup instructions but does not
exist in the repo. It will be created as part of this change, including the
new `MONGODB_URI` / `MONGODB_DB_NAME` variables alongside the existing ones.
