from datetime import datetime
from pydantic import BaseModel, ConfigDict

class ActivityLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int | None
    action: str
    details: str | None
    ip_address: str | None
    created_at: datetime
