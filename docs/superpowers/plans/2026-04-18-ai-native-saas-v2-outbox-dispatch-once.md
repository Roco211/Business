# AI 原生 SaaS V2 Outbox 单次派发实现计划
> **给智能执行代理（agentic workers）：** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务逐项实现本计划。步骤使用 checkbox（`- [ ]`）语法跟踪。

**Goal:** 为 V2 新增一个最小可用的 outbox 单次派发（dispatch once）服务，让系统能够领取一批 pending outbox，执行已支持事件，并把结果回写为 completed / failed / retry pending。

**Architecture:** 当前 V2 已经具备 outbox claim、projection replay 和 lifecycle 状态回写，但还缺少把这些能力真正串起来的 dispatcher。这个切片不新增新的 public/internal HTTP API，而是在 service 层新增独立的 `v2_outbox_dispatch.py`，只支持已存在的库存提交事件 `inventory.stock_in.committed` / `inventory.stock_out.committed`；处理逻辑统一落到库存 projection replay，失败策略分成三类：不支持事件终止失败、payload 不合法终止失败、handler 异常按可重试失败回到 `pending`。

**Tech Stack:** Python、SQLAlchemy、pytest

---

## 文件结构

- 创建 `backend/app/services/v2_outbox_dispatch.py`：实现单次派发服务与结果模型。
- 创建 `backend/tests/test_v2_outbox_dispatch.py`：覆盖成功派发、终止失败、可重试失败。
- 复用 `backend/app/services/v2_outbox.py`：claim / complete / fail 生命周期。
- 复用 `backend/app/services/v2_inventory_projections.py`：已支持事件统一走 projection replay。

### Task 1: 固定 outbox dispatch-once 的服务行为

**Files:**
- Create: `backend/tests/test_v2_outbox_dispatch.py`
- Create: `backend/app/services/v2_outbox_dispatch.py`

- [x] **Step 1: 先写失败测试，确认支持的库存提交事件会 replay projection 并标记 completed**

```python
def test_dispatch_v2_outbox_events_replays_projection_and_completes_supported_inventory_event(db_session) -> None:
    dispatch_service = _load_v2_outbox_dispatch_service()
    _seed_dispatch_scope(db_session)
    _seed_inventory_item(...)
    _seed_inventory_snapshot(... current_quantity=Decimal("99"))
    _seed_inventory_event(... event_type="stock_in", quantity_delta=Decimal("3"), price=Decimal("18.5"))
    _seed_inventory_event(... event_type="stock_out", quantity_delta=Decimal("-1"), price=Decimal("18.5"))
    _seed_outbox_event(
        db_session,
        outbox_event_id="evt_inventory_commit",
        event_type="inventory.stock_in.committed",
        payload_json={"inventory_item_id": "vitem_cola"},
    )

    result = dispatch_service.dispatch_v2_outbox_events(...)

    assert result.claimed_count == 1
    assert result.completed_count == 1
    assert result.retried_count == 0
    assert result.failed_count == 0
    assert snapshot.current_quantity == Decimal("2")
    assert outbox.status == "completed"
```

- [x] **Step 2: 再写失败测试，确认 unsupported event 会终止失败，不进入 retry**

```python
def test_dispatch_v2_outbox_events_marks_unsupported_event_failed_without_retry(db_session) -> None:
    ...
    assert result.failed_count == 1
    assert outbox.status == "failed"
    assert outbox.last_error_code == "unsupported_outbox_event"
```

- [x] **Step 3: 再写失败测试，确认 projection handler 异常时会回到 pending 等待重试**

```python
def test_dispatch_v2_outbox_events_retries_when_projection_handler_raises(db_session, monkeypatch) -> None:
    monkeypatch.setattr(dispatch_service, "replay_v2_inventory_stock_projection", _blow_up)
    ...
    assert result.retried_count == 1
    assert outbox.status == "pending"
    assert outbox.available_at == _dt("2026-04-18T10:12:00")
    assert outbox.last_error_code == "dispatch_failed"
```

- [x] **Step 4: 运行 dispatch 测试，确认当前缺少 dispatch 服务而失败**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_outbox_dispatch.py -q
```

- [x] **Step 5: 实现最小 dispatch 服务**

`backend/app/services/v2_outbox_dispatch.py`

```python
SUPPORTED_DISPATCH_EVENT_TYPES = frozenset(
    {"inventory.stock_in.committed", "inventory.stock_out.committed"}
)


@dataclass(frozen=True)
class V2OutboxDispatchResult:
    tenant_id: str
    shop_id: str
    claimed_count: int
    completed_count: int
    retried_count: int
    failed_count: int
    dispatched_at: datetime


def dispatch_v2_outbox_events(...):
    claimed_events = claim_v2_outbox_events(...)
    for event in claimed_events:
        try:
            _dispatch_single_event(...)
            complete_v2_outbox_event(...)
        except _UnsupportedOutboxEvent:
            fail_v2_outbox_event(..., error_code="unsupported_outbox_event", retry_after_seconds=None)
        except _InvalidOutboxPayload:
            fail_v2_outbox_event(..., error_code="invalid_outbox_payload", retry_after_seconds=None)
        except Exception as exc:
            fail_v2_outbox_event(..., error_code="dispatch_failed", error_message=str(exc), retry_after_seconds=retry_after_seconds)
```

- [x] **Step 6: 重跑 dispatch 测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_outbox_dispatch.py -q
```

Expected:

- `3 passed`

### Task 2: 做阶段验收

**Files:**
- Verify: `backend/tests/test_v2_outbox_dispatch.py`
- Verify: `backend/tests/test_v2_outbox.py`
- Verify: `backend/tests/test_v2_inventory_projection_replay.py`
- Verify: `backend/tests/test_openapi_contract_snapshot.py`

- [x] **Step 1: 运行新增目标测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_outbox_dispatch.py backend/tests/test_v2_outbox.py backend/tests/test_v2_inventory_projection_replay.py -q
```

- [x] **Step 2: 运行关键 V2 回归**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_alembic_bootstrap.py backend/tests/test_v2_identity_context.py backend/tests/test_v2_conversation_runtime.py backend/tests/test_v2_clarification_confirmation.py backend/tests/test_v2_inventory_ledger.py backend/tests/test_v2_inventory_read_api.py backend/tests/test_v2_inventory_corrections_api.py backend/tests/test_v2_inventory_stock_out_api.py backend/tests/test_v2_outbox.py backend/tests/test_v2_outbox_dispatch.py backend/tests/test_v2_inventory_projection_replay.py backend/tests/test_v2_internal_api.py backend/tests/test_openapi_contract_snapshot.py -q
```

- [x] **Step 3: 如关键 V2 回归通过，再运行完整 backend 测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests -q
```
