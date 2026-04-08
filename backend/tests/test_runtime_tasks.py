import pytest

from app.runtime.processor import RuntimeProcessResult
from app.workers.celery_app import celery_app
from app.workers import runtime_tasks


class _FakeSession:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


def test_runtime_task_wrapper_invokes_processor_and_returns_payload(monkeypatch) -> None:
    fake_session = _FakeSession()

    def fake_get_session_factory():
        return lambda: fake_session

    def fake_process_task_run(db_session, task_run_id: str) -> RuntimeProcessResult:
        assert db_session is fake_session
        assert task_run_id == "task_123"
        return RuntimeProcessResult(
            status="completed",
            task_run_id=task_run_id,
            task_type="voice-stock-query",
            error_code=None,
        )

    monkeypatch.setattr(runtime_tasks, "get_session_factory", fake_get_session_factory)
    monkeypatch.setattr(runtime_tasks, "run_runtime_processor", fake_process_task_run)

    result = runtime_tasks.process_task_run("task_123")

    assert result == {
        "status": "completed",
        "task_run_id": "task_123",
        "task_type": "voice-stock-query",
        "error_code": None,
    }
    assert fake_session.closed is True


def test_runtime_task_wrapper_serializes_awaiting_confirmation_status(monkeypatch) -> None:
    fake_session = _FakeSession()

    def fake_get_session_factory():
        return lambda: fake_session

    def fake_process_task_run(db_session, task_run_id: str) -> RuntimeProcessResult:
        assert db_session is fake_session
        assert task_run_id == "task_123"
        return RuntimeProcessResult(
            status="awaiting-confirmation",
            task_run_id=task_run_id,
            task_type="voice-stock-in",
            error_code=None,
        )

    monkeypatch.setattr(runtime_tasks, "get_session_factory", fake_get_session_factory)
    monkeypatch.setattr(runtime_tasks, "run_runtime_processor", fake_process_task_run)

    result = runtime_tasks.process_task_run("task_123")

    assert result == {
        "status": "awaiting-confirmation",
        "task_run_id": "task_123",
        "task_type": "voice-stock-in",
        "error_code": None,
    }
    assert fake_session.closed is True


def test_runtime_task_wrapper_closes_session_when_processor_raises(monkeypatch) -> None:
    fake_session = _FakeSession()

    def fake_get_session_factory():
        return lambda: fake_session

    def raise_processing_error(_db_session, _task_run_id: str) -> RuntimeProcessResult:
        raise RuntimeError("boom")

    monkeypatch.setattr(runtime_tasks, "get_session_factory", fake_get_session_factory)
    monkeypatch.setattr(runtime_tasks, "run_runtime_processor", raise_processing_error)

    with pytest.raises(RuntimeError, match="boom"):
        runtime_tasks.process_task_run("task_123")

    assert fake_session.closed is True


def test_runtime_task_is_registered_on_explicit_celery_app() -> None:
    assert runtime_tasks.celery_app is celery_app
    assert runtime_tasks.process_task_run.app is celery_app
    assert runtime_tasks.process_task_run.name == "app.workers.runtime_tasks.process_task_run"
