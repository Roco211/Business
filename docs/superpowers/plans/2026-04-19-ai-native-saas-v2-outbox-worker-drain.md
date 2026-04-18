# AI 原生 SaaS V2 Outbox Worker Drain 实现计划
> **给智能执行代理（agentic workers）：** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务逐项实现本计划。步骤使用 checkbox（`- [ ]`）语法跟踪。

**Goal:** 为 V2 outbox 增加一个最小可用的有界 worker drain 服务，让后台 worker 能够连续处理多批 pending outbox，并获得可观测的聚合结果。

**Architecture:** 现有 `dispatch_v2_outbox_events` 已经完成单批领取、派发、完成、失败与重试回写。本切片只在 service 层新增 `v2_outbox_worker.py`，提供 `drain_v2_outbox_events(...)` 作为后台 worker 的有界循环原语：每一轮调用 dispatch-once，累加处理结果，遇到空批次或达到 `max_batches` 后停止；它不提交事务，由调用方或未来进程级 worker 入口决定事务边界。该设计避免新增 HTTP API，也不引入 Celery/Redis 依赖。

**Tech Stack:** Python、SQLAlchemy、pytest

---

## 文件结构

- 创建 `backend/app/services/v2_outbox_worker.py`：实现有界 drain 服务与聚合结果模型。
- 创建 `backend/tests/test_v2_outbox_worker.py`：覆盖多批处理、空队列停止、达到批次数上限停止、配置校验。
- 复用 `backend/app/services/v2_outbox_dispatch.py`：每一批仍由 dispatch-once 负责具体事件处理。
- 保持 `backend/app/services/v2_outbox.py` 不变：本切片不改变 outbox 生命周期状态机。

### Task 1: 固定 worker drain 的服务行为

**Files:**
- Create: `backend/tests/test_v2_outbox_worker.py`
- Create: `backend/app/services/v2_outbox_worker.py`

- [x] **Step 1: 先写失败测试，确认 drain 会跨多批连续处理 pending outbox**

测试要点：

```python
def test_drain_v2_outbox_events_processes_multiple_batches(db_session) -> None:
    worker_service = _load_v2_outbox_worker_service()
    _seed_worker_scope(db_session)
    _seed_inventory_item(db_session, inventory_item_id="vitem_cola", name="Cola")
    _seed_inventory_events(db_session, inventory_item_id="vitem_cola")
    _seed_supported_outbox_event(db_session, outbox_event_id="evt_001", inventory_item_id="vitem_cola")
    _seed_supported_outbox_event(db_session, outbox_event_id="evt_002", inventory_item_id="vitem_cola")
    _seed_supported_outbox_event(db_session, outbox_event_id="evt_003", inventory_item_id="vitem_cola")
    db_session.commit()

    result = worker_service.drain_v2_outbox_events(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        batch_limit=2,
        max_batches=5,
        now=_dt("2026-04-19T10:00:00"),
    )

    assert result.batches_run == 2
    assert result.claimed_count == 3
    assert result.completed_count == 3
    assert result.retried_count == 0
    assert result.failed_count == 0
```

- [x] **Step 2: 再写失败测试，确认空队列不会运行有效批次**

测试要点：

```python
def test_drain_v2_outbox_events_stops_when_no_events_are_claimed(db_session) -> None:
    worker_service = _load_v2_outbox_worker_service()
    _seed_worker_scope(db_session)
    db_session.commit()

    result = worker_service.drain_v2_outbox_events(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        batch_limit=10,
        max_batches=3,
        now=_dt("2026-04-19T10:00:00"),
    )

    assert result.batches_run == 0
    assert result.claimed_count == 0
```

- [x] **Step 3: 再写失败测试，确认达到 `max_batches` 后停止并保留剩余 pending**

测试要点：

```python
def test_drain_v2_outbox_events_stops_at_max_batches(db_session) -> None:
    worker_service = _load_v2_outbox_worker_service()
    _seed_worker_scope(db_session)
    _seed_inventory_item(db_session, inventory_item_id="vitem_cola", name="Cola")
    _seed_inventory_events(db_session, inventory_item_id="vitem_cola")
    for index in range(3):
        _seed_supported_outbox_event(
            db_session,
            outbox_event_id=f"evt_{index}",
            inventory_item_id="vitem_cola",
        )
    db_session.commit()

    result = worker_service.drain_v2_outbox_events(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        batch_limit=1,
        max_batches=2,
        now=_dt("2026-04-19T10:00:00"),
    )

    assert result.batches_run == 2
    assert result.claimed_count == 2
    assert _count_outbox_by_status(db_session, status="pending") == 1
    assert _count_outbox_by_status(db_session, status="completed") == 2
```

