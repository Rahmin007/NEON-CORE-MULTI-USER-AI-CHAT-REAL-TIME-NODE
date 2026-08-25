# NEON//CORE — Real-Time Multi-User AI Chat

This version turns the original per-user AI chat into a real multi-user public chat platform with an AI participant and RBAC.

## What changed

- Real-time public lobby using FastAPI WebSockets.
- Open the app in two or more browser windows and users see each other's messages instantly.
- Messages are persisted in SQLite/SQLAlchemy and loaded when a user joins.
- `@ai` is the only trigger for AI. Normal messages never call the AI API.
- AI replies are broadcast to everyone in the public lobby.
- Online-user presence is broadcast in real time.
- USER, MODERATOR and ADMIN have different permissions.
- Moderator console: delete messages, warn users, mute users for 10 minutes, view live users.
- Admin console: manage users, change roles, enable/disable accounts, and view the full activity log.
- Activity/audit logs (every login, chat message, moderation action, and tracked frontend interaction) are stored in MongoDB and visible to ADMIN only.
- Existing database gets a lightweight SQLite migration for `muted_until`.
- The AI key remains server-side in `.env`.

## Data storage

- **SQLite** (`chat.db`) — users and chat messages. Managed automatically via SQLAlchemy; no setup beyond `DATABASE_URL` in `.env`.
- **MongoDB** — the activity/audit log (`activity_logs` collection). Requires a reachable MongoDB instance — either a free [MongoDB Atlas](https://www.mongodb.com/cloud/atlas) cluster or a local instance (e.g. `docker run -d -p 27017:27017 mongo:7`). Set `MONGODB_URI` and `MONGODB_DB_NAME` in `.env`.

## Roles

### USER
- Register/login.
- Talk to other users in the public lobby.
- See online users.
- Ask AI with `@ai question`.

### MODERATOR
- Everything a USER can do.
- Delete inappropriate messages.
- Warn users.
- Mute users for 10 minutes.

### ADMIN
- Everything a MODERATOR can do.
- View all users.
- Change USER/MODERATOR roles.
- Enable/disable accounts.
- View the full activity log.
- Full administration access.

### AI
AI is a system participant, not a human account. It responds only when a message begins with `@ai`.

Example:

```text
Rahmin: Hello everyone
John: Hey Rahmin
Rahmin: @ai explain Docker
AI CORE: Docker is a containerization platform...
```

The first two messages do not call the AI.

## Run on Windows

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
copy .env.example .env
```

Fill in the real values in `.env`:

```text
OPENROUTER_API_KEY=your_real_key
OPENROUTER_MODEL=openrouter/free
MONGODB_URI=mongodb+srv://<user>:<password>@<cluster-host>/?retryWrites=true&w=majority
MONGODB_DB_NAME=neon_core
```

`MONGODB_URI` can also point at a local instance for development — run one with:

```powershell
docker run -d --name neon-core-mongo -p 27017:27017 mongo:7
```

then set `MONGODB_URI=mongodb://localhost:27017` in `.env`.

Then:

```powershell
uvicorn main:app --reload
```

Open `http://127.0.0.1:8000`.

## Testing multi-user chat

1. Register User A in Chrome.
2. Open an Incognito window or another browser.
3. Register User B.
4. Send `Hello` from User A.
5. User B should see it immediately.
6. Send `Hi` from User B.
7. User A should see it immediately.
8. Send `@ai what is TCP?` from either user.
9. Everyone connected should see the user's question and the AI response.

## API

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `GET /api/v1/users/me`
- `GET /api/v1/chat/history`
- `GET /api/v1/chat/online`
- `POST /api/v1/chat/`
- `WS /api/v1/chat/ws?token=<JWT>`
- `DELETE /api/v1/chat/{message_id}` — moderator/admin
- `POST /api/v1/chat/moderation/{user_id}/warn` — moderator/admin
- `POST /api/v1/chat/moderation/{user_id}/mute` — moderator/admin
- `GET /api/v1/admin/users` — admin
- `PATCH /api/v1/admin/users/{id}/role` — admin
- `PATCH /api/v1/admin/users/{id}/status` — admin
- `GET /api/v1/logs/` — admin only
- `POST /api/v1/logs/event` — any authenticated role; generic event tracking used by the frontend

## Production note

The in-memory WebSocket manager is suitable for a single FastAPI process. For multiple workers/servers, use Redis Pub/Sub or another shared broker so messages and presence are synchronized across processes. Add Alembic migrations, rate limiting, HTTPS, refresh-token/session management, and stronger moderation tooling before production.
