from datetime import datetime, timedelta, timezone
UTC = timezone.utc
from decimal import Decimal

from app.core.ids import new_prefixed_id
from app.db.session import get_session_factory
from app.models import AuditLog, Confirmation, MediaUpload, Message, SessionRecord, Shop, TaskRun
from app.runtime.processor import process_task_run
from app.services.bootstrap import ensure_default_context
from app.services.messages import create_message
from app.services.pilot_control import get_or_create_pilot_control
from conftest import auth_headers, login_and_get_token


def _auth_headers(client, monkeypatch=None) -> dict[str, str]:
    return auth_headers(login_and_get_token(client, monkeypatch))


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _create_shop_and_session(db_session, *, shop_id: str, session_id: str) -> SessionRecord:
    now = _now()
    shop = Shop(
        shop_id=shop_id,
        name=f"Shop {shop_id}",
        owner_name="Owner",
        industry="retail",
        locale="zh-CN",
        timezone="Asia/Shanghai",
        require_price_confirmation=True,
        require_new_item_confirmation=True,
        low_confidence_threshold=Decimal("0.8500"),
        default_low_stock_threshold=None,
        created_at=now,
        updated_at=now,
    )
    session = SessionRecord(
        session_id=session_id,
        shop_id=shop_id,
        session_type="workgroup",
        title=f"Session {session_id}",
        participants=["xiaoya"],
        last_event_seq=0,
        last_message_at=None,
        created_at=now,
        updated_at=now,
    )
    db_session.add(shop)
    db_session.add(session)
    db_session.flush()
    return session


def _insert_task_run(
    db_session,
    *,
    shop_id: str,
    session_id: str,
    task_type: str,
    status: str,
    created_at: datetime,
    completed_at: datetime | None = None,
    error_code: str | None = None,
) -> str:
    task_run_id = new_prefixed_id("task")
    message_id = new_prefixed_id("msg")
    db_session.add(
        Message(
            message_id=message_id,
            session_id=session_id,
            actor_type="owner",
            actor_id="owner_default",
            message_type="text",
            text=f"seed {task_type}",
            media_ids=[],
            client_request_id=f"seed_{task_run_id}",
            task_run_id=task_run_id,
            created_at=created_at,
        )
    )
    db_session.add(
        TaskRun(
            task_run_id=task_run_id,
            session_id=session_id,
            source_message_id=message_id,
            task_type=task_type,
            status=status,
            assigned_employee_id="xiaoya",
            result_summary=f"{task_type} {status}",
            error_code=error_code,
            error_message=error_code,
            created_at=created_at,
            updated_at=completed_at or created_at,
            completed_at=completed_at,
        )
    )
    db_session.flush()
    return task_run_id


def _insert_confirmation(
    db_session,
    *,
    task_run_id: str,
    status: str,
    created_at: datetime,
    resolved_at: datetime | None = None,
) -> None:
    db_session.add(
        Confirmation(
            confirmation_id=new_prefixed_id("conf"),
            task_run_id=task_run_id,
            confirmation_type="low-confidence-recognition",
            status=status,
            fields={"summary": "Confirm inventory action"},
            requested_by_employee_id="xiaoya",
            resolution_payload=None if resolved_at is None else {"decision": status},
            approved_by_actor_id=None if resolved_at is None else "owner_default",
            created_at=created_at,
            resolved_at=resolved_at,
        )
    )
    db_session.flush()


