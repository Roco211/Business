# AI 原生 SaaS V2 库存更新事件来源闭环实施计划

> **给智能执行代理（agentic workers）：** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务逐项实现本计划。步骤使用 checkbox（`- [ ]`）语法跟踪。

**Goal:** 让 receipt-derived `inventory.stock_in` 在 outbox worker 派发出的 `inventory.updated` stream event 中继续保留票据来源字段，完成从 confirmation 到 realtime inventory projection 的 provenance 闭环。

**Architecture:** 不改变 inventory projection 的真相来源，仍由 outbox payload 驱动 `inventory.updated`。只在 `backend/app/services/v2_outbox_dispatch.py` 的 stream event data 构造阶段，把已存在于 outbox payload 的 provenance 字段透传给 `inventory.updated`，并用单测与 websocket 测试双重覆盖。

**Tech Stack:** Python、FastAPI、SQLAlchemy、pytest、现有 V2 outbox dispatch / websocket 基础设施

---

## 文件结构

- 修改 `backend/app/services/v2_outbox_dispatch.py`：将 receipt provenance 从 outbox payload 透传到 `inventory.updated` stream event。
- 修改 `backend/tests/test_v2_outbox_dispatch.py`：新增 outbox dispatch 的 provenance 红绿测试。
- 修改 `backend/tests/test_v2_session_stream_ws.py`：新增 receipt-derived inventory.updated websocket 红绿测试。

### Task 1: 用失败测试固定 inventory.updated provenance 缺口

**Files:**
- Modify: `backend/tests/test_v2_outbox_dispatch.py`
- Modify: `backend/tests/test_v2_session_stream_ws.py`

- [x] **Step 1: 新增 outbox dispatch 单测**

```python
assert stream_event.payload_json["source_type"] == "receipt-document"
assert stream_event.payload_json["source_document_id"] == "vdoc_receipt_001"
assert stream_event.payload_json["source_media_asset_id"] == "vmedia_receipt_001"
assert stream_event.payload_json["ledger_source_type"] == "task_run"
```

- [x] **Step 2: 新增 websocket worker 派发测试**

```python
assert inventory_event["event_type"] == "inventory.updated"
assert inventory_event["data"]["source_type"] == "receipt-document"
assert inventory_event["data"]["source_document_id"] == "vdoc_receipt_001"
assert inventory_event["data"]["source_media_asset_id"] == "vmedia_receipt_001"
```

- [x] **Step 3: 运行红灯测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_outbox_dispatch.py::test_dispatch_v2_outbox_events_appends_receipt_provenance_to_inventory_updated_stream_event backend/tests/test_v2_session_stream_ws.py::test_v2_session_stream_ws_delivers_receipt_inventory_update_provenance_before_keepalive -q
```

Expected: FAIL，因为当前 `inventory.updated` event data 只包含 `inventory_item_id` / `inventory_event_id` / `event_type` / `quantity_after` / `unit`。

### Task 2: 在 outbox dispatch 中透传 provenance

**Files:**
- Modify: `backend/app/services/v2_outbox_dispatch.py`

- [x] **Step 1: 抽出 inventory.updated event data builder**

```python
def _build_inventory_updated_stream_payload(outbox_event: V2OutboxEvent, inventory_item_id: str, unit: str | None, inventory_event_id: str | None, inventory_event_type: str | None) -> dict[str, object]:
    payload = {
        "inventory_item_id": inventory_item_id,
        "inventory_event_id": inventory_event_id,
        "event_type": inventory_event_type,
        "quantity_after": outbox_event.payload_json.get("quantity_after"),
        "unit": unit,
    }
    for key in ("source_type", "source_id", "source_document_id", "source_media_asset_id", "ledger_source_type", "ledger_source_id"):
        if outbox_event.payload_json.get(key) is not None:
            payload[key] = outbox_event.payload_json.get(key)
    return payload
```

- [x] **Step 2: 在 `_append_inventory_updated_stream_event(...)` 中复用该 builder**

- [x] **Step 3: 重跑目标测试，确认绿灯**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_outbox_dispatch.py::test_dispatch_v2_outbox_events_appends_receipt_provenance_to_inventory_updated_stream_event backend/tests/test_v2_session_stream_ws.py::test_v2_session_stream_ws_delivers_receipt_inventory_update_provenance_before_keepalive -q
```

Expected: PASS。

### Task 3: 局部回归与整理

**Files:**
- Verify: `backend/tests/test_v2_outbox_dispatch.py`
- Verify: `backend/tests/test_v2_session_stream_ws.py`
- Verify: `backend/app/services/v2_outbox_dispatch.py`

- [x] **Step 1: 运行本刀相关测试切片**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_outbox_dispatch.py backend/tests/test_v2_session_stream_ws.py -q
```

Expected: PASS。

- [x] **Step 2: 检查 diff 与工作区状态**

Run:

```powershell
git diff --check
git status --short
```

Expected: 无格式错误，只包含本刀相关改动。
