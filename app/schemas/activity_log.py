from datetime import datetime
from pydantic import BaseModel, ConfigDict

class ActivityLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    user_id: int | None
    username: str | None
    action: str
    details: dict | str | None
    ip_address: str | None
    created_at: datetime

class ActivityEventCreate(BaseModel):
    action: str
    details: dict | None = None
