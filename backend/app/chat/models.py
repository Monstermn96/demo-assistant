from pydantic import BaseModel
from datetime import datetime


class ChatRequest(BaseModel):
    message: str
    conversation_id: int | None = None
    model: str | None = None


class ChatResponse(BaseModel):
    conversation_id: int
    message: str
    model: str


class ConversationSummary(BaseModel):
    id: int
    title: str
    created_at: datetime
    updated_at: datetime


class MessageOut(BaseModel):
    id: int
    role: str
    content: str | None
    tool_calls: dict | list | None = None
    model: str | None
    agent_events: list | None = None
    created_at: datetime
