from datetime import datetime

from pydantic import BaseModel


class TaskRunData(BaseModel):
    task_run_id: str
    session_id: str
    source_message_id: str
    task_type: str
    status: str
    assigned_employee_id: str | None
    result_summary: str | None
    error_code: str | None
    error_message: str | None
    confirmation_id: str | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
