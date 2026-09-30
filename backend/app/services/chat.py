"""Real-time chat: WebSocket connections, rate limits, the AI participant, and message handling."""
from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict, deque

from fastapi import WebSocket
from openai import AsyncOpenAI

from app.core.config import settings
from app.schemas.models import Role
from app.services import store

logger = logging.getLogger(__name__)

# Custom WebSocket close codes. The frontend stops reconnecting when it sees these.
CLOSE_AUTH_FAILED = 4401
CLOSE_ACCOUNT_DISABLED = 4403


class ChatError(Exception):
    """A problem the user should see (muted, too fast, etc.)."""

    def __init__(self, message: str, too_fast: bool = False) -> None:
        super().__init__(message)
        self.too_fast = too_fast


# ----------------------------------------------------------------- connections
class ConnectionManager:
    """Tracks open WebSockets per user. One user may have several tabs open."""

    def __init__(self) -> None:
        self.sockets: dict[str, set[WebSocket]] = defaultdict(set)
        self.profiles: dict[str, dict] = {}

    def add(self, user: dict, websocket: WebSocket) -> None:
        user_id = str(user["_id"])
        self.sockets[user_id].add(websocket)
        self.profiles[user_id] = {"id": user_id, "username": user["username"], "role": user["role"]}

    def remove(self, user_id: str, websocket: WebSocket) -> None:
        self.sockets[user_id].discard(websocket)
        if not self.sockets[user_id]:
            self.sockets.pop(user_id, None)
            self.profiles.pop(user_id, None)

    def update_profile(self, user: dict) -> None:
        user_id = str(user["_id"])
        if user_id in self.profiles:
            self.profiles[user_id].update({"username": user["username"], "role": user["role"]})

    def online(self) -> list[dict]:
        return sorted(self.profiles.values(), key=lambda p: p["username"].lower())

    def is_online(self, user_id: str) -> bool:
        return user_id in self.sockets

    async def broadcast(self, payload: dict) -> None:
        for user_id in list(self.sockets):
            await self.send_to_user(user_id, payload)

    async def send_to_user(self, user_id: str, payload: dict) -> None:
        for websocket in list(self.sockets.get(user_id, ())):
            try:
                await websocket.send_json(payload)
            except Exception:  # noqa: BLE001 - dead socket; its handler cleans up
                self.remove(user_id, websocket)

    async def close_user(self, user_id: str, code: int, reason: str) -> None:
        for websocket in list(self.sockets.get(user_id, ())):
            try:
                await websocket.close(code=code, reason=reason)
            except Exception:  # noqa: BLE001
                pass
            self.remove(user_id, websocket)

    async def broadcast_presence(self) -> None:
        await self.broadcast({"type": "presence", "users": self.online()})


manager = ConnectionManager()


# ----------------------------------------------------------------- rate limits
class RateLimiter:
    """Sliding window: at most `limit` events per `window` seconds per key."""

    def __init__(self, limit: int, window: float) -> None:
        self.limit, self.window = limit, window
        self.events: dict[str, deque] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        queue = self.events[key]
        while queue and now - queue[0] > self.window:
            queue.popleft()
        if len(queue) >= self.limit:
            return False
        queue.append(now)
        return True

    def reset(self) -> None:
        self.events.clear()


message_limiter = RateLimiter(settings.RATE_LIMIT_MESSAGES, settings.RATE_LIMIT_WINDOW_SECONDS)
ai_limiter = RateLimiter(1, settings.AI_COOLDOWN_SECONDS)
_ai_slots = asyncio.Semaphore(3)  # at most 3 AI requests at the same time
_background: set[asyncio.Task] = set()


# ----------------------------------------------------------------- AI
SYSTEM_PROMPT = (
    "You are AI CORE, the assistant inside NEON//CORE, a public multi-user chat room. "
    "Several people talk in the room; their messages are prefixed with their username. "
    "Answer the latest question helpfully, accurately and concisely. Use Markdown for code "
    "and lists. If you are not sure, say so."
)


