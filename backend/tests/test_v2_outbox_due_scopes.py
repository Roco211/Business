from datetime import datetime, timezone
UTC = timezone.utc
import importlib

import pytest

from app.services.v2_outbox_worker import V2OutboxDrainResult


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=None)


def _utc_now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _load_v2_outbox_due_scopes_service():
    try:
        return importlib.import_module("app.services.v2_outbox_due_scopes")
    except ModuleNotFoundError as exc:  # pragma: no cover - red stage only
        pytest.fail(f"app.services.v2_outbox_due_scopes is not implemented yet: {exc}")


def _seed_outbox_scope(db_session, *, tenant_id: str, shop_id: str) -> None:
    from app.models import V2Account, V2Shop, V2Tenant

    now = _utc_now_naive()
    account_id = f"acct_{tenant_id}"[:40]
    db_session.add(
        V2Account(
            account_id=account_id,
            email=f"{tenant_id}@example.com",
            display_name=tenant_id,
            password_hash="hash",
            password_salt="salt",
            status="active",
            created_at=now,
            updated_at=now,
        )
    )
    db_session.add(
        V2Tenant(
            tenant_id=tenant_id,
            name=tenant_id,
            slug=tenant_id,
            status="active",
            plan_code="trial",
            owner_account_id=account_id,
            created_at=now,
            updated_at=now,
        )
    )
    db_session.add(
        V2Shop(
            shop_id=shop_id,
            tenant_id=tenant_id,
            code=shop_id,
            name=shop_id,
            locale="zh-CN",
            timezone="Asia/Shanghai",
            status="active",
            created_at=now,
            updated_at=now,
        )
    )


def _seed_outbox_event(
    db_session,
    *,
    tenant_id: str,
    shop_id: str,
    outbox_event_id: str,
    status: str,
    available_at: datetime,
) -> None:
    from app.models import V2OutboxEvent

    db_session.add(
        V2OutboxEvent(
            outbox_event_id=outbox_event_id,
            tenant_id=tenant_id,
            shop_id=shop_id,
            aggregate_type="task_run",
            aggregate_id=f"task_{outbox_event_id}"[:40],
            event_type="inventory.stock_in.committed",
            payload_json={"inventory_item_id": "vitem_demo"},
            status=status,
            attempt_count=0,
            last_error_code=None,
            last_error_message=None,
            available_at=available_at,
            processed_at=None,
            created_at=available_at,
            updated_at=available_at,
        )
    )


def test_drain_due_v2_outbox_scopes_processes_due_scopes_in_oldest_first_order(
    db_session, monkeypatch
) -> None:
    due_service = _load_v2_outbox_due_scopes_service()
    _seed_outbox_scope(db_session, tenant_id="tenant_a", shop_id="shop_a1")
    _seed_outbox_scope(db_session, tenant_id="tenant_b", shop_id="shop_b1")
    _seed_outbox_event(
        db_session,
        tenant_id="tenant_b",
        shop_id="shop_b1",
        outbox_event_id="evt_b_001",
        status="pending",
        available_at=_dt("2026-04-19T09:40:00"),
    )
    _seed_outbox_event(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        outbox_event_id="evt_a_001",
        status="pending",
        available_at=_dt("2026-04-19T09:50:00"),
    )
    db_session.commit()

    called_scopes: list[tuple[str, str]] = []

    def _fake_drain(
        _db_session,
        *,
        tenant_id: str,
        shop_id: str,
        batch_limit: int,
        max_batches: int,
        retry_after_seconds: int | None,
        now: datetime,
    ) -> V2OutboxDrainResult:
        called_scopes.append((tenant_id, shop_id))
        claimed_count = 2 if tenant_id == "tenant_b" else 3
        return V2OutboxDrainResult(
            tenant_id=tenant_id,
            shop_id=shop_id,
            batch_limit=batch_limit,
            max_batches=max_batches,
            batches_run=1,
            claimed_count=claimed_count,
            completed_count=claimed_count,
            retried_count=0,
            failed_count=0,
            drained_at=now,
        )

    monkeypatch.setattr(due_service, "drain_v2_outbox_events", _fake_drain)

    result = due_service.drain_due_v2_outbox_scopes(
        db_session,
        scope_limit=10,
        batch_limit_per_scope=20,
        max_batches_per_scope=3,
        now=_dt("2026-04-19T10:00:00"),
    )

    assert called_scopes == [("tenant_b", "shop_b1"), ("tenant_a", "shop_a1")]
    assert result.scope_limit == 10
    assert result.batch_limit_per_scope == 20
    assert result.max_batches_per_scope == 3
    assert result.scope_count == 2
    assert result.claimed_count == 5
    assert result.completed_count == 5
    assert result.retried_count == 0
    assert result.failed_count == 0
    assert result.drained_at == _dt("2026-04-19T10:00:00")


def test_drain_due_v2_outbox_scopes_respects_scope_limit_and_due_filter(db_session, monkeypatch) -> None:
    due_service = _load_v2_outbox_due_scopes_service()
    _seed_outbox_scope(db_session, tenant_id="tenant_a", shop_id="shop_a1")
    _seed_outbox_scope(db_session, tenant_id="tenant_b", shop_id="shop_b1")
    _seed_outbox_scope(db_session, tenant_id="tenant_c", shop_id="shop_c1")
    _seed_outbox_scope(db_session, tenant_id="tenant_d", shop_id="shop_d1")
    _seed_outbox_event(
        db_session,
        tenant_id="tenant_b",
        shop_id="shop_b1",
        outbox_event_id="evt_b_due",
        status="pending",
        available_at=_dt("2026-04-19T09:40:00"),
    )
    _seed_outbox_event(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        outbox_event_id="evt_a_due",
        status="pending",
        available_at=_dt("2026-04-19T09:50:00"),
    )
    _seed_outbox_event(
        db_session,
        tenant_id="tenant_c",
        shop_id="shop_c1",
        outbox_event_id="evt_c_future",
        status="pending",
        available_at=_dt("2026-04-19T10:30:00"),
    )
    _seed_outbox_event(
        db_session,
        tenant_id="tenant_d",
        shop_id="shop_d1",
        outbox_event_id="evt_d_completed",
        status="completed",
        available_at=_dt("2026-04-19T09:30:00"),
    )
    db_session.commit()

    called_scopes: list[tuple[str, str]] = []

    def _fake_drain(
        _db_session,
        *,
        tenant_id: str,
        shop_id: str,
        batch_limit: int,
        max_batches: int,
        retry_after_seconds: int | None,
        now: datetime,
    ) -> V2OutboxDrainResult:
        called_scopes.append((tenant_id, shop_id))
        return V2OutboxDrainResult(
            tenant_id=tenant_id,
            shop_id=shop_id,
            batch_limit=batch_limit,
            max_batches=max_batches,
            batches_run=1,
            claimed_count=1,
            completed_count=1,
            retried_count=0,
            failed_count=0,
            drained_at=now,
        )

    monkeypatch.setattr(due_service, "drain_v2_outbox_events", _fake_drain)

    result = due_service.drain_due_v2_outbox_scopes(
        db_session,
        scope_limit=2,
        batch_limit_per_scope=5,
        max_batches_per_scope=2,
        now=_dt("2026-04-19T10:00:00"),
    )

    assert called_scopes == [("tenant_b", "shop_b1"), ("tenant_a", "shop_a1")]
    assert result.scope_count == 2
    assert result.claimed_count == 2
    assert result.completed_count == 2


def test_drain_due_v2_outbox_scopes_rejects_invalid_limits(db_session) -> None:
    due_service = _load_v2_outbox_due_scopes_service()

    with pytest.raises(ValueError, match="scope_limit must be > 0"):
        due_service.drain_due_v2_outbox_scopes(db_session, scope_limit=0)

    with pytest.raises(ValueError, match="batch_limit_per_scope must be > 0"):
        due_service.drain_due_v2_outbox_scopes(
            db_session,
            scope_limit=1,
            batch_limit_per_scope=0,
        )

    with pytest.raises(ValueError, match="max_batches_per_scope must be > 0"):
        due_service.drain_due_v2_outbox_scopes(
            db_session,
            scope_limit=1,
            batch_limit_per_scope=1,
            max_batches_per_scope=0,
        )
