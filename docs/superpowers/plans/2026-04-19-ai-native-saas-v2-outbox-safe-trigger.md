# AI 原生 SaaS V2 Outbox 安全触发实现计划
> **给智能执行代理（agentic workers）：** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务逐项实现本计划。步骤使用 checkbox（`- [ ]`）语法跟踪。

**Goal:** 为 V2 inventory commit 的 outbox 增加“提交后安全触发”的 worker enqueue 层，让业务事务提交成功后能够立即 best-effort 唤起 outbox worker。

**Architecture:** 当前 V2 已具备 outbox 写入、单次 dispatch、drain 和 Celery worker task，但还缺少把“业务提交完成”和“后台消费启动”安全串起来的触发层。本切片新增一个轻量 service `v2_outbox_runtime_dispatch.py`，主线程只负责启动一个守护线程（daemon thread），由后台线程调用 `app.workers.v2_outbox_tasks.drain_v2_outbox.apply_async(...)`；`approve_v2_confirmation(...)` 仅在 inventory stock-in / stock-out 分支完成 `db_session.commit()` 之后调用该 helper。后台 publish 使用 `retry=False`，避免 broker 不可用时阻塞请求线程；helper 只有在线程启动失败时才返回 `False`。

**Tech Stack:** Python、Celery、SQLAlchemy、pytest

---

## 文件结构

- 创建 `backend/app/services/v2_outbox_runtime_dispatch.py`：封装 V2 outbox worker 的 best-effort enqueue。
- 创建 `backend/tests/test_v2_outbox_runtime_dispatch.py`：覆盖 enqueue 成功与失败。
- 修改 `backend/app/services/v2_conversation.py`：在 inventory confirmation commit 成功后触发 enqueue。
- 修改 `backend/tests/test_v2_clarification_confirmation.py`：验证触发发生在 commit 之后，且非 inventory approval 不会触发。

### Task 1: 固定安全触发 helper 行为

**Files:**
- Create: `backend/tests/test_v2_outbox_runtime_dispatch.py`
- Create: `backend/app/services/v2_outbox_runtime_dispatch.py`

- [x] **Step 1: 先写失败测试，确认 helper 会启动守护线程，并由后台 publish 把参数透传给 Celery task**

测试要点：

```python
def test_enqueue_v2_outbox_drain_dispatches_worker_task(monkeypatch) -> None:
    captured = {}

    class _FakeTask:
        def apply_async(self, *, args, kwargs, retry):
            captured["args"] = args
            captured["kwargs"] = kwargs
            captured["retry"] = retry

    class _FakeThread:
        def __init__(self, *, target, kwargs, daemon, name) -> None:
            captured["thread_daemon"] = daemon
            captured["thread_name"] = name
            self._target = target
            self._kwargs = kwargs

        def start(self) -> None:
            captured["thread_started"] = True
            self._target(**self._kwargs)

    monkeypatch.setattr(dispatch_service, "drain_v2_outbox", _FakeTask())
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
```

- [x] **Step 2: 再写失败测试，确认后台 publish 报错时 helper 仍然返回 `True`，不反向影响请求线程**

测试要点：

```python
def test_enqueue_v2_outbox_drain_swallows_background_publish_errors(monkeypatch) -> None:
    class _FakeTask:
        def apply_async(self, *args, **kwargs):
            raise RuntimeError("queue unavailable")

    monkeypatch.setattr(dispatch_service, "drain_v2_outbox", _FakeTask())
    monkeypatch.setattr(dispatch_service.threading, "Thread", _FakeThread)

    assert dispatch_service.enqueue_v2_outbox_drain(
        tenant_id="tenant_a",
        shop_id="shop_a1",
    ) is True
```

- [x] **Step 3: 再写失败测试，确认线程启动失败时 helper 返回 `False`**

测试要点：

```python
def test_enqueue_v2_outbox_drain_returns_false_when_enqueue_thread_fails(monkeypatch) -> None:
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
```

- [x] **Step 4: 运行 helper 测试，确认当前模块缺失而失败**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_outbox_runtime_dispatch.py -q
```

- [x] **Step 5: 实现最小 enqueue helper**

`backend/app/services/v2_outbox_runtime_dispatch.py`

```python
import logging
import threading

from app.workers.v2_outbox_tasks import drain_v2_outbox

logger = logging.getLogger(__name__)


def _publish_v2_outbox_drain(
    *,
    tenant_id: str,
    shop_id: str,
    batch_limit: int = 50,
    max_batches: int = 10,
    retry_after_seconds: int | None = 60,
) -> None:
    try:
        drain_v2_outbox.apply_async(
            args=(tenant_id, shop_id),
            kwargs={
                "batch_limit": batch_limit,
                "max_batches": max_batches,
                "retry_after_seconds": retry_after_seconds,
            },
            retry=False,
        )
    except Exception as exc:
        logger.warning("Failed to enqueue V2 outbox drain for %s/%s: %s", tenant_id, shop_id, exc)


