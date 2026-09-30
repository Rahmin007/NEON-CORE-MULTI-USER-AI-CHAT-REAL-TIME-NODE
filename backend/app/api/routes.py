"""All HTTP and WebSocket routes, grouped by router."""
from __future__ import annotations

from datetime import timedelta

import jwt
from fastapi import APIRouter, Depends, HTTPException, Query, Request, WebSocket, WebSocketDisconnect, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

from app.core.security import create_access_token, decode_access_token, verify_password
from app.db import mongo
from app.schemas.models import (
    HUMAN_ROLES,
    STAFF_ROLES,
    ActivityEventIn,
    ActivityOut,
    AdminCreateUser,
    MessageIn,
    MessageOut,
    ModerationRequest,
    MuteRequest,
    OnlineUser,
    RegisterRequest,
    Role,
    RoleUpdate,
    StatsOut,
    StatusUpdate,
    TokenResponse,
    UserOut,
)
from app.services import store
from app.services.chat import (
    CLOSE_ACCOUNT_DISABLED,
    CLOSE_AUTH_FAILED,
    ChatError,
    handle_user_message,
    manager,
    muted_seconds_left,
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
HUMAN_ROLE_VALUES = {r.value for r in HUMAN_ROLES}


def client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


# ============================================================== dependencies
async def current_user(token: str = Depends(oauth2_scheme)) -> dict:
    unauthorized = HTTPException(
        status.HTTP_401_UNAUTHORIZED, "Your session has expired. Please log in again.", {"WWW-Authenticate": "Bearer"}
    )
    try:
        user_id = decode_access_token(token)
    except jwt.PyJWTError:
        raise unauthorized from None
    user = await store.get_user(user_id)
    if not user:
        raise unauthorized
    if not user.get("is_active", True):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account has been disabled.")
    return user


def require_roles(*roles: Role):
    allowed = {r.value for r in roles}

    async def checker(user: dict = Depends(current_user)) -> dict:
        if user["role"] not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You don't have permission to do that.")
        return user

    return checker


chat_member = require_roles(*HUMAN_ROLES)
staff = require_roles(*STAFF_ROLES)
admin = require_roles(Role.ADMIN)


# ============================================================== auth & me
auth_router = APIRouter(prefix="/auth", tags=["Authentication"])


@auth_router.post("/register", response_model=UserOut, status_code=201)
async def register(payload: RegisterRequest, request: Request):
    try:
        user = await store.create_user(payload.username, payload.email, payload.password)
    except store.AlreadyExists:
        raise HTTPException(409, "That username or email is already registered.") from None
    await store.log_activity(user, "REGISTER", None, client_ip(request))
    return store.user_out(user)


@auth_router.post("/login", response_model=TokenResponse)
async def login(request: Request, form: OAuth2PasswordRequestForm = Depends()):
    user = await store.get_user_by_username(form.username)
    if not user or not verify_password(form.password, user["hashed_password"]):
        await store.log_activity(user, "LOGIN_FAILED", {"username": form.username}, client_ip(request), form.username)
        raise HTTPException(401, "Incorrect username or password.", {"WWW-Authenticate": "Bearer"})
    if not user.get("is_active", True):
        raise HTTPException(403, "This account has been disabled.")
    await store.log_activity(user, "LOGIN_SUCCESS", None, client_ip(request))
    return {"access_token": create_access_token(str(user["_id"]), user["role"])}


users_router = APIRouter(prefix="/users", tags=["Users"])


@users_router.get("/me", response_model=UserOut)
async def me(user: dict = Depends(current_user)):
    return store.user_out(user)


@users_router.post("/me/warnings/{warning_id}/acknowledge")
async def acknowledge_warning(warning_id: str, request: Request, user: dict = Depends(current_user)):
    if not await store.acknowledge_warning(str(user["_id"]), warning_id):
        raise HTTPException(404, "Warning not found.")
    await store.log_activity(user, "WARNING_ACKNOWLEDGED", {"warning_id": warning_id}, client_ip(request))
    return {"ok": True}


# ============================================================== chat
chat_router = APIRouter(prefix="/chat", tags=["Chat"])


@chat_router.get("/history", response_model=list[MessageOut], dependencies=[Depends(chat_member)])
async def history(limit: int = Query(50, ge=1, le=100), before: str | None = None):
    return [store.message_out(m) for m in await store.message_history(limit, before)]


@chat_router.get("/online", response_model=list[OnlineUser], dependencies=[Depends(chat_member)])
async def online():
    return manager.online()


@chat_router.post("/messages", response_model=MessageOut, status_code=201)
async def send_message(payload: MessageIn, request: Request, user: dict = Depends(chat_member)):
    """REST alternative to sending over the WebSocket."""
    try:
        return await handle_user_message(user, payload.message, client_ip(request))
    except ChatError as exc:
        raise HTTPException(429 if exc.too_fast else 403, str(exc)) from None


@chat_router.websocket("/ws")
async def chat_socket(websocket: WebSocket):
    await websocket.accept()
    try:
        user = await store.get_user(decode_access_token(websocket.query_params.get("token", "")))
    except jwt.PyJWTError:
        user = None
    if not user or user["role"] not in HUMAN_ROLE_VALUES:
        await websocket.close(code=CLOSE_AUTH_FAILED, reason="Authentication failed")
        return
    if not user.get("is_active", True):
        await websocket.close(code=CLOSE_ACCOUNT_DISABLED, reason="Account disabled")
        return

    user_id = str(user["_id"])
    manager.add(user, websocket)
    # Muted users can still connect and read; they just can't send.
    await websocket.send_json({"type": "session", "muted_seconds": muted_seconds_left(user)})
    # Warnings given while the user was offline are shown as soon as they come back.
    for warning in await store.unacknowledged_warnings(user_id):
        await websocket.send_json({"type": "warning", "warning": store.warning_out(warning)})
    await manager.broadcast_presence()
    try:
        while True:
            data = await websocket.receive_json()
            if not isinstance(data, dict):
                continue
            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
                continue
            # Reload the user on every message so mutes, bans and role changes apply instantly.
            user = await store.get_user(user_id)
            if not user or not user.get("is_active", True):
                await websocket.close(code=CLOSE_ACCOUNT_DISABLED, reason="Account disabled")
                break
            try:
                await handle_user_message(user, str(data.get("message", "")))
            except ChatError as exc:
                await websocket.send_json({"type": "error", "message": str(exc)})
    except (WebSocketDisconnect, RuntimeError, ValueError):
        pass  # client left, or sent something that isn't JSON
    finally:
        manager.remove(user_id, websocket)
        await manager.broadcast_presence()


@chat_router.delete("/messages/{message_id}")
async def delete_message(message_id: str, request: Request, user: dict = Depends(staff)):
    if not await store.delete_message(message_id):
        raise HTTPException(404, "Message not found.")
    await store.log_activity(user, "MOD_DELETE_MESSAGE", {"message_id": message_id}, client_ip(request))
    await manager.broadcast({"type": "message_deleted", "message_id": message_id})
    return {"ok": True}


async def _moderation_target(target_id: str, actor: dict) -> dict:
    target = await store.get_user(target_id)
    if not target:
        raise HTTPException(404, "User not found.")
    if str(target["_id"]) == str(actor["_id"]):
        raise HTTPException(400, "You can't moderate yourself.")
    if actor["role"] == Role.MODERATOR.value and target["role"] != Role.USER.value:
        raise HTTPException(403, "Moderators can only moderate regular users.")
    return target


@chat_router.post("/moderation/{user_id}/warn")
async def warn_user(user_id: str, payload: ModerationRequest, request: Request, actor: dict = Depends(staff)):
    """Saves the warning, then shows it to the user now (if online) or the next time they connect."""
    target = await _moderation_target(user_id, actor)
    reason = payload.reason.strip() or "Please follow the chat rules."
    warning = await store.create_warning(target, actor, reason)
    await manager.send_to_user(user_id, {"type": "warning", "warning": store.warning_out(warning)})
    await store.log_activity(actor, "MOD_WARN_USER", {"target": target["username"], "reason": reason}, client_ip(request))
    return {"ok": True, "delivered": manager.is_online(user_id)}


@chat_router.post("/moderation/{user_id}/mute")
async def mute_user(user_id: str, payload: MuteRequest, request: Request, actor: dict = Depends(staff)):
    target = await _moderation_target(user_id, actor)
    until = store.utcnow() + timedelta(minutes=payload.minutes)
    await store.update_user(user_id, {"muted_until": until})
    await manager.send_to_user(user_id, {"type": "session", "muted_seconds": payload.minutes * 60})
    await manager.broadcast(
        {"type": "notice", "level": "warning", "message": f"{target['username']} was muted for {payload.minutes} minutes."}
    )
    await store.log_activity(
        actor,
        "MOD_MUTE_USER",
        {"target": target["username"], "minutes": payload.minutes, "reason": payload.reason},
        client_ip(request),
    )
    return {"ok": True, "muted_until": until}


@chat_router.post("/moderation/{user_id}/unmute")
async def unmute_user(user_id: str, request: Request, actor: dict = Depends(staff)):
    target = await _moderation_target(user_id, actor)
    await store.update_user(user_id, {"muted_until": None})
    await manager.send_to_user(user_id, {"type": "session", "muted_seconds": 0})
    await store.log_activity(actor, "MOD_UNMUTE_USER", {"target": target["username"]}, client_ip(request))
    return {"ok": True}


# ============================================================== admin
admin_router = APIRouter(prefix="/admin", tags=["Administration"], dependencies=[Depends(admin)])


@admin_router.get("/users", response_model=list[UserOut])
async def list_users(q: str = Query("", max_length=50)):
    return [store.user_out(u) for u in await store.list_users(q)]


@admin_router.post("/users", response_model=UserOut, status_code=201)
async def create_user(payload: AdminCreateUser, request: Request, actor: dict = Depends(admin)):
    try:
        user = await store.create_user(payload.username, payload.email, payload.password, payload.role)
    except store.AlreadyExists:
        raise HTTPException(409, "That username or email is already registered.") from None
    await store.log_activity(actor, "ADMIN_CREATE_USER", {"target": user["username"], "role": user["role"]}, client_ip(request))
    return store.user_out(user)


@admin_router.patch("/users/{user_id}/role", response_model=UserOut)
async def change_role(user_id: str, payload: RoleUpdate, request: Request, actor: dict = Depends(admin)):
    if user_id == str(actor["_id"]):
        raise HTTPException(400, "You can't change your own role.")
    user = await store.update_user(user_id, {"role": payload.role})
    if not user:
        raise HTTPException(404, "User not found.")
    manager.update_profile(user)
    await manager.broadcast_presence()
    await manager.send_to_user(user_id, {"type": "role_changed", "role": payload.role})
    await store.log_activity(actor, "ADMIN_CHANGE_ROLE", {"target": user["username"], "role": payload.role}, client_ip(request))
    return store.user_out(user)


@admin_router.patch("/users/{user_id}/status", response_model=UserOut)
async def change_status(user_id: str, payload: StatusUpdate, request: Request, actor: dict = Depends(admin)):
    if user_id == str(actor["_id"]):
        raise HTTPException(400, "You can't disable your own account.")
    user = await store.update_user(user_id, {"is_active": payload.is_active})
    if not user:
        raise HTTPException(404, "User not found.")
    if not payload.is_active:
        await manager.close_user(user_id, CLOSE_ACCOUNT_DISABLED, "Account disabled")
        await manager.broadcast_presence()
    await store.log_activity(
        actor, "ADMIN_CHANGE_STATUS", {"target": user["username"], "active": payload.is_active}, client_ip(request)
    )
    return store.user_out(user)


@admin_router.get("/stats", response_model=StatsOut)
async def stats():
    return {
        "users": await store.count_users(),
        "active_users": await store.count_users({"is_active": True}),
        "moderators": await store.count_users({"role": Role.MODERATOR.value}),
        "admins": await store.count_users({"role": Role.ADMIN.value}),
        "messages": await store.count_messages(),
        "online": len(manager.online()),
    }


# ============================================================== activity log
logs_router = APIRouter(prefix="/logs", tags=["Activity log"])


@logs_router.get("", response_model=list[ActivityOut], dependencies=[Depends(admin)])
async def activity_log(
    limit: int = Query(100, ge=1, le=500),
    action: str | None = Query(None, max_length=40),
    before: str | None = None,
):
    return [store.activity_out(row) for row in await store.list_activity(limit, action, before)]


@logs_router.post("/event", status_code=201)
async def track_event(payload: ActivityEventIn, request: Request, user: dict = Depends(current_user)):
    await store.log_activity(user, f"UI_{payload.action}", payload.details, client_ip(request))
    return {"ok": True}


# ============================================================== health
health_router = APIRouter(tags=["Health"])


@health_router.get("/health")
async def health():
    database_ok = await mongo.ping()
    return {"status": "ok" if database_ok else "degraded", "database": "connected" if database_ok else "unreachable"}


API_ROUTERS = [auth_router, users_router, chat_router, admin_router, logs_router]
