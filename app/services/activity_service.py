import logging
from datetime import datetime, timezone

from app.db.mongo import activity_logs

logger = logging.getLogger(__name__)


def log_activity(
    user_id: int | None,
    username: str | None,
    action: str,
    details: dict | str | None = None,
    ip_address: str | None = None,
) -> None:
    try:
        activity_logs.insert_one(
            {
                "user_id": user_id,
                "username": username,
                "action": action,
                "details": details,
                "ip_address": ip_address,
                "created_at": datetime.now(timezone.utc),
            }
        )
    except Exception:
        logger.exception("Failed to write activity log for action=%s", action)
