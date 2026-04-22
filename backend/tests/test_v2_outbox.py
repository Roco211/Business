from datetime import datetime, timezone
UTC = timezone.utc
import importlib

import pytest
from sqlalchemy import select


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=None)


def _utc_now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _load_v2_outbox_service():
    try:
        return importlib.import_module("app.services.v2_outbox")
    except ModuleNotFoundError as exc:  # pragma: no cover - red stage only
        pytest.fail(f"app.services.v2_outbox is not implemented yet: {exc}")


def _seed_v2_outbox_scope(db_session) -> None:
    from app.models import V2Account, V2Shop, V2Tenant

    now = _utc_now_naive()
    db_session.add(
        V2Account(
            account_id="acct_001",
            email="owner@example.com",
            display_name="Owner",
            password_hash="hash",
            password_salt="salt",
            status="active",
            created_at=now,
            updated_at=now,
        )
    )
    db_session.add_all(
        [
            V2Tenant(
                tenant_id="tenant_a",
                name="Tenant A",
                slug="tenant-a",
                status="active",
                plan_code="trial",
                owner_account_id="acct_001",
                created_at=now,
                updated_at=now,
            ),
            V2Tenant(
                tenant_id="tenant_b",
                name="Tenant B",
                slug="tenant-b",
                status="active",
                plan_code="trial",
                owner_account_id="acct_001",
                created_at=now,
                updated_at=now,
            ),
            V2Shop(
                shop_id="shop_a1",
                tenant_id="tenant_a",
                code="a-1",
                name="Shop A1",
                locale="zh-CN",
                timezone="Asia/Shanghai",
                status="active",
                created_at=now,
                updated_at=now,
            ),
            V2Shop(
                shop_id="shop_a2",
                tenant_id="tenant_a",
                code="a-2",
                name="Shop A2",
                locale="zh-CN",
                timezone="Asia/Shanghai",
                status="active",
                created_at=now,
                updated_at=now,
            ),
            V2Shop(
                shop_id="shop_b1",
                tenant_id="tenant_b",
                code="b-1",
                name="Shop B1",
                locale="zh-CN",
                timezone="Asia/Shanghai",
                status="active",
                created_at=now,
                updated_at=now,
            ),
        ]
    )
    db_session.commit()


def _seed_v2_outbox_event(
    db_session,
    *,
    outbox_event_id: str,
    tenant_id: str,
    shop_id: str,
    status: str,
    available_at: datetime,
    created_at: datetime,
    attempt_count: int = 0,
) -> None:
    from app.models import V2OutboxEvent

    db_session.add(
        V2OutboxEvent(
            outbox_event_id=outbox_event_id,
            tenant_id=tenant_id,
            shop_id=shop_id,
            aggregate_type="task_run",
            aggregate_id=f"task_{outbox_event_id}",
            event_type="inventory.stock_in.committed",
            payload_json={"source": outbox_event_id},
            status=status,
            attempt_count=attempt_count,
            available_at=available_at,
            created_at=created_at,
        )
    )


def test_claim_v2_outbox_events_claims_pending_events_in_stable_order(db_session) -> None:
    from app.models import V2OutboxEvent

    outbox_service = _load_v2_outbox_service()
    _seed_v2_outbox_scope(db_session)
    _seed_v2_outbox_event(
        db_session,
        outbox_event_id="evt_oldest",
        tenant_id="tenant_a",
        shop_id="shop_a1",
        status="pending",
        available_at=_dt("2026-04-18T10:00:00"),
        created_at=_dt("2026-04-18T10:00:00"),
    )
    _seed_v2_outbox_event(
        db_session,
        outbox_event_id="evt_newer",
        tenant_id="tenant_a",
        shop_id="shop_a1",
        status="pending",
        available_at=_dt("2026-04-18T10:01:00"),
        created_at=_dt("2026-04-18T10:01:00"),
    )
    _seed_v2_outbox_event(
        db_session,
        outbox_event_id="evt_future",
        tenant_id="tenant_a",
        shop_id="shop_a1",
        status="pending",
        available_at=_dt("2026-04-18T11:00:00"),
        created_at=_dt("2026-04-18T10:02:00"),
    )
    db_session.commit()

    claimed = outbox_service.claim_v2_outbox_events(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        limit=2,
        now=_dt("2026-04-18T10:05:00"),
    )

    db_session.expire_all()
    rows = db_session.scalars(
        select(V2OutboxEvent).order_by(V2OutboxEvent.created_at.asc(), V2OutboxEvent.outbox_event_id.asc())
    ).all()

    assert [event.outbox_event_id for event in claimed] == ["evt_oldest", "evt_newer"]
    assert [event.status for event in claimed] == ["processing", "processing"]
    assert [event.attempt_count for event in claimed] == [1, 1]
    assert [(event.outbox_event_id, event.status, event.attempt_count) for event in rows] == [
        ("evt_oldest", "processing", 1),
        ("evt_newer", "processing", 1),
        ("evt_future", "pending", 0),
    ]