- [x] **Step 4: 再写失败测试，确认无效配置会被拒绝**

测试要点：

```python
def test_drain_v2_outbox_events_rejects_invalid_limits(db_session) -> None:
    worker_service = _load_v2_outbox_worker_service()

    with pytest.raises(ValueError, match="batch_limit must be > 0"):
        worker_service.drain_v2_outbox_events(
            db_session,
            tenant_id="tenant_a",
            shop_id="shop_a1",
            batch_limit=0,
            max_batches=1,
        )

    with pytest.raises(ValueError, match="max_batches must be > 0"):
        worker_service.drain_v2_outbox_events(
            db_session,
            tenant_id="tenant_a",
            shop_id="shop_a1",
            batch_limit=1,
            max_batches=0,
        )
```

- [x] **Step 5: 运行 worker 测试，确认当前缺少服务而失败**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_outbox_worker.py -q
```

Expected:

- FAIL，原因是 `app.services.v2_outbox_worker` 尚未实现。

- [x] **Step 6: 实现最小 worker drain 服务**

`backend/app/services/v2_outbox_worker.py`

```python
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.services.v2_outbox_dispatch import dispatch_v2_outbox_events
from app.services.v2_time import utc_now_naive


@dataclass(frozen=True)
class V2OutboxDrainResult:
    tenant_id: str
    shop_id: str
    batch_limit: int
    max_batches: int
    batches_run: int
    claimed_count: int
    completed_count: int
    retried_count: int
    failed_count: int
    drained_at: datetime


def drain_v2_outbox_events(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    batch_limit: int = 50,
    max_batches: int = 10,
    retry_after_seconds: int | None = 60,
    now: datetime | None = None,
) -> V2OutboxDrainResult:
    if batch_limit <= 0:
        raise ValueError("batch_limit must be > 0")
    if max_batches <= 0:
        raise ValueError("max_batches must be > 0")

    drain_now = now or utc_now_naive()
    batches_run = 0
    claimed_count = 0
    completed_count = 0
    retried_count = 0
    failed_count = 0

    for _ in range(max_batches):
        batch_result = dispatch_v2_outbox_events(
            db_session,
            tenant_id=tenant_id,
            shop_id=shop_id,
            limit=batch_limit,
            retry_after_seconds=retry_after_seconds,
            now=drain_now,
        )
        if batch_result.claimed_count == 0:
            break

        batches_run += 1
        claimed_count += batch_result.claimed_count
        completed_count += batch_result.completed_count
        retried_count += batch_result.retried_count
        failed_count += batch_result.failed_count

    return V2OutboxDrainResult(...)
```

- [x] **Step 7: 重跑 worker 测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_outbox_worker.py -q
```

Expected:

- `4 passed`

### Task 2: 做阶段验收

**Files:**
- Verify: `backend/tests/test_v2_outbox_worker.py`
- Verify: `backend/tests/test_v2_outbox_dispatch.py`
- Verify: `backend/tests/test_v2_outbox.py`
- Verify: `backend/tests/test_v2_inventory_projection_replay.py`

- [x] **Step 1: 运行 worker + dispatch 目标测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_outbox_worker.py backend/tests/test_v2_outbox_dispatch.py backend/tests/test_v2_outbox.py backend/tests/test_v2_inventory_projection_replay.py -q
```

- [x] **Step 2: 运行关键 V2 回归**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_alembic_bootstrap.py backend/tests/test_v2_identity_context.py backend/tests/test_v2_conversation_runtime.py backend/tests/test_v2_clarification_confirmation.py backend/tests/test_v2_inventory_ledger.py backend/tests/test_v2_inventory_read_api.py backend/tests/test_v2_inventory_corrections_api.py backend/tests/test_v2_inventory_stock_out_api.py backend/tests/test_v2_outbox.py backend/tests/test_v2_outbox_dispatch.py backend/tests/test_v2_outbox_worker.py backend/tests/test_v2_inventory_projection_replay.py backend/tests/test_v2_internal_api.py backend/tests/test_openapi_contract_snapshot.py -q
```

- [x] **Step 3: 如关键 V2 回归通过，再运行完整 backend 测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests -q
```