def _insert_provider_telemetry(
    db_session,
    *,
    shop_id: str,
    task_run_id: str,
    created_at: datetime,
    task_type: str,
    capability: str,
    provider_mode: str,
    provider_label: str,
    outcome: str,
    used_fallback: bool = False,
    recognized_confidence: float | None = None,
    low_confidence: bool = False,
    error_code: str | None = None,
    trial_provider_profile: str = "pilot-v1",
    cutover_mode: str | None = None,
    guardrail_status: str | None = None,
    guardrail_reason: str | None = None,
    shadow_forced_confirmation: bool | None = None,
    guardrail_degraded: bool | None = None,
    guardrail_degraded_reasons: list[str] | None = None,
) -> None:
    metadata_json: dict[str, object] = {
        "task_type": task_type,
        "capability": capability,
        "provider_mode": provider_mode,
        "provider_label": provider_label,
        "used_fallback": used_fallback,
        "recognized_confidence": recognized_confidence,
        "low_confidence": low_confidence,
        "outcome": outcome,
        "error_code": error_code,
        "trial_provider_profile": trial_provider_profile,
    }
    if cutover_mode is not None:
        metadata_json["cutover_mode"] = cutover_mode
    if guardrail_status is not None:
        metadata_json["guardrail_status"] = guardrail_status
    if guardrail_reason is not None:
        metadata_json["guardrail_reason"] = guardrail_reason
    if shadow_forced_confirmation is not None:
        metadata_json["shadow_forced_confirmation"] = shadow_forced_confirmation
    if guardrail_degraded is not None:
        metadata_json["guardrail_degraded"] = guardrail_degraded
    if guardrail_degraded_reasons is not None:
        metadata_json["guardrail_degraded_reasons"] = list(guardrail_degraded_reasons)

    db_session.add(
        AuditLog(
            audit_log_id=new_prefixed_id("audit"),
            shop_id=shop_id,
            scope="pilot",
            action="runtime.provider_telemetry",
            actor_type="system",
            actor_id="runtime_system",
            task_run_id=task_run_id,
            target_type="task_run",
            target_id=task_run_id,
            metadata_json=metadata_json,
            created_at=created_at,
        )
    )
    db_session.flush()


def _create_receipt_runtime_task(db_session, *, media_id: str, client_request_id: str) -> str:
    context = ensure_default_context(db_session)
    db_session.add(
        MediaUpload(
            media_id=media_id,
            shop_id=context.shop.shop_id,
            uploader_actor_type="owner",
            uploader_actor_id="owner_default",
            media_type="receipt-image",
            file_name=f"{media_id}.bin",
            content_type="application/octet-stream",
            size_bytes=1024,
            status="uploaded",
            upload_url=f"https://mock.example/uploads/{media_id}",
            public_url=f"https://mock.example/media/{media_id}",
            checksum_sha256="abc123",
            uploaded_at=context.session.created_at,
            created_at=context.session.created_at,
            updated_at=context.session.created_at,
        )
    )
    db_session.commit()
    result = create_message(
        db_session,
        session_id=context.session.session_id,
        actor_type="owner",
        actor_id="owner_default",
        message_type="receipt-image",
        text=None,
        media_ids=[media_id],
        client_request_id=client_request_id,
    )
    return result.task_run_id


def _create_voice_runtime_task(db_session, *, media_id: str, client_request_id: str) -> str:
    context = ensure_default_context(db_session)
    db_session.add(
        MediaUpload(
            media_id=media_id,
            shop_id=context.shop.shop_id,
            uploader_actor_type="owner",
            uploader_actor_id="owner_default",
            media_type="audio",
            file_name=f"{media_id}.bin",
            content_type="application/octet-stream",
            size_bytes=1024,
            status="uploaded",
            upload_url=f"https://mock.example/uploads/{media_id}",
            public_url=f"https://mock.example/media/{media_id}",
            checksum_sha256="abc123",
            uploaded_at=context.session.created_at,
            created_at=context.session.created_at,
            updated_at=context.session.created_at,
        )
    )
    db_session.commit()
    result = create_message(
        db_session,
        session_id=context.session.session_id,
        actor_type="owner",
        actor_id="owner_default",
        message_type="voice",
        text=None,
        media_ids=[media_id],
        client_request_id=client_request_id,
    )
    return result.task_run_id


