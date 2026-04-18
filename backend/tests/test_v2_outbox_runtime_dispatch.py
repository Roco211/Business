import importlib


def _load_dispatch_service():
    return importlib.import_module("app.services.v2_outbox_runtime_dispatch")


def test_enqueue_v2_outbox_drain_dispatches_worker_task(monkeypatch) -> None:
    dispatch_service = _load_dispatch_service()
    captured: dict[str, object] = {}

    class _FakeTask:
        def apply_async(self, *, args, kwargs, retry):
            captured["args"] = args
            captured["kwargs"] = kwargs
            captured["retry"] = retry

    monkeypatch.setattr(dispatch_service, "drain_v2_outbox", _FakeTask())

    class _FakeThread:
        def __init__(self, *, target, kwargs, daemon, name) -> None:
            captured["thread_daemon"] = daemon
            captured["thread_name"] = name
            self._target = target
            self._kwargs = kwargs

        def start(self) -> None:
            captured["thread_started"] = True
            self._target(**self._kwargs)

    monkeypatch.setattr(dispatch_service.threading, "Thread", _FakeThread)

    result = dispatch_service.enqueue_v2_outbox_drain(
        tenant_id="tenant_a",
        shop_id="shop_a1",
        batch_limit=20,
        max_batches=3,
        retry_after_seconds=120,
    )

    assert result is True
    assert captured == {
        "args": ("tenant_a", "shop_a1"),
        "kwargs": {
            "batch_limit": 20,
            "max_batches": 3,
            "retry_after_seconds": 120,
        },
        "retry": False,
        "thread_daemon": True,
        "thread_name": "v2-outbox-enqueue",
        "thread_started": True,
    }


def test_enqueue_v2_outbox_drain_swallows_background_publish_errors(monkeypatch) -> None:
    dispatch_service = _load_dispatch_service()

    class _FakeTask:
        def apply_async(self, *args, **kwargs):
            raise RuntimeError("queue unavailable")

    monkeypatch.setattr(dispatch_service, "drain_v2_outbox", _FakeTask())

    class _FakeThread:
        def __init__(self, *, target, kwargs, daemon, name) -> None:
            self._target = target
            self._kwargs = kwargs

        def start(self) -> None:
            self._target(**self._kwargs)

    monkeypatch.setattr(dispatch_service.threading, "Thread", _FakeThread)

    assert dispatch_service.enqueue_v2_outbox_drain(
        tenant_id="tenant_a",
        shop_id="shop_a1",
    ) is True


def test_enqueue_v2_outbox_drain_returns_false_when_enqueue_thread_fails(monkeypatch) -> None:
    dispatch_service = _load_dispatch_service()

    class _BrokenThread:
        def __init__(self, *, target, kwargs, daemon, name) -> None:
            self._target = target
            self._kwargs = kwargs

        def start(self) -> None:
            raise RuntimeError("thread start failed")

    monkeypatch.setattr(dispatch_service.threading, "Thread", _BrokenThread)

    assert dispatch_service.enqueue_v2_outbox_drain(
        tenant_id="tenant_a",
        shop_id="shop_a1",
    ) is False
