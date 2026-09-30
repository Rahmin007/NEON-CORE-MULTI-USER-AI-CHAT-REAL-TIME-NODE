# NEON//CORE — Real-time Multi-User AI Chat

[![Live demo](https://img.shields.io/badge/LIVE%20DEMO-neon--core--vert.vercel.app-00f6ff?style=for-the-badge)](https://neon-core-vert.vercel.app)
[![CI](https://github.com/Rahmin007/NEON-CORE-MULTI-USER-AI-CHAT-REAL-TIME-NODE/actions/workflows/ci.yml/badge.svg)](https://github.com/Rahmin007/NEON-CORE-MULTI-USER-AI-CHAT-REAL-TIME-NODE/actions)

**▶ Try it: [neon-core-vert.vercel.app](https://neon-core-vert.vercel.app)**. Register an account, then open the site in a second browser (or an incognito window) to chat with yourself in real time. Start a message with `@ai` to ask the AI.

> The backend runs on a free server that sleeps when nobody is using it, so the first visit can take about 50 seconds to wake up.

A public chat room where everyone sees each other's messages instantly, and an AI joins in when someone starts a message with `@ai`. Includes role-based moderation (warn, mute, delete), an admin console and a full activity log.

| Layer | Tech |
| --- | --- |
| Frontend | React 18, Vite, React Router, Tailwind CSS, react-markdown |
| Backend | Python, FastAPI, WebSockets, JWT (PyJWT), bcrypt |
| Database | MongoDB (PyMongo async driver): users, messages, warnings, activity log |
| AI | Any model on OpenRouter (OpenAI-compatible API) |
| Hosting | Vercel (frontend), Render (backend), MongoDB Atlas (database) |
| Tests | Pytest (25 tests), Vitest + Testing Library, GitHub Actions CI |

## Features

- **Real-time lobby** over WebSockets, with online presence and role badges.
- **AI participant:** `@ai <question>` gets an answer everyone can see.
  - The AI reads recent conversation for context and replies in Markdown.
  - It runs in the background with a "typing" indicator, so the chat never freezes while it thinks.
  - Each user can ask it once every 10 seconds.
- **Roles**
  - **USER:** chat and ask the AI.
  - **MODERATOR:** everything a user can do, plus delete messages and warn or mute regular users.
  - **ADMIN:** everything a moderator can do, plus create users, change roles, enable or disable accounts, view stats, and read the activity log.
- **Moderation takes effect instantly:**
  - A muted user's input is disabled with a countdown, but they can still read.
  - Warnings appear as a dialog the user must acknowledge. They're saved in MongoDB, so users who were offline see them when they next log in.
  - Disabled accounts are disconnected immediately.
- **Activity log in MongoDB:** logins, messages and moderation actions are recorded and filterable by action. Old entries expire automatically after 90 days (TTL index).
- **Safety:**
  - Message rate limiting and a length limit.
  - bcrypt password hashing and signed JWTs.
  - CORS restricted to your frontend.
  - Admins can't lock themselves out.
  - AI output is rendered without raw HTML.

## Project structure

```
backend/                 FastAPI app
  app/main.py            startup, CORS, routes
  app/api/routes.py      REST + WebSocket endpoints and role checks
  app/services/store.py  all MongoDB reads/writes
  app/services/chat.py   connections, rate limits, AI, message handling
  app/schemas/models.py  request/response models
  tests/                 pytest suite
frontend/                React app
  src/context/           auth, chat (WebSocket state), toasts
  src/hooks/             useChatSocket (auto-reconnect), useCountdown
  src/components/        messages, composer, online users, dialogs
  src/pages/             login/register, lobby, console, 404
render.yaml              one-click backend deploy on Render
START-HERE.bat           one-click local start on Windows
```

## Run locally

**Easiest (Windows):** double-click **`START-HERE.bat`**.
- It installs everything, starts the backend and frontend, and opens http://localhost:5173.
- Log in with `admin` / `admin12345`.
- It uses a temporary in-memory database, so data resets when you close it.

**Manual setup:** you need **Python 3.11+**, **Node.js 20.19+** and **MongoDB**. For MongoDB, use a free Atlas cluster, or run it locally with `docker run -d -p 27017:27017 mongo:7`.

Backend (terminal 1):

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r requirements-dev.txt
copy .env.example .env          # macOS/Linux: cp .env.example .env
# edit .env: MONGODB_URI, ADMIN_USERNAME / ADMIN_EMAIL / ADMIN_PASSWORD, OPENROUTER_API_KEY
uvicorn app.main:app --reload
```

Frontend (terminal 2):

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The admin account from `.env` is created automatically on first start. To test multi-user chat, open a second browser or an incognito window.

**Tests:** run `pytest` in `backend/`, and `npm test` in `frontend/`.

## Deploy

The live demo runs on free tiers:

| Part | Service | Notes |
| --- | --- | --- |
| Database | MongoDB Atlas (M0) | 512 MB free |
| Backend | Render web service | Sleeps after 15 min idle; first request then takes ~50 s |
| Frontend | Vercel | Root directory: `frontend`, env var `VITE_API_URL` |

Step-by-step instructions: **[docs/DEPLOY.md](docs/DEPLOY.md)**.

## API overview

| Method | Path | Who |
| --- | --- | --- |
| POST | `/api/v1/auth/register`, `/api/v1/auth/login` | anyone |
| GET | `/api/v1/users/me` | signed in |
| POST | `/api/v1/users/me/warnings/{id}/acknowledge` | signed in |
| GET | `/api/v1/chat/history?limit=&before=` · `/api/v1/chat/online` | users |
| WS | `/api/v1/chat/ws?token=<JWT>` | users |
| POST | `/api/v1/chat/messages` | users |
| DELETE | `/api/v1/chat/messages/{id}` | mod/admin |
| POST | `/api/v1/chat/moderation/{user_id}/warn · /mute · /unmute` | mod/admin |
| GET/POST/PATCH | `/api/v1/admin/users…`, `/api/v1/admin/stats` | admin |
| GET | `/api/v1/logs?action=&before=` | admin |
| GET | `/health` | anyone |

Interactive docs are available at `/docs` when `ENVIRONMENT` is not `production`.

## Scaling note

WebSocket connections are tracked in memory, so run the backend as **one process**. To scale to several servers, add Redis Pub/Sub so messages and presence are shared between them.