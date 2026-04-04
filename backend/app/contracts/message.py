from datetime import datetime

from pydantic import BaseModel, Field


class CreateSessionMessageRequest(BaseModel):
    message_type: str
    text: str | None = None
    media_ids: list[str] = Field(default_factory=list)
    client_request_id: str


class CreateSessionMessageData(BaseModel):
    message_id: str
    task_run_id: str
    status: str


class SessionMessageItem(BaseModel):
    message_id: str
    session_id: str
    actor_type: str
    actor_id: str
    message_type: str
    text: str | None
    media_ids: list[str]
    task_run_id: str | None
    created_at: datetime


class SessionMessagesMeta(BaseModel):
    next_cursor: str | None = None


class SessionMessagesResponse(BaseModel):
    data: list[SessionMessageItem]
    meta: SessionMessagesMeta
