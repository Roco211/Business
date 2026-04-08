from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SessionStreamEventEnvelope(BaseModel):
    event_id: str
    seq: int
    event_type: str
    session_id: str
    task_run_id: str | None = None
    message_id: str | None = None
    occurred_at: datetime
    data: dict[str, Any] = Field(default_factory=dict)
