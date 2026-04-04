from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ConfirmationData(BaseModel):
    confirmation_id: str
    task_run_id: str
    confirmation_type: str
    status: str
    fields: dict[str, Any]
    requested_by_employee_id: str
    resolution_payload: dict[str, Any] | None
    approved_by_actor_id: str | None
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None
