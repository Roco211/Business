# AI 原生 SaaS V2 Outbox Due Scope Drain 实现计划
> **给智能执行代理（agentic workers）：** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务逐项实现本计划。步骤使用 checkbox（`- [ ]`）语法跟踪。

**Goal:** 为 V2 outbox 增加一个“系统级兜底消费”入口，能够扫描所有已到可执行时间的 `tenant/shop` 作用域，并逐个执行现有 scoped drain。

**Architecture:** 当前 V2 已具备单个 `tenant/shop` 的 outbox drain、Celery worker task 和提交后安全触发，但还缺少一个不依赖业务请求的全局兜底入口。本切片新增 `v2_outbox_due_scopes.py`，负责查询 `status='pending'` 且 `available_at <= now` 的 outbox 作用域，并按最早可执行时间顺序逐个调用 `drain_v2_outbox_events(...)`；再新增 `v2_outbox_due_tasks.py` 作为 Celery task 包装器，在独立数据库会话中执行 sweep 并提交事务。这个切片只提供可调度的任务入口，不把具体周期策略写死。

**Tech Stack:** Python、SQLAlchemy、Celery、pytest

---

## 文件结构

- 创建 `backend/app/services/v2_outbox_due_scopes.py`：实现 due scope 扫描与聚合 drain 结果。
- 创建 `backend/tests/test_v2_outbox_due_scopes.py`：覆盖作用域选择、顺序、上限和参数校验。
- 创建 `backend/app/workers/v2_outbox_due_tasks.py`：实现 Celery task 包装器。
- 创建 `backend/tests/test_v2_outbox_due_tasks.py`：覆盖 task commit / rollback / close / 注册。
- 修改 `backend/app/workers/celery_app.py`：注册新的 due scope worker task。
- 修改 `backend/tests/test_worker_bootstrap.py`：校验 Celery include 与 task 注册。

### Task 1: 固定 due scope 扫描与 drain 行为

**Files:**
- Create: `backend/tests/test_v2_outbox_due_scopes.py`
- Create: `backend/app/services/v2_outbox_due_scopes.py`

- [x] **Step 1: 先写失败测试，确认会按最早 `available_at` 顺序逐个处理 due scope**

测试要点：

```python
def test_drain_due_v2_outbox_scopes_processes_due_scopes_in_oldest_first_order(db_session, monkeypatch) -> None:
    due_service = _load_v2_outbox_due_scopes_service()
    _seed_outbox_scope(db_session, tenant_id="tenant_a", shop_id="shop_a1")
    _seed_outbox_scope(db_session, tenant_id="tenant_b", shop_id="shop_b1")
    _seed_due_outbox_event(... tenant_id="tenant_b", shop_id="shop_b1", available_at=_dt("2026-04-19T09:40:00"))
    _seed_due_outbox_event(... tenant_id="tenant_a", shop_id="shop_a1", available_at=_dt("2026-04-19T09:50:00"))
    called_scopes = []

    monkeypatch.setattr(due_service, "drain_v2_outbox_events", _fake_drain)

    result = due_service.drain_due_v2_outbox_scopes(
        db_session,
        scope_limit=10,
        batch_limit_per_scope=20,
        max_batches_per_scope=3,
        now=_dt("2026-04-19T10:00:00"),
    )

    assert called_scopes == [("tenant_b", "shop_b1"), ("tenant_a", "shop_a1")]
    assert result.scope_count == 2
    assert result.claimed_count == 5
```

- [x] **Step 2: 再写失败测试，确认会跳过 future / non-pending scope，并受 `scope_limit` 约束**

测试要点：

```python
def test_drain_due_v2_outbox_scopes_respects_scope_limit_and_due_filter(db_session, monkeypatch) -> None:
    ...
    assert called_scopes == [("tenant_b", "shop_b1"), ("tenant_a", "shop_a1")]
    assert result.scope_count == 2
```

- [x] **Step 3: 再写失败测试，确认无效配置会被拒绝**

测试要点：

```python
def test_drain_due_v2_outbox_scopes_rejects_invalid_limits(db_session) -> None:
    with pytest.raises(ValueError, match="scope_limit must be > 0"):
        ...
    with pytest.raises(ValueError, match="batch_limit_per_scope must be > 0"):
        ...
    with pytest.raises(ValueError, match="max_batches_per_scope must be > 0"):
        ...
```

- [x] **Step 4: 运行 due scope 测试，确认当前模块缺失而失败**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_outbox_due_scopes.py -q
```

- [x] **Step 5: 实现最小 due scope drain service**

`backend/app/services/v2_outbox_due_scopes.py`

```python
@dataclass(frozen=True)
class V2OutboxDueScopesDrainResult:
    scope_limit: int
    batch_limit_per_scope: int
    max_batches_per_scope: int
    scope_count: int
    claimed_count: int
    completed_count: int
    retried_count: int
    failed_count: int
    drained_at: datetime