def enqueue_v2_outbox_drain(...) -> bool:
    try:
        publish_thread = threading.Thread(
            target=_publish_v2_outbox_drain,
            kwargs={...},
            daemon=True,
            name="v2-outbox-enqueue",
        )
        publish_thread.start()
    except Exception as exc:
        logger.warning("Failed to start V2 outbox enqueue thread for %s/%s: %s", tenant_id, shop_id, exc)
        return False
    return True
```

- [x] **Step 6: 重跑 helper 测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_outbox_runtime_dispatch.py -q
```

Expected:

- `3 passed`

### Task 2: 固定 inventory commit 的提交后触发行为

**Files:**
- Modify: `backend/tests/test_v2_clarification_confirmation.py`
- Modify: `backend/app/services/v2_conversation.py`

- [x] **Step 1: 先写失败测试，确认 inventory confirmation approve 会在 commit 后触发 enqueue**

测试要点：

```python
def test_v2_approve_inventory_confirmation_enqueues_outbox_drain_after_commit(client, db_session, monkeypatch) -> None:
    observed = {}

    def fake_enqueue_v2_outbox_drain(*, tenant_id: str, shop_id: str, **kwargs) -> bool:
        verification_session = get_session_factory()()
        try:
            outbox_event = verification_session.scalar(
                select(V2OutboxEvent).where(V2OutboxEvent.aggregate_id == task_run_id)
            )
            observed["tenant_id"] = tenant_id
            observed["shop_id"] = shop_id
            observed["status"] = outbox_event.status
        finally:
            verification_session.close()
        return True

    monkeypatch.setattr(v2_conversation, "enqueue_v2_outbox_drain", fake_enqueue_v2_outbox_drain)
    response = client.post(...)

    assert response.status_code == 200
    assert observed["tenant_id"] == "tenant_a"
    assert observed["shop_id"] == "shop_a1"
    assert observed["status"] == "pending"
```

- [x] **Step 2: 再写失败测试，确认非 inventory approval 不会触发 enqueue**

测试要点：

```python
def test_v2_approve_manual_review_confirmation_does_not_enqueue_outbox_drain(client, db_session, monkeypatch) -> None:
    calls = []

    def fake_enqueue_v2_outbox_drain(**kwargs) -> bool:
        calls.append(kwargs)
        return True

    monkeypatch.setattr(v2_conversation, "enqueue_v2_outbox_drain", fake_enqueue_v2_outbox_drain)
    response = client.post(...)

    assert response.status_code == 200
    assert calls == []
```

- [x] **Step 3: 运行 confirmation 相关测试，确认当前未触发 enqueue 而失败**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_clarification_confirmation.py -q
```

- [x] **Step 4: 在 `approve_v2_confirmation(...)` 中实现提交后触发**

实现要点：

```python
from app.services.v2_outbox_runtime_dispatch import enqueue_v2_outbox_drain


def approve_v2_confirmation(...):
    try:
        should_enqueue_outbox = False
        ...
        if confirmation.confirmation_type == "inventory.stock_in":
            ...
            should_enqueue_outbox = True
        elif confirmation.confirmation_type == "inventory.stock_out":
            ...
            should_enqueue_outbox = True
        ...
        db_session.commit()
    except Exception:
        db_session.rollback()
        raise

    if should_enqueue_outbox:
        enqueue_v2_outbox_drain(tenant_id=tenant_id, shop_id=shop_id)
    return confirmation
```

- [x] **Step 5: 重跑 confirmation 相关测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_clarification_confirmation.py -q
```

Expected:

- 相关新增用例通过

### Task 3: 做阶段验收

**Files:**
- Verify: `backend/tests/test_v2_outbox_runtime_dispatch.py`
- Verify: `backend/tests/test_v2_clarification_confirmation.py`
- Verify: `backend/tests/test_v2_outbox_tasks.py`
- Verify: `backend/tests/test_v2_outbox_worker.py`
- Verify: `backend/tests/test_v2_outbox_dispatch.py`

- [x] **Step 1: 运行目标回归**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_outbox_runtime_dispatch.py backend/tests/test_v2_clarification_confirmation.py backend/tests/test_v2_outbox_tasks.py backend/tests/test_v2_outbox_worker.py backend/tests/test_v2_outbox_dispatch.py -q
```

- [x] **Step 2: 运行关键 V2 / worker 回归**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_alembic_bootstrap.py backend/tests/test_v2_identity_context.py backend/tests/test_v2_conversation_runtime.py backend/tests/test_v2_clarification_confirmation.py backend/tests/test_v2_inventory_ledger.py backend/tests/test_v2_inventory_read_api.py backend/tests/test_v2_inventory_corrections_api.py backend/tests/test_v2_inventory_stock_out_api.py backend/tests/test_v2_outbox.py backend/tests/test_v2_outbox_dispatch.py backend/tests/test_v2_outbox_worker.py backend/tests/test_v2_outbox_tasks.py backend/tests/test_v2_outbox_runtime_dispatch.py backend/tests/test_v2_inventory_projection_replay.py backend/tests/test_v2_internal_api.py backend/tests/test_runtime_tasks.py backend/tests/test_worker_bootstrap.py backend/tests/test_openapi_contract_snapshot.py -q
```

- [x] **Step 3: 如关键回归通过，再运行完整 backend 测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests -q
```
