from datetime import datetime

import pytest

from app.services.v2_outbox_due_scopes import V2OutboxDueScopesDrainResult
from app.workers import v2_outbox_due_tasks
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


def test_v2_outbox_due_task_wrapper_invokes_drain_and_commits(monkeypatch) -> None:
    fake_session = _FakeSession()

    def fake_get_session_factory():
        return lambda: fake_session

    def fake_run_due_scope_drain(
        db_session,
        *,
        scope_limit: int,
        batch_limit_per_scope: int,
        max_batches_per_scope: int,
        retry_after_seconds: int | None,
    ) -> V2OutboxDueScopesDrainResult:
        assert db_session is fake_session
        assert scope_limit == 20
        assert batch_limit_per_scope == 5
        assert max_batches_per_scope == 2
        assert retry_after_seconds == 120
        return V2OutboxDueScopesDrainResult(
            scope_limit=scope_limit,
            batch_limit_per_scope=batch_limit_per_scope,
            max_batches_per_scope=max_batches_per_scope,
            scope_count=3,
            claimed_count=5,
            completed_count=4,
            retried_count=1,
            failed_count=0,
            drained_at=datetime.fromisoformat("2026-04-19T12:00:00"),
        )

    monkeypatch.setattr(v2_outbox_due_tasks, "get_session_factory", fake_get_session_factory)
    monkeypatch.setattr(v2_outbox_due_tasks, "run_due_scope_drain", fake_run_due_scope_drain)

    result = v2_outbox_due_tasks.drain_due_v2_outbox_scopes(
        scope_limit=20,
        batch_limit_per_scope=5,
        max_batches_per_scope=2,
        retry_after_seconds=120,
    )

    assert result == {
        "scope_limit": 20,
        "batch_limit_per_scope": 5,
        "max_batches_per_scope": 2,
        "scope_count": 3,
        "claimed_count": 5,
        "completed_count": 4,
        "retried_count": 1,
        "failed_count": 0,
        "drained_at": "2026-04-19T12:00:00",
    }
    assert fake_session.committed is True
    assert fake_session.rolled_back is False
    assert fake_session.closed is True


def test_v2_outbox_due_task_wrapper_rolls_back_on_failure(monkeypatch) -> None:
    fake_session = _FakeSession()

    def fake_get_session_factory():
        return lambda: fake_session

    def raise_boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(v2_outbox_due_tasks, "get_session_factory", fake_get_session_factory)
    monkeypatch.setattr(v2_outbox_due_tasks, "run_due_scope_drain", raise_boom)

    with pytest.raises(RuntimeError, match="boom"):
        v2_outbox_due_tasks.drain_due_v2_outbox_scopes()

    assert fake_session.committed is False
    assert fake_session.rolled_back is True
    assert fake_session.closed is True


def test_v2_outbox_due_task_is_registered_on_explicit_celery_app() -> None:
    assert v2_outbox_due_tasks.celery_app is celery_app
    assert v2_outbox_due_tasks.drain_due_v2_outbox_scopes.app is celery_app
    assert (
        v2_outbox_due_tasks.drain_due_v2_outbox_scopes.name
        == "app.workers.v2_outbox_due_tasks.drain_due_v2_outbox_scopes"
    )
