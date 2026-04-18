from datetime import datetime

import pytest

from app.services.v2_outbox_worker import V2OutboxDrainResult
from app.workers import v2_outbox_tasks
from app.workers.celery_app import celery_app


class _FakeSession:
    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True

    def close(self) -> None:
        self.closed = True


def test_v2_outbox_task_wrapper_invokes_drain_and_commits(monkeypatch) -> None:
    fake_session = _FakeSession()

    def fake_get_session_factory():
        return lambda: fake_session

    def fake_run_outbox_drain(
        db_session,
        *,
        tenant_id: str,
        shop_id: str,
        batch_limit: int,
        max_batches: int,
        retry_after_seconds: int | None,
    ) -> V2OutboxDrainResult:
        assert db_session is fake_session
        assert tenant_id == "tenant_a"
        assert shop_id == "shop_a1"
        assert batch_limit == 20
        assert max_batches == 3
        assert retry_after_seconds == 120
        return V2OutboxDrainResult(
            tenant_id=tenant_id,
            shop_id=shop_id,
            batch_limit=batch_limit,
            max_batches=max_batches,
            batches_run=2,
            claimed_count=5,
            completed_count=4,
            retried_count=1,
            failed_count=0,
            drained_at=datetime.fromisoformat("2026-04-19T10:00:00"),
        )

    monkeypatch.setattr(v2_outbox_tasks, "get_session_factory", fake_get_session_factory)
    monkeypatch.setattr(v2_outbox_tasks, "run_outbox_drain", fake_run_outbox_drain)

    result = v2_outbox_tasks.drain_v2_outbox(
        "tenant_a",
        "shop_a1",
        batch_limit=20,
        max_batches=3,
        retry_after_seconds=120,
    )

    assert result == {
        "tenant_id": "tenant_a",
        "shop_id": "shop_a1",
        "batch_limit": 20,
        "max_batches": 3,
        "batches_run": 2,
        "claimed_count": 5,
        "completed_count": 4,
        "retried_count": 1,
        "failed_count": 0,
        "drained_at": "2026-04-19T10:00:00",
    }
    assert fake_session.committed is True
    assert fake_session.rolled_back is False
    assert fake_session.closed is True


def test_v2_outbox_task_wrapper_rolls_back_on_failure(monkeypatch) -> None:
    fake_session = _FakeSession()

    def fake_get_session_factory():
        return lambda: fake_session

    def raise_boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(v2_outbox_tasks, "get_session_factory", fake_get_session_factory)
    monkeypatch.setattr(v2_outbox_tasks, "run_outbox_drain", raise_boom)

    with pytest.raises(RuntimeError, match="boom"):
        v2_outbox_tasks.drain_v2_outbox("tenant_a", "shop_a1")

    assert fake_session.committed is False
    assert fake_session.rolled_back is True
    assert fake_session.closed is True


def test_v2_outbox_task_is_registered_on_explicit_celery_app() -> None:
    assert v2_outbox_tasks.celery_app is celery_app
    assert v2_outbox_tasks.drain_v2_outbox.app is celery_app
    assert v2_outbox_tasks.drain_v2_outbox.name == "app.workers.v2_outbox_tasks.drain_v2_outbox"
