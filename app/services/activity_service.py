from sqlalchemy.orm import Session
from app.models.activity_log import ActivityLog

def log_activity(db: Session, user_id: int | None, action: str, details: str | None = None, ip_address: str | None = None):
    entry = ActivityLog(user_id=user_id, action=action, details=details, ip_address=ip_address)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry
