from app.core.ids import new_prefixed_id
from app.models import V2ModelCallLog
from app.services.v2_time import utc_now_naive


def append_v2_model_call_log(
    db_session,
    *,
    tenant_id: str,
    shop_id: str,
    context_session_id: str,
    requested_by_account_id: str,
    media_asset_id: str | None,
    task_run_id: str | None,
    conversation_session_id: str | None,
    provider_type: str,
    provider_key: str,
    model_name: str,
    operation_type: str,
    status: str,
    request_payload: dict[str, object] | None,
    response_payload: dict[str, object] | None,
    error_code: str | None,
    latency_ms: int | None,
    cost_micros: int | None,
) -> V2ModelCallLog:
    now = utc_now_naive()
    log = V2ModelCallLog(
        model_call_log_id=new_prefixed_id("vcall"),
        tenant_id=tenant_id,
        shop_id=shop_id,
        context_session_id=context_session_id,
        requested_by_account_id=requested_by_account_id,
        media_asset_id=media_asset_id,
        task_run_id=task_run_id,
        conversation_session_id=conversation_session_id,
        provider_type=provider_type.strip().lower(),
        provider_key=provider_key.strip(),
        model_name=model_name.strip(),
        operation_type=operation_type.strip(),
        status=status.strip().lower(),
        request_payload=request_payload,
        response_payload=response_payload,
        error_code=error_code,
        latency_ms=latency_ms,
        cost_micros=cost_micros,
        started_at=now,
        completed_at=now if status.strip().lower() == "completed" else None,
        created_at=now,
    )
    db_session.add(log)
    db_session.commit()
    return log
