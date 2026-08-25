from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import RequireRole, get_current_user
from app.core.security import decode_access_token
from app.db.session import SessionLocal, get_db
from app.models.chat import ChatMessage
from app.models.user import User, UserRole
from app.schemas.chat import ChatRequest, ChatResponse, OnlineUser, ModerationAction
from app.services.activity_service import log_activity
from app.services.ai_service import generate_ai_response
from app.services.chat_manager import manager

router = APIRouter(prefix="/chat", tags=["Multi-user Chat"])
CHAT_ROLES = [UserRole.USER, UserRole.MODERATOR, UserRole.ADMIN]
MOD_ROLES = [UserRole.MODERATOR, UserRole.ADMIN]


def serialize_message(db: Session, message: ChatMessage) -> dict:
    return {
        "id": message.id,
        "user_id": message.user_id,
        "username": "AI CORE" if message.sender_role == UserRole.AI.value else (message.user.username if message.user else "UNKNOWN"),
        "sender_role": message.sender_role,
        "message": message.message,
        "created_at": message.created_at.isoformat(),
    }


def check_muted(user: User):
    if not user.muted_until:
        return
    muted_until = user.muted_until
    if muted_until.tzinfo is None:
        muted_until = muted_until.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    if muted_until > now:
        seconds = int((muted_until - now).total_seconds())
        raise HTTPException(403, f"You are muted for another {max(seconds, 1)} seconds.")


@router.get("/history", response_model=list[ChatResponse], dependencies=[Depends(RequireRole(CHAT_ROLES))])
def chat_history(db: Session = Depends(get_db)):
    rows = db.scalars(select(ChatMessage).order_by(ChatMessage.id.desc()).limit(200)).all()
    return [serialize_message(db, row) for row in reversed(rows)]


@router.get("/online", response_model=list[OnlineUser], dependencies=[Depends(RequireRole(CHAT_ROLES))])
def online_users():
    return manager.online()


@router.post("/", response_model=ChatResponse, dependencies=[Depends(RequireRole(CHAT_ROLES))])
async def send_message(payload: ChatRequest, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    check_muted(current_user)
    text = payload.message.strip()
    user_msg = ChatMessage(user_id=current_user.id, sender_role=current_user.role.value, message=text)
    db.add(user_msg); db.commit(); db.refresh(user_msg)
    await manager.broadcast({"type": "message", "message": serialize_message(db, user_msg)})
    log_activity(db, current_user.id, "CHAT_MESSAGE", f"Prompt length: {len(text)}", request.client.host if request.client else None)

    if text.lower().startswith("@ai"):
        prompt = text[3:].strip()
        if not prompt:
            answer = "Usage: @ai <your question>"
        else:
            rows = db.scalars(select(ChatMessage).order_by(ChatMessage.id.desc()).limit(20)).all()
            history = [{"role": "assistant" if r.sender_role == UserRole.AI.value else "user", "content": r.message} for r in reversed(rows) if not r.message.lower().startswith("@ai")]
            answer = await generate_ai_response(prompt, history[-10:])
        ai_msg = ChatMessage(user_id=current_user.id, sender_role=UserRole.AI.value, message=answer)
        db.add(ai_msg); db.commit(); db.refresh(ai_msg)
        await manager.broadcast({"type": "message", "message": serialize_message(db, ai_msg)})
        return ai_msg

    return user_msg


@router.websocket("/ws")
async def websocket_chat(websocket: WebSocket):
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008, reason="Authentication required")
        return
    db = SessionLocal()
    user = None
    try:
        try:
            payload = decode_access_token(token)
            user_id = int(payload.get("sub"))
            user = db.get(User, user_id)
        except Exception:
            user = None
        if not user or not user.is_active or user.role not in CHAT_ROLES:
            await websocket.close(code=1008, reason="Authentication failed")
            return

        check_muted(user)
        await manager.connect(user.id, user.username, websocket)
        await manager.broadcast({"type": "presence", "users": manager.online()})

        while True:
            data = await websocket.receive_json()
            text = str(data.get("message", "")).strip()
            if not text or len(text) > 10000:
                await websocket.send_json({"type": "error", "message": "Message must be between 1 and 10000 characters."})
                continue
            try:
                check_muted(user)
            except HTTPException as exc:
                await websocket.send_json({"type": "error", "message": exc.detail})
                continue

            msg = ChatMessage(user_id=user.id, sender_role=user.role.value, message=text)
            db.add(msg); db.commit(); db.refresh(msg)
            await manager.broadcast({"type": "message", "message": serialize_message(db, msg)})
            log_activity(db, user.id, "CHAT_MESSAGE", f"Message length: {len(text)}", None)

            if text.lower().startswith("@ai"):
                prompt = text[3:].strip()
                if not prompt:
                    answer = "Usage: @ai <your question>"
                else:
                    rows = db.scalars(select(ChatMessage).order_by(ChatMessage.id.desc()).limit(20)).all()
                    history = [{"role": "assistant" if r.sender_role == UserRole.AI.value else "user", "content": r.message} for r in reversed(rows) if not r.message.lower().startswith("@ai")]
                    answer = await generate_ai_response(prompt, history[-10:])
                ai_msg = ChatMessage(user_id=user.id, sender_role=UserRole.AI.value, message=answer)
                db.add(ai_msg); db.commit(); db.refresh(ai_msg)
                await manager.broadcast({"type": "message", "message": serialize_message(db, ai_msg)})
    except WebSocketDisconnect:
        pass
    finally:
        if user:
            manager.disconnect(user.id, websocket)
            await manager.broadcast({"type": "presence", "users": manager.online()})
        db.close()


@router.delete("/{message_id}", dependencies=[Depends(RequireRole(MOD_ROLES))])
async def delete_message(message_id: int, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    msg = db.get(ChatMessage, message_id)
    if not msg:
        raise HTTPException(404, "Message not found.")
    db.delete(msg); db.commit()
    log_activity(db, current_user.id, "MOD_DELETE_MESSAGE", f"Deleted message {message_id}", request.client.host if request.client else None)
    await manager.broadcast({"type": "message_deleted", "message_id": message_id})
    return {"ok": True}


@router.post("/moderation/{user_id}/mute", dependencies=[Depends(RequireRole(MOD_ROLES))])
async def mute_user(user_id: int, payload: ModerationAction, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user: raise HTTPException(404, "User not found.")
    if user.role == UserRole.ADMIN and current_user.role != UserRole.ADMIN:
        raise HTTPException(403, "Moderators cannot mute administrators.")
    user.muted_until = datetime.now(timezone.utc) + timedelta(minutes=10)
    db.commit()
    log_activity(db, current_user.id, "MOD_MUTE_USER", f"Muted {user.username} for 10 minutes. {payload.reason}", request.client.host if request.client else None)
    await manager.broadcast({"type": "moderation", "message": f"{user.username} has been muted for 10 minutes."})
    return {"ok": True, "muted_until": user.muted_until}


@router.post("/moderation/{user_id}/warn", dependencies=[Depends(RequireRole(MOD_ROLES))])
async def warn_user(user_id: int, payload: ModerationAction, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user: raise HTTPException(404, "User not found.")
    log_activity(db, current_user.id, "MOD_WARN_USER", f"Warned {user.username}. {payload.reason}", request.client.host if request.client else None)
    return {"ok": True}