def test_pilot_summary_endpoint_requires_owner_auth(client) -> None:
    response = client.get("/api/v1/system/pilot-summary")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_pilot_summary_endpoint_returns_recent_aggregates_for_the_authenticated_shop(
    client,
    monkeypatch,
) -> None:
    monkeypatch.setenv("TRIAL_PROVIDER_PROFILE", "pilot-v1")

    db_session = get_session_factory()()
    try:
        context = ensure_default_context(db_session)
        now = _now()

        completed_voice_task = _insert_task_run(
            db_session,
            shop_id=context.shop.shop_id,
            session_id=context.session.session_id,
            task_type="voice-stock-query",
            status="completed",
            created_at=now - timedelta(hours=3),
            completed_at=now - timedelta(hours=3) + timedelta(minutes=1),
        )
        awaiting_photo_task = _insert_task_run(
            db_session,
            shop_id=context.shop.shop_id,
            session_id=context.session.session_id,
            task_type="photo-stock-in",
            status="awaiting-confirmation",
            created_at=now - timedelta(hours=2),
        )
        approved_photo_task = _insert_task_run(
            db_session,
            shop_id=context.shop.shop_id,
            session_id=context.session.session_id,
            task_type="photo-stock-in",
            status="completed",
            created_at=now - timedelta(hours=2),
            completed_at=now - timedelta(hours=2) + timedelta(minutes=5),
        )
        rejected_photo_task = _insert_task_run(
            db_session,
            shop_id=context.shop.shop_id,
            session_id=context.session.session_id,
            task_type="photo-stock-in",
            status="rejected",
            created_at=now - timedelta(hours=1),
            completed_at=now - timedelta(hours=1) + timedelta(minutes=4),
        )
        failed_voice_task = _insert_task_run(
            db_session,
            shop_id=context.shop.shop_id,
            session_id=context.session.session_id,
            task_type="voice-stock-query",
            status="failed",
            created_at=now - timedelta(minutes=45),
            completed_at=now - timedelta(minutes=40),
            error_code="asr_low_confidence",
        )
        failed_photo_task = _insert_task_run(
            db_session,
            shop_id=context.shop.shop_id,
            session_id=context.session.session_id,
            task_type="photo-stock-query",
            status="failed",
            created_at=now - timedelta(minutes=30),
            completed_at=now - timedelta(minutes=25),
            error_code="vision_unavailable",
        )

        _insert_confirmation(
            db_session,
            task_run_id=awaiting_photo_task,
            status="pending",
            created_at=now - timedelta(hours=2),
        )
        _insert_confirmation(
            db_session,
            task_run_id=approved_photo_task,
            status="approved",
            created_at=now - timedelta(hours=2),
            resolved_at=now - timedelta(hours=2) + timedelta(minutes=10),
        )
        _insert_confirmation(
            db_session,
            task_run_id=rejected_photo_task,
            status="rejected",
            created_at=now - timedelta(hours=1),
            resolved_at=now - timedelta(hours=1) + timedelta(minutes=10),
        )

        _insert_provider_telemetry(
            db_session,
            shop_id=context.shop.shop_id,
            task_run_id=completed_voice_task,
            created_at=now - timedelta(hours=3),
            task_type="voice-stock-query",
            capability="asr",
            provider_mode="real-provider",
            provider_label="asr-primary",
            outcome="completed",
            recognized_confidence=0.98,
        )
        _insert_provider_telemetry(
            db_session,
            shop_id=context.shop.shop_id,
            task_run_id=awaiting_photo_task,
            created_at=now - timedelta(hours=2),
            task_type="photo-stock-in",
            capability="vision",
            provider_mode="real-provider",
            provider_label="vision-primary",
            outcome="awaiting-confirmation",
            recognized_confidence=0.92,
        )
        _insert_provider_telemetry(
            db_session,
            shop_id=context.shop.shop_id,
            task_run_id=approved_photo_task,
            created_at=now - timedelta(hours=2),
            task_type="photo-stock-in",
            capability="vision",
            provider_mode="real-provider",
            provider_label="vision-primary",
            outcome="completed",
            used_fallback=False,
            recognized_confidence=0.91,
        )
        _insert_provider_telemetry(
            db_session,
            shop_id=context.shop.shop_id,
            task_run_id=approved_photo_task,
            created_at=now - timedelta(hours=2) + timedelta(seconds=5),
            task_type="photo-stock-in",
            capability="vision",
            provider_mode="real-provider",
            provider_label="vision-primary",
            outcome="completed",
            used_fallback=True,
            recognized_confidence=0.90,
        )
        _insert_provider_telemetry(
            db_session,
            shop_id=context.shop.shop_id,
            task_run_id=failed_voice_task,
            created_at=now - timedelta(minutes=40),
            task_type="voice-stock-query",
            capability="asr",
            provider_mode="real-provider",
            provider_label="asr-primary",
            outcome="failed",
            recognized_confidence=0.42,
            low_confidence=True,
            error_code="asr_low_confidence",
        )
        _insert_provider_telemetry(
            db_session,
            shop_id=context.shop.shop_id,
            task_run_id=failed_photo_task,
            created_at=now - timedelta(minutes=25),
            task_type="photo-stock-query",
            capability="vision",
            provider_mode="real-provider",
            provider_label="vision-primary",
            outcome="failed",
            error_code="vision_unavailable",
        )

        out_of_window_task = _insert_task_run(
            db_session,
            shop_id=context.shop.shop_id,
            session_id=context.session.session_id,
            task_type="voice-stock-query",
            status="completed",
            created_at=now - timedelta(hours=30),
            completed_at=now - timedelta(hours=30) + timedelta(minutes=1),
        )
        _insert_provider_telemetry(
            db_session,
            shop_id=context.shop.shop_id,
            task_run_id=out_of_window_task,
            created_at=now - timedelta(hours=30),
            task_type="voice-stock-query",
            capability="asr",
            provider_mode="real-provider",
            provider_label="asr-primary",
            outcome="completed",
            recognized_confidence=0.99,
        )

        other_session = _create_shop_and_session(
            db_session,
            shop_id="shop_other",
            session_id="sess_other",
        )
        other_shop_task = _insert_task_run(
            db_session,
            shop_id="shop_other",
            session_id=other_session.session_id,
            task_type="voice-stock-query",
            status="completed",
            created_at=now - timedelta(minutes=20),
            completed_at=now - timedelta(minutes=15),
        )
        _insert_provider_telemetry(
            db_session,
            shop_id="shop_other",
            task_run_id=other_shop_task,
            created_at=now - timedelta(minutes=15),
            task_type="voice-stock-query",
            capability="asr",
            provider_mode="real-provider",
            provider_label="asr-primary",
            outcome="completed",
            recognized_confidence=0.99,
        )
        db_session.commit()
    finally:
        db_session.close()

    response = client.get(
        "/api/v1/system/pilot-summary?hours=24",
        headers=_auth_headers(client, monkeypatch),
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["time_window"]["hours"] == 24
    assert payload["time_window"]["started_at"] < payload["time_window"]["ended_at"]
    assert payload["task_totals"]["voice-stock-query"]["completed"] == 1
    assert payload["task_totals"]["voice-stock-query"]["failed"] == 1
    assert payload["task_totals"]["photo-stock-in"]["awaiting-confirmation"] == 1
    assert payload["task_totals"]["photo-stock-in"]["completed"] == 1
    assert payload["task_totals"]["photo-stock-in"]["rejected"] == 1
    assert payload["task_totals"]["photo-stock-query"]["failed"] == 1
    assert payload["confirmations"]["created"] == 3
    assert payload["confirmations"]["approved"] == 1
    assert payload["confirmations"]["rejected"] == 1
    assert payload["low_confidence_count"] == 1
    assert payload["fallback_count"] == 1
    assert payload["telemetry_task_count"] == 5
    assert payload["provider_failures"]["asr_low_confidence"] == 1
    assert payload["provider_failures"]["vision_unavailable"] == 1
    assert payload["trial_provider_profile"] == "pilot-v1"


def test_pilot_summary_counts_ocr_fallback_and_low_confidence_from_real_runtime_telemetry(
    client,
    monkeypatch,
) -> None:
    from app.runtime import processor as runtime_processor
    from app.models import OcrDocument

    monkeypatch.setenv("TRIAL_PROVIDER_PROFILE", "pilot-v1")
    monkeypatch.setenv("OCR_PROVIDER", "real-provider")
    monkeypatch.setenv("OCR_PROVIDER_LABEL", "ocr-primary")

    db_session = get_session_factory()()
    try:
        task_run_id = _create_receipt_runtime_task(
            db_session,
            media_id="receipt_summary_demo",
            client_request_id="pilot_summary_receipt_telemetry",
        )
        persisted_document = OcrDocument(
            ocr_document_id="ocr_summary_receipt",
            shop_id="shop_default",
            task_run_id=task_run_id,
            media_id="receipt_summary_demo",
            document_type="purchase-receipt",
            status="completed",
            provider_name="stub-ocr",
            raw_text="receipt text",
            extracted_fields={
                "items": [{"name": "Red Bull 250ml", "quantity": 3, "unit": "can", "price": 41.0}],
                "total_amount": 123.0,
            },
            low_confidence_fields=["items[0].price"],
            created_at=_now(),
            updated_at=_now(),
        )

        class StubCreateResult:
            def __init__(self):
                self.ocr_document = persisted_document
                self.response_status = "processing"
                self.provider_name = "stub-ocr"
                self.used_fallback = True
                self.low_confidence_fields = ["items[0].price"]

        def stub_create_ocr_document(*args, **kwargs):
            return StubCreateResult()

        monkeypatch.setattr(runtime_processor, "create_ocr_document", stub_create_ocr_document)

        result = process_task_run(db_session, task_run_id)
        assert result.status == "awaiting-confirmation"
    finally:
        db_session.close()

    response = client.get(
        "/api/v1/system/pilot-summary?hours=24",
        headers=_auth_headers(client, monkeypatch),
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["task_totals"]["receipt-ocr"]["awaiting-confirmation"] == 1
    assert payload["low_confidence_count"] == 1
    assert payload["fallback_count"] == 1
    assert payload["telemetry_task_count"] == 1
    assert payload["trial_provider_profile"] == "pilot-v1"


def test_pilot_summary_counts_cutover_mode_from_real_open_allowed_runtime_telemetry(
    client,
    monkeypatch,
) -> None:
    from app.runtime import tools as runtime_tools
    from app.services.asr_types import AsrTranscription

    monkeypatch.setenv("APP_RUNTIME_MODE", "trial")
    monkeypatch.setenv("TRIAL_PROVIDER_PROFILE", "pilot-v1")

    class _Gateway:
        def transcribe(self, _media_input):
            return AsrTranscription(text="check stock left for cola", provider="real-asr", confidence=0.97)

    monkeypatch.setattr(runtime_tools, "get_default_asr_gateway", lambda: _Gateway())

    db_session = get_session_factory()()
    try:
        context = ensure_default_context(db_session)
        pilot_control, _ = get_or_create_pilot_control(
            db_session,
            shop_id=context.shop.shop_id,
            trial_provider_profile="pilot-v1",
        )
        pilot_control.cutover_mode = "open"
        pilot_control.approved_calibration_artifact_id = "artifact_20260407"
        pilot_control.last_preflight_status = "ready"
        db_session.commit()

        task_run_id = _create_voice_runtime_task(
            db_session,
            media_id="voice_summary_open_allowed",
            client_request_id="pilot_summary_open_allowed_cutover",
        )
        result = process_task_run(db_session, task_run_id)
        assert result.status == "completed"
    finally:
        db_session.close()

    response = client.get(
        "/api/v1/system/pilot-summary?hours=24",
        headers=_auth_headers(client, monkeypatch),
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["task_totals"]["voice-stock-query"]["completed"] == 1
    assert payload["telemetry_task_count"] == 1
    assert payload["cutover_mode_counts"]["open"] == 1


def test_pilot_summary_distinguishes_cutover_guardrail_outcomes_from_provider_failures(
    client,
    monkeypatch,
) -> None:
    monkeypatch.setenv("TRIAL_PROVIDER_PROFILE", "pilot-v1")

    db_session = get_session_factory()()
    try:
        context = ensure_default_context(db_session)
        now = _now()
        guardrail_block_task = _insert_task_run(
            db_session,
            shop_id=context.shop.shop_id,
            session_id=context.session.session_id,
            task_type="voice-stock-in",
            status="failed",
            created_at=now - timedelta(minutes=40),
            completed_at=now - timedelta(minutes=35),
            error_code="pilot_cutover_closed",
        )
        provider_failure_task = _insert_task_run(
            db_session,
            shop_id=context.shop.shop_id,
            session_id=context.session.session_id,
            task_type="photo-stock-query",
            status="failed",
            created_at=now - timedelta(minutes=30),
            completed_at=now - timedelta(minutes=25),
            error_code="vision_unavailable",
        )
        shadow_task = _insert_task_run(
            db_session,
            shop_id=context.shop.shop_id,
            session_id=context.session.session_id,
            task_type="voice-stock-in",
            status="awaiting-confirmation",
            created_at=now - timedelta(minutes=20),
        )
        degraded_open_task = _insert_task_run(
            db_session,
            shop_id=context.shop.shop_id,
            session_id=context.session.session_id,
            task_type="voice-stock-in",
            status="awaiting-confirmation",
            created_at=now - timedelta(minutes=10),
        )

        _insert_provider_telemetry(
            db_session,
            shop_id=context.shop.shop_id,
            task_run_id=guardrail_block_task,
            created_at=now - timedelta(minutes=35),
            task_type="voice-stock-in",
            capability="guardrail",
            provider_mode="guardrail",
            provider_label="pilot-cutover",
            outcome="failed",
            error_code="pilot_cutover_closed",
            cutover_mode="closed",
            guardrail_status="blocked",
            guardrail_reason="cutover_mode_closed",
            shadow_forced_confirmation=False,
            guardrail_degraded=False,
            guardrail_degraded_reasons=[],
        )
        _insert_provider_telemetry(
            db_session,
            shop_id=context.shop.shop_id,
            task_run_id=provider_failure_task,
            created_at=now - timedelta(minutes=25),
            task_type="photo-stock-query",
            capability="vision",
            provider_mode="real-provider",
            provider_label="vision-primary",
            outcome="failed",
            error_code="vision_unavailable",
            cutover_mode="open",
            guardrail_status="allowed",
            shadow_forced_confirmation=False,
            guardrail_degraded=False,
            guardrail_degraded_reasons=[],
        )
        _insert_provider_telemetry(
            db_session,
            shop_id=context.shop.shop_id,
            task_run_id=shadow_task,
            created_at=now - timedelta(minutes=20),
            task_type="voice-stock-in",
            capability="guardrail",
            provider_mode="guardrail",
            provider_label="pilot-cutover",
            outcome="awaiting-confirmation",
            cutover_mode="shadow",
            guardrail_status="forced-confirmation",
            guardrail_reason="cutover_mode_shadow",
            shadow_forced_confirmation=True,
            guardrail_degraded=False,
            guardrail_degraded_reasons=[],
        )
        _insert_provider_telemetry(
            db_session,
            shop_id=context.shop.shop_id,
            task_run_id=degraded_open_task,
            created_at=now - timedelta(minutes=10),
            task_type="voice-stock-in",
            capability="guardrail",
            provider_mode="guardrail",
            provider_label="pilot-cutover",
            outcome="awaiting-confirmation",
            cutover_mode="open",
            guardrail_status="forced-confirmation",
            guardrail_reason="cutover_alignment_invalid",
            shadow_forced_confirmation=False,
            guardrail_degraded=True,
            guardrail_degraded_reasons=[
                "trial_provider_profile_mismatch",
                "approved_calibration_artifact_missing",
            ],
        )
        db_session.commit()
    finally:
        db_session.close()

    response = client.get(
        "/api/v1/system/pilot-summary?hours=24",
        headers=_auth_headers(client, monkeypatch),
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["provider_failures"]["vision_unavailable"] == 1
    assert "pilot_cutover_closed" not in payload["provider_failures"]
    assert payload["cutover_mode_counts"]["closed"] == 1
    assert payload["cutover_mode_counts"]["shadow"] == 1
    assert payload["cutover_mode_counts"]["open"] == 2
    assert payload["guardrail_blocks"]["cutover_mode_closed"] == 1
    assert payload["shadow_forced_confirmation_count"] == 1
    assert payload["guardrail_degraded_reasons"]["trial_provider_profile_mismatch"] == 1
    assert payload["guardrail_degraded_reasons"]["approved_calibration_artifact_missing"] == 1


def test_pilot_summary_ignores_telemetry_from_other_trial_provider_profiles(
    client,
    monkeypatch,
) -> None:
    monkeypatch.setenv("TRIAL_PROVIDER_PROFILE", "pilot-v1")

    db_session = get_session_factory()()
    try:
        context = ensure_default_context(db_session)
        now = _now()
        task_run_id = _insert_task_run(
            db_session,
            shop_id=context.shop.shop_id,
            session_id=context.session.session_id,
            task_type="voice-stock-query",
            status="failed",
            created_at=now - timedelta(minutes=30),
            completed_at=now - timedelta(minutes=25),
            error_code="asr_low_confidence",
        )
        _insert_provider_telemetry(
            db_session,
            shop_id=context.shop.shop_id,
            task_run_id=task_run_id,
            created_at=now - timedelta(minutes=25),
            task_type="voice-stock-query",
            capability="asr",
            provider_mode="real-provider",
            provider_label="asr-primary",
            outcome="failed",
            used_fallback=True,
            low_confidence=True,
            error_code="asr_low_confidence",
            trial_provider_profile="pilot-v2",
        )
        db_session.commit()
    finally:
        db_session.close()

    response = client.get(
        "/api/v1/system/pilot-summary?hours=24",
        headers=_auth_headers(client, monkeypatch),
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["low_confidence_count"] == 0
    assert payload["fallback_count"] == 0
    assert payload["telemetry_task_count"] == 0
    assert payload["provider_failures"] == {}
    assert payload["trial_provider_profile"] == "pilot-v1"
