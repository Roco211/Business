from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ConfirmationData(BaseModel):
    confirmation_id: str
    session_id: str
    task_run_id: str
    confirmation_type: str
    status: str
    fields: dict[str, Any]
    requested_by_employee_id: str | None
    resolution_payload: dict[str, Any] | None
    approved_by_actor_id: str | None
    created_at: datetime
    resolved_at: datetime | None


class ApproveConfirmationRequest(BaseModel):
    fields: dict[str, Any] = Field(default_factory=dict)


class ListConfirmationsMeta(BaseModel):
    count: int


class ListConfirmationsResponse(BaseModel):
    data: list[ConfirmationData]
    meta: ListConfirmationsMeta
