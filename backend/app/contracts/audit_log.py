from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AuditLogData(BaseModel):
    audit_log_id: str
    shop_id: str
    scope: str
    action: str
    actor_type: str
    actor_id: str
    task_run_id: str | None
    target_type: str | None
    target_id: str | None
    metadata: dict[str, Any]
    created_at: datetime


class ListAuditLogsMeta(BaseModel):
    count: int


class ListAuditLogsResponse(BaseModel):
    data: list[AuditLogData]
    meta: ListAuditLogsMeta
