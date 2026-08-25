from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=10000)

class ChatResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    username: str | None = None
    sender_role: str
    message: str
    created_at: datetime

class OnlineUser(BaseModel):
    id: int
    username: str

class ModerationAction(BaseModel):
    reason: str = Field(default="", max_length=500)
