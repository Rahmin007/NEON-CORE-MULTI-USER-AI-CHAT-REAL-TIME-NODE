from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.dependencies import RequireRole
from app.db.session import get_db
from app.models.activity_log import ActivityLog
from app.models.user import UserRole
from app.schemas.activity_log import ActivityLogResponse

router = APIRouter(prefix="/logs", tags=["Activity Audit"])
logs_access = RequireRole([UserRole.ADMIN, UserRole.MODERATOR])

@router.get("/", response_model=list[ActivityLogResponse], dependencies=[Depends(logs_access)])
def get_activity_logs(db: Session = Depends(get_db)):
    return db.scalars(select(ActivityLog).order_by(ActivityLog.created_at.desc()).limit(500)).all()
