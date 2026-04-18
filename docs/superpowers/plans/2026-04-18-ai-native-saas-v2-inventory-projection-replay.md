# AI 原生 SaaS V2 库存投影重放实现计划
> **给智能执行代理（agentic workers）：** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务逐项实现本计划。步骤使用 checkbox（`- [ ]`）语法跟踪。

**Goal:** 为 V2 新增 `POST /api/v2/internal/projections/replay`，能够基于库存账本（inventory ledger）重建当前 tenant/shop 下的库存投影（stock snapshot）。

**Architecture:** 当前 V2 库存提交已经同步写入 `V2InventoryLedgerEvent` 与 `V2InventoryStockSnapshot`，但 spec 明确要求“数据库事件是真相、投影可 replay / catch-up”。本切片新增独立的库存投影重放服务，不把 replay 逻辑塞进 `v2_inventory.py` 的写路径；internal route 继续复用 `Authorization + X-Context-Token` 约束，只允许在当前 tenant/shop 上下文内重放整个门店或单个商品的库存投影。

**Tech Stack:** Python、FastAPI、SQLAlchemy、Pydantic、pytest、OpenAPI snapshot

---

## 文件结构

- 创建 `backend/app/services/v2_inventory_projections.py`：封装基于账本事件重建库存快照的服务逻辑。
- 修改 `backend/app/contracts/v2/internal.py`：增加 projection replay 请求/响应模型。
- 修改 `backend/app/api/v2/routes/internal.py`：新增 `/api/v2/internal/projections/replay` 路由。
- 创建 `backend/tests/test_v2_inventory_projection_replay.py`：覆盖 service 层 replay 行为。
- 修改 `backend/tests/test_v2_internal_api.py`：覆盖 replay API 响应与作用域约束。
- 修改 `project_docs/generated/openapi-v1.json`：更新 OpenAPI 快照。

### Task 1: 固定库存投影重放服务行为

**Files:**
- Create: `backend/tests/test_v2_inventory_projection_replay.py`
- Create: `backend/app/services/v2_inventory_projections.py`

- [x] **Step 1: 先写失败测试，确认 replay 能基于账本重建快照并删除无账本的陈旧快照**

```python
def test_replay_v2_inventory_stock_projection_rebuilds_snapshots_from_ledger_and_deletes_stale_rows(db_session) -> None:
    seed_v2_inventory_projection_scope(db_session)
    seed_v2_inventory_item(db_session, inventory_item_id="vitem_cola", name="Cola")
    seed_v2_inventory_snapshot(
        db_session,
        snapshot_id="vsnapshot_cola",
        inventory_item_id="vitem_cola",
        current_quantity=Decimal("99"),
        current_price=Decimal("99"),
    )
    seed_v2_inventory_item(db_session, inventory_item_id="vitem_stale", name="Stale")
    seed_v2_inventory_snapshot(
        db_session,
        snapshot_id="vsnapshot_stale",
        inventory_item_id="vitem_stale",
        current_quantity=Decimal("7"),
        current_price=Decimal("10"),
    )
    seed_v2_inventory_event(... quantity_delta=Decimal("3"), price=Decimal("18.5"), occurred_at=_dt("2026-04-18T10:00:00"))
    seed_v2_inventory_event(... quantity_delta=Decimal("-1"), price=Decimal("18.5"), occurred_at=_dt("2026-04-18T11:00:00"))

    result = replay_v2_inventory_stock_projection(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
    )

    assert result.replayed_item_count == 1
    assert result.replayed_snapshot_count == 1
    assert result.deleted_snapshot_count == 1
    assert result.ledger_event_count == 2
```

- [x] **Step 2: 再写失败测试，确认单商品 replay 只影响目标商品**

```python
def test_replay_v2_inventory_stock_projection_scopes_to_single_item(db_session) -> None:
    ...
    assert refreshed_target.current_quantity == Decimal("2")
    assert untouched_other.current_quantity == Decimal("8")
```

- [x] **Step 3: 运行测试，确认当前缺少 projection replay 服务而失败**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_inventory_projection_replay.py -q
```

- [x] **Step 4: 实现最小 projection replay 服务**

`backend/app/services/v2_inventory_projections.py`

```python
@dataclass(frozen=True)
class V2InventoryProjectionReplayResult:
    tenant_id: str
    shop_id: str
    inventory_item_id: str | None
    replayed_item_count: int
    replayed_snapshot_count: int
    deleted_snapshot_count: int
    ledger_event_count: int
    replayed_at: datetime


