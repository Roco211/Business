# AI 原生 SaaS V2 Outbox Inventory Stream Event 实现计划

> **给智能执行代理（agentic workers）：** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务逐项实现本计划。步骤使用 checkbox（`- [ ]`）语法跟踪。

**Goal:** 在 V2 outbox 成功完成库存 projection replay 后追加 durable `inventory.updated` session stream 事件，补上“提交事实 -> outbox -> projection -> 可回放实时事件”的最小链路。

**Architecture:** 不新增新的 public/internal API，也不让 websocket 直接依赖 outbox。`dispatch_v2_outbox_events(...)` 仍先重放库存投影；只有 projection 成功后，才根据 outbox payload 中的 `session_id` 追加 `inventory.updated` durable stream 事件。缺少 `session_id` 的旧事件继续只做 projection，不阻塞 outbox 完成。

**Tech Stack:** Python、SQLAlchemy、pytest

---

## 文件结构

- 修改 `backend/tests/test_v2_outbox_dispatch.py`：先固定成功 dispatch 后会追加 `inventory.updated` stream 事件。
- 修改 `backend/app/services/v2_outbox_dispatch.py`：projection 成功后写入 V2 stream 事件。

### Task 1: 固定 projection 后 durable stream 行为

**Files:**
- Modify: `backend/tests/test_v2_outbox_dispatch.py`
- Modify: `backend/app/services/v2_outbox_dispatch.py`

- [x] **Step 1: 先写失败测试，确认库存 projection 成功后追加 `inventory.updated`**

测试要点：

```python
def test_dispatch_v2_outbox_events_appends_inventory_updated_stream_event(db_session) -> None:
    _seed_dispatch_scope(db_session)
    _seed_conversation_task(db_session)
    _seed_inventory_item(...)
    _seed_inventory_event(...)
    _seed_outbox_event(
        db_session,
        outbox_event_id="evt_inventory_stream",
        event_type="inventory.stock_in.committed",
        payload_json={
            "session_id": "vsess_001",
            "task_run_id": "vtask_001",
            "inventory_item_id": "vitem_cola",
            "inventory_event_id": "vevent_cola_in",
            "event_type": "stock_in",
            "quantity_after": "3",
            "unit": "box",
        },
    )

    dispatch_service.dispatch_v2_outbox_events(...)

    assert stream_event.event_type == "inventory.updated"
    assert stream_event.seq == 1
    assert stream_event.payload_json["inventory_item_id"] == "vitem_cola"
```

- [x] **Step 2: 运行 dispatch 测试，确认红灯**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_outbox_dispatch.py -q
```

- [x] **Step 3: 实现最小 stream event 追加**

实现边界：

- projection replay 成功后调用 `append_v2_session_event(...)`。
- `session_id` 不是非空字符串时跳过 stream event，不让旧 outbox payload 失败。
- `task_run_id` 不是非空字符串时写入 `None`。
- event payload 包含：
  - `inventory_item_id`
  - `inventory_event_id`
  - `event_type`
  - `quantity_after`
  - `unit`
- `occurred_at` 使用当前 dispatch 时间。

- [x] **Step 4: 重跑目标回归**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_outbox_dispatch.py backend/tests/test_v2_session_stream_service.py backend/tests/test_v2_session_stream_api.py -q
```
