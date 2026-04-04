from fastapi import APIRouter, Depends, Header, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.contracts.audit_log import AuditLogData, ListAuditLogsMeta, ListAuditLogsResponse
from app.contracts.common import ErrorBody, ErrorEnvelope
from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.models import AuditLog
from app.services.audit_logs import UnsupportedAuditScopeError, list_audit_logs

router = APIRouter(prefix="/api/v1/audit-logs", tags=["audit-logs"])


def _unauthorized() -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content=ErrorEnvelope(
            error=ErrorBody(code="unauthorized", message="Unauthorized", details=[])
        ).model_dump(),
    )


def _unsupported_scope() -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ErrorEnvelope(
            error=ErrorBody(
                code="unsupported_audit_scope",
                message="Audit scope is not supported",
                details=[],
            )
        ).model_dump(),
    )


def _to_audit_log_data(item: AuditLog) -> AuditLogData:
    return AuditLogData(
        audit_log_id=item.audit_log_id,
        shop_id=item.shop_id,
        scope=item.scope,
        action=item.action,
        actor_type=item.actor_type,
        actor_id=item.actor_id,
        task_run_id=item.task_run_id,
        target_type=item.target_type,
        target_id=item.target_id,
        metadata=item.metadata_json,
        created_at=item.created_at,
    )


@router.get("", response_model=ListAuditLogsResponse)
def get_audit_logs(
    authorization: str | None = Header(default=None),
    scope: str = Query(default="inventory"),
    limit: int = Query(default=20, ge=1, le=50),
    settings: Settings = Depends(get_settings),
    db_session: Session = Depends(get_db_session),
) -> ListAuditLogsResponse | JSONResponse:
    if authorization != "Bearer mock_owner_token":
        return _unauthorized()
    try:
        page = list_audit_logs(
            db_session,
            shop_id=settings.default_shop_id,
            scope=scope,
            limit=limit,
        )
    except UnsupportedAuditScopeError:
        return _unsupported_scope()
    return ListAuditLogsResponse(
        data=[_to_audit_log_data(item) for item in page.items],
        meta=ListAuditLogsMeta(count=len(page.items)),
    )
