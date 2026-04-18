# AI 原生 SaaS V2 库存查询接口实现计划
> **给智能执行代理（agentic workers）：** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务逐项实现本计划。步骤使用 checkbox（`- [ ]`）语法跟踪。

**Goal:** 为 `/api/v2` 补齐最小库存查询面，支持在显式上下文下读取 tenant 级商品列表、shop 级库存投影列表与 shop 级库存账本事件列表。

**Architecture:** 本阶段只开放只读查询接口，不引入 correction、dashboard 聚合或写操作。`items` 走 tenant 边界，`stock` 与 `events` 同时按 `tenant_id + shop_id` 约束；API 层复用现有 `Authorization + X-Context-Token` 执行上下文，服务层封装查询与排序逻辑，路由层只做上下文校验和响应编排。

**Tech Stack:** Python、FastAPI、Pydantic、SQLAlchemy、pytest、OpenAPI snapshot

---

## 文件结构

- 新增 `backend/tests/test_v2_inventory_read_api.py`：覆盖 inventory items / stock / events 三个列表接口。
- 新增 `backend/app/contracts/v2/inventory.py`：定义 V2 inventory 查询响应模型。
- 新增 `backend/app/api/v2/routes/inventory.py`：新增 V2 inventory 查询路由。
- 修改 `backend/app/api/v2/router.py`：注册 inventory 路由。
- 修改 `backend/app/services/v2_inventory.py`：补充查询服务。
- 修改 `project_docs/generated/openapi-v1.json`：刷新 OpenAPI 快照。

### Task 1: 固定 inventory items 列表接口

**Files:**
- Create: `backend/tests/test_v2_inventory_read_api.py`
- Create: `backend/app/contracts/v2/inventory.py`
- Create: `backend/app/api/v2/routes/inventory.py`
- Modify: `backend/app/api/v2/router.py`
- Modify: `backend/app/services/v2_inventory.py`

- [ ] **Step 1: 先写失败测试，确认 items 接口按 tenant 返回商品**

```python
def test_v2_list_inventory_items_returns_tenant_scoped_items(client, db_session) -> None:
    token, context_token = _seed_v2_inventory_api_context(client, db_session)
    _commit_inventory_stock_in(
        db_session,
        task_run_id="vtask_items_1",
        tenant_id="tenant_a",
        shop_id="shop_a1",
        payload={"item_name": "Cola", "quantity": 2, "unit": "box", "price": 18.5},
    )
    _commit_inventory_stock_in(
        db_session,
        task_run_id="vtask_items_2",
        tenant_id="tenant_a",
        shop_id="shop_a1",
        payload={"item_name": "Orange", "quantity": 1, "unit": "box", "price": 12},
    )

    response = client.get(
        "/api/v2/inventory/items?limit=20",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["count"] == 2
    assert [item["name"] for item in payload["items"]] == ["Orange", "Cola"]
```

- [ ] **Step 2: 运行 items 测试，确认因为路由或契约缺失而失败**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_inventory_read_api.py::test_v2_list_inventory_items_returns_tenant_scoped_items -q
```

- [ ] **Step 3: 实现 items 查询契约、服务与路由**

```python
class V2InventoryItemData(BaseModel):
    inventory_item_id: str
    tenant_id: str
    sku: str | None
    name: str
    barcode: str | None
    default_unit: str
    status: str
    created_at: datetime
    updated_at: datetime
```

```python
def list_v2_inventory_items(...):
    ...
```

- [ ] **Step 4: 重跑 items 测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_inventory_read_api.py::test_v2_list_inventory_items_returns_tenant_scoped_items -q
```

Expected:

- `1 passed`

### Task 2: 固定 stock 列表接口

**Files:**
- Modify: `backend/tests/test_v2_inventory_read_api.py`
- Modify: `backend/app/contracts/v2/inventory.py`
- Modify: `backend/app/api/v2/routes/inventory.py`
- Modify: `backend/app/services/v2_inventory.py`

- [ ] **Step 1: 先写失败测试，确认 stock 接口只返回当前 shop 的库存投影**

```python
def test_v2_list_inventory_stock_returns_current_shop_snapshots(client, db_session) -> None:
    token, context_token = _seed_v2_inventory_api_context(client, db_session)
    _seed_v2_inventory_shop_and_access(db_session, shop_id="shop_a2", code="a-2", name="Shop A2")
    _commit_inventory_stock_in(
        db_session,
        task_run_id="vtask_stock_a1",
        tenant_id="tenant_a",
        shop_id="shop_a1",
        payload={"item_name": "Cola", "quantity": 2, "unit": "box", "price": 18.5},
    )
    _commit_inventory_stock_in(
        db_session,
        task_run_id="vtask_stock_a2",
        tenant_id="tenant_a",
        shop_id="shop_a2",
        payload={"item_name": "Cola", "quantity": 5, "unit": "box", "price": 19},
    )

    response = client.get(
        "/api/v2/inventory/stock?limit=20",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["count"] == 1
    assert payload["items"][0]["shop_id"] == "shop_a1"
    assert payload["items"][0]["item_name"] == "Cola"
```

