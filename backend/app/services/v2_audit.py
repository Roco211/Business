from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models import V2AuditLog
from app.services.v2_time import utc_now_naive


def append_v2_audit_log(
    db: Session,
    *,
    tenant_id: str,
    shop_id: str,
    action: str,
    actor_id: str,
    target_type: str | None = None,
    target_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    actor_type: str = "account",
    session_id: str | None = None,
    task_run_id: str | None = None,
) -> V2AuditLog:
    log = V2AuditLog(
        audit_log_id=f"vaudit_{uuid.uuid4().hex}"[:40],
        tenant_id=tenant_id,
        shop_id=shop_id,
        actor_type=actor_type,
        actor_id=actor_id,
        session_id=session_id,
        task_run_id=task_run_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        metadata_json=metadata or {},
        created_at=utc_now_naive(),
    )
    db.add(log)
    return log