def replay_v2_inventory_stock_projection(...):
    events = db_session.scalars(
        select(V2InventoryLedgerEvent)
        .where(...)
        .order_by(V2InventoryLedgerEvent.occurred_at.asc(), V2InventoryLedgerEvent.event_id.asc())
    ).all()
    existing_snapshots = {...}
    aggregates = {...}
    for event in events:
        state.quantity += Decimal(event.quantity_delta)
        state.price = event.price
        state.updated_at = event.occurred_at
    ...
    db_session.flush()
    return V2InventoryProjectionReplayResult(...)
```

- [x] **Step 5: 重跑 projection replay service 测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_inventory_projection_replay.py -q
```

Expected:

- `2 passed`

### Task 2: 暴露 internal projection replay API

**Files:**
- Modify: `backend/app/contracts/v2/internal.py`
- Modify: `backend/app/api/v2/routes/internal.py`
- Modify: `backend/tests/test_v2_internal_api.py`

- [x] **Step 1: 写失败测试，确认 internal replay API 返回当前上下文下的重放结果**

```python
def test_v2_projection_replay_rebuilds_inventory_snapshot_for_current_context(client, db_session) -> None:
    token, context_token = _seed_v2_internal_context(client, db_session)
    seed_v2_internal_inventory_replay_fixture(db_session)

    response = client.post(
        "/api/v2/internal/projections/replay",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={},
    )

    assert response.status_code == 200
    assert response.json()["data"]["tenant_id"] == "tenant_a"
    assert response.json()["data"]["shop_id"] == "shop_a1"
    assert response.json()["data"]["replayed_item_count"] == 1
    assert response.json()["data"]["deleted_snapshot_count"] == 1
```

- [x] **Step 2: 运行 API 测试，确认当前缺少 replay route 而失败**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_internal_api.py -k "projection_replay" -q
```

- [x] **Step 3: 扩展 internal contract 并新增 replay route**

`backend/app/contracts/v2/internal.py`

```python
class V2ProjectionReplayRequest(BaseModel):
    inventory_item_id: str | None = None


class V2ProjectionReplayData(BaseModel):
    tenant_id: str
    shop_id: str
    inventory_item_id: str | None
    replayed_item_count: int
    replayed_snapshot_count: int
    deleted_snapshot_count: int
    ledger_event_count: int
    replayed_at: datetime
```

`backend/app/api/v2/routes/internal.py`

```python
@router.post("/projections/replay", response_model=V2DataEnvelope[V2ProjectionReplayData])
def post_v2_projection_replay(...):
    result = replay_v2_inventory_stock_projection(...)
    return V2DataEnvelope(data=V2ProjectionReplayData(...))
```

- [x] **Step 4: 重跑 replay API 测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_internal_api.py -k "projection_replay" -q
```

Expected:

- `1 passed`

### Task 3: 更新契约快照并做阶段验收

**Files:**
- Verify: `backend/tests/test_v2_inventory_projection_replay.py`
- Verify: `backend/tests/test_v2_internal_api.py`
- Verify: `backend/tests/test_openapi_contract_snapshot.py`
- Modify: `project_docs/generated/openapi-v1.json`

- [x] **Step 1: 更新 OpenAPI 快照**

Run:

```powershell
$env:PYTHONPATH="backend"; @'
import json
from pathlib import Path
from app.main import create_app

snapshot_path = Path("project_docs/generated/openapi-v1.json")
snapshot_path.write_text(
    json.dumps(create_app().openapi(), ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
'@ | python -
```

- [x] **Step 2: 运行新增目标测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_inventory_projection_replay.py backend/tests/test_v2_internal_api.py -q
```

- [x] **Step 3: 运行 OpenAPI 快照测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_openapi_contract_snapshot.py -q
```

- [x] **Step 4: 运行关键 V2 回归**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_alembic_bootstrap.py backend/tests/test_v2_identity_context.py backend/tests/test_v2_conversation_runtime.py backend/tests/test_v2_clarification_confirmation.py backend/tests/test_v2_inventory_ledger.py backend/tests/test_v2_inventory_read_api.py backend/tests/test_v2_inventory_corrections_api.py backend/tests/test_v2_inventory_stock_out_api.py backend/tests/test_v2_outbox.py backend/tests/test_v2_inventory_projection_replay.py backend/tests/test_v2_internal_api.py backend/tests/test_openapi_contract_snapshot.py -q
```

- [x] **Step 5: 如关键 V2 回归通过，再运行完整 backend 测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests -q
```