- [ ] **Step 2: 运行 stock 测试，确认因为查询逻辑缺失而失败**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_inventory_read_api.py::test_v2_list_inventory_stock_returns_current_shop_snapshots -q
```

- [ ] **Step 3: 实现 stock 查询数据模型与服务**

```python
class V2InventoryStockData(BaseModel):
    snapshot_id: str
    tenant_id: str
    shop_id: str
    inventory_item_id: str
    item_name: str
    default_unit: str
    current_quantity: Decimal
    current_price: Decimal | None
    low_stock_threshold: Decimal | None
    updated_at: datetime
```

```python
def list_v2_inventory_stock(...):
    # join snapshot + item，按 updated_at desc 排序
```

- [ ] **Step 4: 重跑 stock 测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_inventory_read_api.py::test_v2_list_inventory_stock_returns_current_shop_snapshots -q
```

Expected:

- `1 passed`

### Task 3: 固定 events 列表接口

**Files:**
- Modify: `backend/tests/test_v2_inventory_read_api.py`
- Modify: `backend/app/contracts/v2/inventory.py`
- Modify: `backend/app/api/v2/routes/inventory.py`
- Modify: `backend/app/services/v2_inventory.py`

- [ ] **Step 1: 先写失败测试，确认 events 接口返回当前 shop 最新事件**

```python
def test_v2_list_inventory_events_returns_current_shop_events_newest_first(client, db_session) -> None:
    token, context_token = _seed_v2_inventory_api_context(client, db_session)
    _commit_inventory_stock_in(
        db_session,
        task_run_id="vtask_events_1",
        tenant_id="tenant_a",
        shop_id="shop_a1",
        payload={"item_name": "Cola", "quantity": 2, "unit": "box", "price": 18.5},
    )
    _commit_inventory_stock_in(
        db_session,
        task_run_id="vtask_events_2",
        tenant_id="tenant_a",
        shop_id="shop_a1",
        payload={"item_name": "Orange", "quantity": 1, "unit": "box", "price": 12},
    )

    response = client.get(
        "/api/v2/inventory/events?limit=20",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["count"] == 2
    assert [item["item_name"] for item in payload["events"]] == ["Orange", "Cola"]
```

- [ ] **Step 2: 运行 events 测试，确认因为路由或查询缺失而失败**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_inventory_read_api.py::test_v2_list_inventory_events_returns_current_shop_events_newest_first -q
```

- [ ] **Step 3: 实现 events 查询数据模型与服务**

```python
class V2InventoryLedgerEventData(BaseModel):
    event_id: str
    tenant_id: str
    shop_id: str
    inventory_item_id: str
    item_name: str
    event_type: str
    quantity_delta: Decimal
    quantity_after: Decimal
    unit: str
    price: Decimal | None
    source_type: str
    source_id: str
    reason: str | None
    created_by_account_id: str
    occurred_at: datetime
```

```python
def list_v2_inventory_events(...):
    # join ledger event + item，按 occurred_at desc 排序
```

- [ ] **Step 4: 重跑 events 测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_inventory_read_api.py::test_v2_list_inventory_events_returns_current_shop_events_newest_first -q
```

Expected:

- `1 passed`

### Task 4: 阶段验收

**Files:**
- Verify: `backend/tests/test_v2_inventory_read_api.py`
- Modify: `project_docs/generated/openapi-v1.json`

- [ ] **Step 1: 运行 V2 inventory read API 测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_inventory_read_api.py -q
```

- [ ] **Step 2: 运行关键 V2 回归**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_identity_context.py backend/tests/test_v2_conversation_runtime.py backend/tests/test_v2_clarification_confirmation.py backend/tests/test_v2_inventory_ledger.py backend/tests/test_v2_inventory_read_api.py -q
```

- [ ] **Step 3: 刷新 OpenAPI 快照并校验**

Run:

```powershell
$env:PYTHONPATH="backend"; python backend/scripts/generate_openapi_snapshot.py
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_openapi_contract_snapshot.py -q
```

- [ ] **Step 4: 运行后端全量测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests -q
```

- [ ] **Step 5: 检查 git 状态并提交**

Run:

```powershell
git status --short
git add backend/app/contracts/v2/inventory.py backend/app/api/v2/routes/inventory.py backend/app/api/v2/router.py backend/app/services/v2_inventory.py backend/tests/test_v2_inventory_read_api.py docs/superpowers/plans/2026-04-18-ai-native-saas-v2-inventory-read-apis.md project_docs/generated/openapi-v1.json
git commit -m "feat: add v2 inventory read apis"
```

## 自检

- Spec coverage：本计划只覆盖 `GET /api/v2/inventory/items`、`GET /api/v2/inventory/stock`、`GET /api/v2/inventory/events` 三个最小查询接口。
- Placeholder scan：没有使用 `TBD`、`TODO`、`implement later` 等占位词。
- Type consistency：统一使用 `items / stock / events` 三组列表响应，避免把 tenant 级商品与 shop 级 snapshot 混为同一个返回模型。
