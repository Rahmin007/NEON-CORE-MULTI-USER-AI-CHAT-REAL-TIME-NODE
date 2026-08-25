from fastapi import APIRouter, Depends, Request

from app.api.dependencies import RequireRole, get_current_user
from app.db.mongo import activity_logs
from app.models.user import User, UserRole
from app.schemas.activity_log import ActivityEventCreate, ActivityLogResponse
from app.services.activity_service import log_activity

router = APIRouter(prefix="/logs", tags=["Activity Audit"])
admin_only = RequireRole([UserRole.ADMIN])


def _serialize(doc: dict) -> dict:
    doc["id"] = str(doc.pop("_id"))
    return doc


@router.get("/", response_model=list[ActivityLogResponse], dependencies=[Depends(admin_only)])
def get_activity_logs():
    rows = activity_logs.find().sort("created_at", -1).limit(500)
    return [_serialize(row) for row in rows]


@router.post("/event", status_code=201)
def create_event(payload: ActivityEventCreate, request: Request, current_user: User = Depends(get_current_user)):
    log_activity(
        current_user.id,
        current_user.username,
        payload.action,
        payload.details,
        request.client.host if request.client else None,
    )
    return {"ok": True}