def drain_due_v2_outbox_scopes(...):
    due_scopes = db_session.execute(
        select(V2OutboxEvent.tenant_id, V2OutboxEvent.shop_id)
        .where(...)
        .group_by(V2OutboxEvent.tenant_id, V2OutboxEvent.shop_id)
        .order_by(func.min(V2OutboxEvent.available_at).asc(), ...)
        .limit(scope_limit)
    ).all()
    ...
    for tenant_id, shop_id in due_scopes:
        batch_result = drain_v2_outbox_events(...)
        ...
```

- [x] **Step 6: 重跑 due scope 测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_outbox_due_scopes.py -q
```

Expected:

- `3 passed`

### Task 2: 固定 Celery due scope worker task 行为

**Files:**
- Create: `backend/tests/test_v2_outbox_due_tasks.py`
- Create: `backend/app/workers/v2_outbox_due_tasks.py`
- Modify: `backend/app/workers/celery_app.py`
- Modify: `backend/tests/test_worker_bootstrap.py`

- [x] **Step 1: 先写失败测试，确认 task 包装器会调用 due scope drain 并提交事务**

测试要点：

```python
def test_v2_outbox_due_task_wrapper_invokes_drain_and_commits(monkeypatch) -> None:
    fake_session = _FakeSession()
    ...
    result = v2_outbox_due_tasks.drain_due_v2_outbox_scopes(
        scope_limit=20,
        batch_limit_per_scope=5,
        max_batches_per_scope=2,
    )

    assert result["scope_count"] == 3
    assert fake_session.committed is True
```

- [x] **Step 2: 再写失败测试，确认异常时会回滚并关闭会话**

测试要点：

```python
def test_v2_outbox_due_task_wrapper_rolls_back_on_failure(monkeypatch) -> None:
    ...
    with pytest.raises(RuntimeError, match="boom"):
        v2_outbox_due_tasks.drain_due_v2_outbox_scopes()
```

- [x] **Step 3: 再写失败测试，确认 task 已注册到显式 celery app**

测试要点：

```python
def test_v2_outbox_due_task_is_registered_on_explicit_celery_app() -> None:
    assert v2_outbox_due_tasks.drain_due_v2_outbox_scopes.name == "app.workers.v2_outbox_due_tasks.drain_due_v2_outbox_scopes"
```

- [x] **Step 4: 扩展 worker bootstrap 测试，确认 include 包含新模块**

- [x] **Step 5: 运行 due task 测试，确认当前模块/注册缺失而失败**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_outbox_due_tasks.py backend/tests/test_worker_bootstrap.py -q
```

- [x] **Step 6: 实现最小 due scope Celery task**

`backend/app/workers/v2_outbox_due_tasks.py`

```python
@celery_app.task(name="app.workers.v2_outbox_due_tasks.drain_due_v2_outbox_scopes")
def drain_due_v2_outbox_scopes(...) -> dict[str, object]:
    db_session = get_session_factory()()
    try:
        result = run_due_scope_drain(...)
        db_session.commit()
        return {...}
    except Exception:
        db_session.rollback()
        raise
    finally:
        db_session.close()
```

- [x] **Step 7: 重跑 due task 测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_outbox_due_tasks.py backend/tests/test_worker_bootstrap.py -q
```

Expected:

- `4 passed`

### Task 3: 做阶段验收

**Files:**
- Verify: `backend/tests/test_v2_outbox_due_scopes.py`
- Verify: `backend/tests/test_v2_outbox_due_tasks.py`
- Verify: `backend/tests/test_v2_outbox_runtime_dispatch.py`
- Verify: `backend/tests/test_v2_outbox_tasks.py`
- Verify: `backend/tests/test_v2_outbox_worker.py`
- Verify: `backend/tests/test_v2_outbox_dispatch.py`

- [x] **Step 1: 运行目标回归**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_outbox_due_scopes.py backend/tests/test_v2_outbox_due_tasks.py backend/tests/test_v2_outbox_runtime_dispatch.py backend/tests/test_v2_outbox_tasks.py backend/tests/test_v2_outbox_worker.py backend/tests/test_v2_outbox_dispatch.py -q
```

- [x] **Step 2: 运行关键 V2 / worker 回归**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_alembic_bootstrap.py backend/tests/test_v2_identity_context.py backend/tests/test_v2_conversation_runtime.py backend/tests/test_v2_clarification_confirmation.py backend/tests/test_v2_inventory_ledger.py backend/tests/test_v2_inventory_read_api.py backend/tests/test_v2_inventory_corrections_api.py backend/tests/test_v2_inventory_stock_out_api.py backend/tests/test_v2_outbox.py backend/tests/test_v2_outbox_dispatch.py backend/tests/test_v2_outbox_worker.py backend/tests/test_v2_outbox_tasks.py backend/tests/test_v2_outbox_runtime_dispatch.py backend/tests/test_v2_outbox_due_scopes.py backend/tests/test_v2_outbox_due_tasks.py backend/tests/test_v2_inventory_projection_replay.py backend/tests/test_v2_internal_api.py backend/tests/test_runtime_tasks.py backend/tests/test_worker_bootstrap.py backend/tests/test_openapi_contract_snapshot.py -q
```

- [x] **Step 3: 如关键回归通过，再运行完整 backend 测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests -q
```