async def generate_ai_reply(prompt: str, asked_by: str) -> str:
    if not settings.OPENROUTER_API_KEY:
        return "AI is not configured on this server yet. An admin needs to set `OPENROUTER_API_KEY`."

    recent = await store.message_history(limit=12)
    context = [
        {"role": "assistant", "content": m["message"]}
        if m["sender_role"] == Role.AI.value
        else {"role": "user", "content": f"{m['username']}: {m['message']}"}
        for m in recent[:-1]  # the last one is the question itself
    ]
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, *context, {"role": "user", "content": f"{asked_by}: {prompt}"}]

    client = AsyncOpenAI(
        api_key=settings.OPENROUTER_API_KEY,
        base_url="https://openrouter.ai/api/v1",
        default_headers={"X-Title": settings.PROJECT_NAME},
        timeout=settings.AI_TIMEOUT_SECONDS,
    )
    try:
        response = await client.chat.completions.create(
            model=settings.OPENROUTER_MODEL, messages=messages, temperature=0.7, max_tokens=800
        )
        return (response.choices[0].message.content or "").strip() or "I couldn't come up with an answer."
    finally:
        await client.close()


async def _answer_with_ai(prompt: str, asked_by: str) -> None:
    """Runs in the background so the chat never waits for the AI."""
    await manager.broadcast({"type": "ai_typing", "active": True, "requested_by": asked_by})
    try:
        async with _ai_slots:
            answer = await generate_ai_reply(prompt, asked_by)
        reply = await store.create_message(None, Role.AI.value, answer)
        await manager.broadcast({"type": "message", "message": _json(store.message_out(reply))})
    except Exception:  # noqa: BLE001 - the AI failing must never break the chat
        logger.exception("AI request failed")
        await manager.broadcast(
            {"type": "notice", "level": "error", "message": "AI CORE couldn't answer right now. Please try again in a moment."}
        )
    finally:
        await manager.broadcast({"type": "ai_typing", "active": False, "requested_by": asked_by})


# ----------------------------------------------------------------- messages
def _json(message: dict) -> dict:
    return {**message, "created_at": message["created_at"].isoformat()}


def muted_seconds_left(user: dict) -> int:
    until = store.as_utc(user.get("muted_until"))
    if not until:
        return 0
    return max(0, int((until - store.utcnow()).total_seconds()))


async def handle_user_message(user: dict, raw_text: str, ip_address: str | None = None) -> dict:
    """Validates, stores and broadcasts a message; starts the AI if it begins with @ai.

    `user` must be freshly loaded from the database so mutes/bans apply immediately."""
    text = (raw_text or "").strip()
    if not text:
        raise ChatError("Message cannot be empty.")
    if len(text) > settings.MAX_MESSAGE_LENGTH:
        raise ChatError(f"Messages can be at most {settings.MAX_MESSAGE_LENGTH} characters.")
    seconds = muted_seconds_left(user)
    if seconds:
        raise ChatError(f"You are muted for another {_duration(seconds)}.")
    user_id = str(user["_id"])
    if not message_limiter.allow(user_id):
        raise ChatError("You're sending messages too fast. Wait a few seconds.", too_fast=True)

    asks_ai = text.lower().startswith("@ai")
    prompt = text[3:].strip() if asks_ai else ""
    if asks_ai and prompt and not ai_limiter.allow(user_id):
        raise ChatError(f"You can ask the AI once every {settings.AI_COOLDOWN_SECONDS} seconds.", too_fast=True)

    saved = await store.create_message(user, user["role"], text)
    out = store.message_out(saved)
    await manager.broadcast({"type": "message", "message": _json(out)})
    await store.log_activity(user, "CHAT_MESSAGE", {"length": len(text), "ai": asks_ai}, ip_address)

    if asks_ai:
        if not prompt:
            await manager.send_to_user(user_id, {"type": "notice", "level": "info", "message": "Usage: @ai <your question>"})
        else:
            task = asyncio.create_task(_answer_with_ai(prompt, user["username"]))
            _background.add(task)
            task.add_done_callback(_background.discard)
    return out


def _duration(seconds: int) -> str:
    minutes, secs = divmod(seconds, 60)
    return f"{minutes}m {secs}s" if minutes else f"{secs}s"
