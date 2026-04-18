# AI 原生 SaaS V2 Outbox Worker Task 实现计划
> **给智能执行代理（agentic workers）：** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务逐项实现本计划。步骤使用 checkbox（`- [ ]`）语法跟踪。

**Goal:** 为 V2 outbox drain 增加正式的 Celery worker task 入口，让后台进程可以在独立数据库会话中执行 drain、提交事务并返回结构化结果。

**Architecture:** `v2_outbox_worker.py` 只负责有界 drain 原语，不拥有事务边界。本切片新增 `app.workers.v2_outbox_tasks`，复用现有 Celery 基座与 `get_session_factory()`，在任务入口内部创建会话、调用 `drain_v2_outbox_events(...)`、成功时提交、异常时回滚并关闭会话；同时把新 task 注册到 `celery_app` 的 include 列表。这个切片不新增 HTTP API，也不引入新的调度系统。

**Tech Stack:** Python、Celery、SQLAlchemy、pytest

---

## 文件结构

- 创建 `backend/app/workers/v2_outbox_tasks.py`：实现 V2 outbox drain 的 Celery task 包装器。
- 创建 `backend/tests/test_v2_outbox_tasks.py`：覆盖 commit、rollback、close 和任务注册。
- 修改 `backend/app/workers/celery_app.py`：把新任务模块加入 Celery include。
- 修改 `backend/tests/test_worker_bootstrap.py`：校验 Celery app 会加载新任务模块。

### Task 1: 固定 V2 outbox worker task 行为

**Files:**
- Create: `backend/tests/test_v2_outbox_tasks.py`
- Create: `backend/app/workers/v2_outbox_tasks.py`
- Modify: `backend/app/workers/celery_app.py`
- Modify: `backend/tests/test_worker_bootstrap.py`

- [x] **Step 1: 先写失败测试，确认 task 包装器会调用 drain 服务、提交事务并返回结构化结果**

测试要点：

```python
def test_v2_outbox_task_wrapper_invokes_drain_and_commits(monkeypatch) -> None:
    fake_session = _FakeSession()

    def fake_get_session_factory():
        return lambda: fake_session

    def fake_run_outbox_drain(db_session, **kwargs) -> V2OutboxDrainResult:
        assert db_session is fake_session
        assert kwargs["tenant_id"] == "tenant_a"
        return V2OutboxDrainResult(...)

    monkeypatch.setattr(v2_outbox_tasks, "get_session_factory", fake_get_session_factory)
    monkeypatch.setattr(v2_outbox_tasks, "run_outbox_drain", fake_run_outbox_drain)

    result = v2_outbox_tasks.drain_v2_outbox("tenant_a", "shop_a1", batch_limit=20, max_batches=3)

    assert result["completed_count"] == 5
    assert fake_session.committed is True
    assert fake_session.closed is True
```

- [x] **Step 2: 再写失败测试，确认 drain 抛错时会回滚并关闭会话**

测试要点：

```python
def test_v2_outbox_task_wrapper_rolls_back_on_failure(monkeypatch) -> None:
    fake_session = _FakeSession()
    ...
    monkeypatch.setattr(v2_outbox_tasks, "run_outbox_drain", _raise_boom)

    with pytest.raises(RuntimeError, match="boom"):
        v2_outbox_tasks.drain_v2_outbox("tenant_a", "shop_a1")

    assert fake_session.rolled_back is True
    assert fake_session.closed is True
```

- [x] **Step 3: 再写失败测试，确认 task 已注册到显式 celery app**

测试要点：

```python
def test_v2_outbox_task_is_registered_on_explicit_celery_app() -> None:
    assert v2_outbox_tasks.celery_app is celery_app
    assert v2_outbox_tasks.drain_v2_outbox.app is celery_app
    assert v2_outbox_tasks.drain_v2_outbox.name == "app.workers.v2_outbox_tasks.drain_v2_outbox"
```

- [x] **Step 4: 扩展 worker bootstrap 测试，确认 celery include 包含新任务模块**

测试要点：

```python
def test_celery_app_uses_redis_broker_defaults() -> None:
    celery_app = create_celery_app()

    assert celery_app.conf.include == (
        "app.workers.runtime_tasks",
        "app.workers.v2_outbox_tasks",
    )
    assert "app.workers.v2_outbox_tasks.drain_v2_outbox" in celery_app.tasks
```

- [x] **Step 5: 运行 worker task 测试，确认当前缺少模块或注册而失败**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_outbox_tasks.py backend/tests/test_worker_bootstrap.py -q
```

- [x] **Step 6: 实现最小 Celery task 包装器与注册**

`backend/app/workers/v2_outbox_tasks.py`

```python
from app.db.session import get_session_factory
from app.services.v2_outbox_worker import drain_v2_outbox_events as run_outbox_drain
from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.v2_outbox_tasks.drain_v2_outbox")
def drain_v2_outbox(
    tenant_id: str,
    shop_id: str,
    batch_limit: int = 50,
    max_batches: int = 10,
    retry_after_seconds: int | None = 60,
) -> dict[str, object]:
    db_session = get_session_factory()()
    try:
        result = run_outbox_drain(...)
        db_session.commit()
        return {
            "tenant_id": result.tenant_id,
            "shop_id": result.shop_id,
            ...
            "drained_at": result.drained_at.isoformat(),
        }
    except Exception:
        db_session.rollback()
        raise
    finally:
        db_session.close()
```

- [x] **Step 7: 重跑 worker task 测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_outbox_tasks.py backend/tests/test_worker_bootstrap.py -q
```

Expected:

- `5 passed`

### Task 2: 做阶段验收

**Files:**
- Verify: `backend/tests/test_v2_outbox_tasks.py`
- Verify: `backend/tests/test_v2_outbox_worker.py`
- Verify: `backend/tests/test_v2_outbox_dispatch.py`
- Verify: `backend/tests/test_worker_bootstrap.py`

- [x] **Step 1: 运行 worker 目标回归**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_outbox_tasks.py backend/tests/test_v2_outbox_worker.py backend/tests/test_v2_outbox_dispatch.py backend/tests/test_worker_bootstrap.py -q
```

- [x] **Step 2: 运行关键 V2 / worker 回归**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_alembic_bootstrap.py backend/tests/test_v2_identity_context.py backend/tests/test_v2_conversation_runtime.py backend/tests/test_v2_clarification_confirmation.py backend/tests/test_v2_inventory_ledger.py backend/tests/test_v2_inventory_read_api.py backend/tests/test_v2_inventory_corrections_api.py backend/tests/test_v2_inventory_stock_out_api.py backend/tests/test_v2_outbox.py backend/tests/test_v2_outbox_dispatch.py backend/tests/test_v2_outbox_worker.py backend/tests/test_v2_inventory_projection_replay.py backend/tests/test_v2_internal_api.py backend/tests/test_runtime_tasks.py backend/tests/test_v2_outbox_tasks.py backend/tests/test_worker_bootstrap.py backend/tests/test_openapi_contract_snapshot.py -q
```

- [x] **Step 3: 如关键回归通过，再运行完整 backend 测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests -q
```