def test_claim_v2_outbox_events_skips_other_scope_and_non_pending_rows(db_session) -> None:
    outbox_service = _load_v2_outbox_service()
    _seed_v2_outbox_scope(db_session)
    _seed_v2_outbox_event(
        db_session,
        outbox_event_id="evt_scope_match",
        tenant_id="tenant_a",
        shop_id="shop_a1",
        status="pending",
        available_at=_dt("2026-04-18T10:00:00"),
        created_at=_dt("2026-04-18T10:00:00"),
    )
    _seed_v2_outbox_event(
        db_session,
        outbox_event_id="evt_processing",
        tenant_id="tenant_a",
        shop_id="shop_a1",
        status="processing",
        available_at=_dt("2026-04-18T09:00:00"),
        created_at=_dt("2026-04-18T09:00:00"),
        attempt_count=2,
    )
    _seed_v2_outbox_event(
        db_session,
        outbox_event_id="evt_other_shop",
        tenant_id="tenant_a",
        shop_id="shop_a2",
        status="pending",
        available_at=_dt("2026-04-18T08:00:00"),
        created_at=_dt("2026-04-18T08:00:00"),
    )
    _seed_v2_outbox_event(
        db_session,
        outbox_event_id="evt_other_tenant",
        tenant_id="tenant_b",
        shop_id="shop_b1",
        status="pending",
        available_at=_dt("2026-04-18T07:00:00"),
        created_at=_dt("2026-04-18T07:00:00"),
    )
    db_session.commit()

    claimed = outbox_service.claim_v2_outbox_events(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        limit=10,
        now=_dt("2026-04-18T10:05:00"),
    )

    assert [event.outbox_event_id for event in claimed] == ["evt_scope_match"]
    assert claimed[0].status == "processing"
    assert claimed[0].attempt_count == 1


def test_complete_v2_outbox_event_marks_processing_event_completed(db_session) -> None:
    from app.models import V2OutboxEvent

    outbox_service = _load_v2_outbox_service()
    _seed_v2_outbox_scope(db_session)
    _seed_v2_outbox_event(
        db_session,
        outbox_event_id="evt_processing",
        tenant_id="tenant_a",
        shop_id="shop_a1",
        status="processing",
        available_at=_dt("2026-04-18T10:00:00"),
        created_at=_dt("2026-04-18T10:00:00"),
        attempt_count=1,
    )
    db_session.commit()

    completed = outbox_service.complete_v2_outbox_event(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        outbox_event_id="evt_processing",
        now=_dt("2026-04-18T10:10:00"),
    )

    db_session.expire_all()
    persisted = db_session.scalar(
        select(V2OutboxEvent).where(V2OutboxEvent.outbox_event_id == "evt_processing")
    )
    claimed_again = outbox_service.claim_v2_outbox_events(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        limit=10,
        now=_dt("2026-04-18T10:11:00"),
    )

    assert completed.status == "completed"
    assert completed.processed_at == _dt("2026-04-18T10:10:00")
    assert completed.updated_at == _dt("2026-04-18T10:10:00")
    assert completed.last_error_code is None
    assert completed.last_error_message is None
    assert persisted is not None
    assert persisted.status == "completed"
    assert claimed_again == []


def test_fail_v2_outbox_event_without_retry_marks_terminal_failed(db_session) -> None:
    outbox_service = _load_v2_outbox_service()
    _seed_v2_outbox_scope(db_session)
    _seed_v2_outbox_event(
        db_session,
        outbox_event_id="evt_processing",
        tenant_id="tenant_a",
        shop_id="shop_a1",
        status="processing",
        available_at=_dt("2026-04-18T10:00:00"),
        created_at=_dt("2026-04-18T10:00:00"),
        attempt_count=2,
    )
    db_session.commit()

    failed = outbox_service.fail_v2_outbox_event(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        outbox_event_id="evt_processing",
        error_code="projection_failed",
        error_message="Projection worker failed",
        now=_dt("2026-04-18T10:10:00"),
    )

    assert failed.status == "failed"
    assert failed.attempt_count == 2
    assert failed.available_at == _dt("2026-04-18T10:10:00")
    assert failed.processed_at == _dt("2026-04-18T10:10:00")
    assert failed.updated_at == _dt("2026-04-18T10:10:00")
    assert failed.last_error_code == "projection_failed"
    assert failed.last_error_message == "Projection worker failed"


def test_fail_v2_outbox_event_with_retry_returns_to_pending_after_delay(db_session) -> None:
    outbox_service = _load_v2_outbox_service()
    _seed_v2_outbox_scope(db_session)
    _seed_v2_outbox_event(
        db_session,
        outbox_event_id="evt_processing",
        tenant_id="tenant_a",
        shop_id="shop_a1",
        status="processing",
        available_at=_dt("2026-04-18T10:00:00"),
        created_at=_dt("2026-04-18T10:00:00"),
        attempt_count=2,
    )
    db_session.commit()

    retried = outbox_service.fail_v2_outbox_event(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        outbox_event_id="evt_processing",
        error_code="temporary_projection_error",
        error_message="Temporary projection worker error",
        retry_after_seconds=300,
        now=_dt("2026-04-18T10:10:00"),
    )

    assert retried.status == "pending"
    assert retried.attempt_count == 2
    assert retried.available_at == _dt("2026-04-18T10:15:00")
    assert retried.processed_at is None
    assert retried.updated_at == _dt("2026-04-18T10:10:00")
    assert retried.last_error_code == "temporary_projection_error"
    assert retried.last_error_message == "Temporary projection worker error"

    too_early_claim = outbox_service.claim_v2_outbox_events(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        limit=10,
        now=_dt("2026-04-18T10:14:59"),
    )
    retry_claim = outbox_service.claim_v2_outbox_events(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        limit=10,
        now=_dt("2026-04-18T10:15:00"),
    )

    assert too_early_claim == []
    assert [event.outbox_event_id for event in retry_claim] == ["evt_processing"]
    assert retry_claim[0].status == "processing"
    assert retry_claim[0].attempt_count == 3
