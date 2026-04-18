# AI 原生 SaaS V2 库存纠错接口实现计划
> **给智能执行代理（agentic workers）：** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务逐项实现本计划。步骤使用 checkbox（`- [ ]`）语法跟踪。

**Goal:** 为 `/api/v2` 补齐 `POST /api/v2/inventory/corrections`，支持在显式租户（tenant）/门店（shop）上下文下提交库存纠错，并以 ledger event 追加修正 shop 级库存投影。

**Architecture:** 本阶段只实现纠错写接口，不引入 audit、outbox 或 message projection。纠错服务在 `v2_inventory.py` 中直接对 `V2InventoryStockSnapshot` 做并发前置校验，然后追加 `event_type="correction"` 的 `V2InventoryLedgerEvent` 并更新当前 snapshot；API 层复用现有 `Authorization + X-Context-Token` 执行上下文，将 not found / conflict / validation 分别映射到 404 / 409 / 422。

**Tech Stack:** Python、FastAPI、Pydantic、SQLAlchemy、pytest、OpenAPI snapshot

---

## 文件结构

- 新增 `backend/tests/test_v2_inventory_corrections_api.py`：覆盖 correction 成功、冲突、校验失败、跨 shop 不可见。
- 修改 `backend/app/contracts/v2/inventory.py`：新增 correction 请求与响应模型。
- 修改 `backend/app/services/v2_inventory.py`：新增 V2 correction 服务与错误类型。
- 修改 `backend/app/api/v2/routes/inventory.py`：新增 correction 路由和错误映射。
- 修改 `project_docs/generated/openapi-v1.json`：刷新 OpenAPI 快照。

### Task 1: 固定 correction API 的成功行为

**Files:**
- Create: `backend/tests/test_v2_inventory_corrections_api.py`
- Modify: `backend/app/contracts/v2/inventory.py`
- Modify: `backend/app/services/v2_inventory.py`
- Modify: `backend/app/api/v2/routes/inventory.py`

- [ ] **Step 1: 先写失败测试，确认 correction 会写入 correction ledger event 并更新 snapshot**

```python
def test_v2_submit_inventory_correction_updates_snapshot_and_returns_event_id(client, db_session) -> None:
    token, context_token = _seed_v2_inventory_api_context(client, db_session)
    inventory_item_id = _commit_inventory_stock_in(
        db_session,
        task_run_id="vtask_correction_seed",
        tenant_id="tenant_a",
        shop_id="shop_a1",
        payload={"item_name": "Cola", "quantity": 2, "unit": "box", "price": 18.5},
    )

    response = client.post(
        "/api/v2/inventory/corrections",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={
            "inventory_item_id": inventory_item_id,
            "expected_quantity": 2,
            "corrected_quantity": 6,
            "reason": "physical recount",
        },
    )

    assert response.status_code == 200
    assert response.json()["data"]["inventory_item_id"] == inventory_item_id
    assert response.json()["data"]["new_quantity"] == "6"
    assert response.json()["data"]["correction_event_id"].startswith("vevent_")
```

- [ ] **Step 2: 运行成功测试，确认因为路由或服务缺失而失败**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_inventory_corrections_api.py::test_v2_submit_inventory_correction_updates_snapshot_and_returns_event_id -q
```

- [ ] **Step 3: 新增 correction 请求 / 响应契约与最小服务签名**

```python
class V2SubmitInventoryCorrectionRequest(BaseModel):
    inventory_item_id: str
    expected_quantity: Decimal
    corrected_quantity: Decimal
    reason: str


class V2SubmitInventoryCorrectionData(BaseModel):
    correction_event_id: str
    inventory_item_id: str
    new_quantity: Decimal
```

```python
@dataclass(frozen=True)
class V2InventoryCorrectionResult:
    snapshot: V2InventoryStockSnapshot
    event: V2InventoryLedgerEvent
```

- [ ] **Step 4: 实现 correction 路由与最小服务，让成功测试转绿**

```python
@router.post("/corrections", response_model=V2DataEnvelope[V2SubmitInventoryCorrectionData])
def submit_inventory_correction_v2(...):
    ...
```

```python
def submit_v2_inventory_correction(...):
    # 查找当前 tenant/shop 下 snapshot
    # 校验 expected_quantity
    # 更新 snapshot.current_quantity
    # 追加 correction event
    # commit
```

- [ ] **Step 5: 重跑成功测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_inventory_corrections_api.py::test_v2_submit_inventory_correction_updates_snapshot_and_returns_event_id -q
```

Expected:

- `1 passed`

### Task 2: 固定 conflict / validation / shop 边界

**Files:**
- Modify: `backend/tests/test_v2_inventory_corrections_api.py`
- Modify: `backend/app/services/v2_inventory.py`
- Modify: `backend/app/api/v2/routes/inventory.py`

- [ ] **Step 1: 写失败测试，确认 stale expected quantity 返回 409**

```python
def test_v2_submit_inventory_correction_rejects_stale_expected_quantity(client, db_session) -> None:
    ...
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "inventory_conflict"
```

- [ ] **Step 2: 写失败测试，确认负数 corrected quantity 返回 422**

```python
def test_v2_submit_inventory_correction_rejects_negative_quantity(client, db_session) -> None:
    ...
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
```

- [ ] **Step 3: 写失败测试，确认其他门店的 snapshot 在当前上下文不可见**

```python
def test_v2_submit_inventory_correction_rejects_item_outside_current_shop(client, db_session) -> None:
    ...
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "inventory_item_not_found"
```

- [ ] **Step 4: 运行这三个测试，确认失败原因准确**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_inventory_corrections_api.py::test_v2_submit_inventory_correction_rejects_stale_expected_quantity backend/tests/test_v2_inventory_corrections_api.py::test_v2_submit_inventory_correction_rejects_negative_quantity backend/tests/test_v2_inventory_corrections_api.py::test_v2_submit_inventory_correction_rejects_item_outside_current_shop -q
```

- [ ] **Step 5: 补全 service / route 的错误类型与映射**

```python
class V2InventoryCorrectionValidationError(ValueError):
    pass


class V2InventoryCorrectionConflictError(ValueError):
    pass


class V2InventoryCorrectionItemNotFoundError(LookupError):
    pass
```

- [ ] **Step 6: 重跑三条错误路径测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_inventory_corrections_api.py::test_v2_submit_inventory_correction_rejects_stale_expected_quantity backend/tests/test_v2_inventory_corrections_api.py::test_v2_submit_inventory_correction_rejects_negative_quantity backend/tests/test_v2_inventory_corrections_api.py::test_v2_submit_inventory_correction_rejects_item_outside_current_shop -q
```

Expected:

- `3 passed`

### Task 3: 阶段验收

**Files:**
- Verify: `backend/tests/test_v2_inventory_corrections_api.py`
- Modify: `project_docs/generated/openapi-v1.json`

- [ ] **Step 1: 运行 correction API 测试文件**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_inventory_corrections_api.py -q
```

- [ ] **Step 2: 运行关键 V2 回归**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_identity_context.py backend/tests/test_v2_conversation_runtime.py backend/tests/test_v2_clarification_confirmation.py backend/tests/test_v2_inventory_ledger.py backend/tests/test_v2_inventory_read_api.py backend/tests/test_v2_inventory_corrections_api.py -q
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
git add backend/app/contracts/v2/inventory.py backend/app/services/v2_inventory.py backend/app/api/v2/routes/inventory.py backend/tests/test_v2_inventory_corrections_api.py docs/superpowers/plans/2026-04-18-ai-native-saas-v2-inventory-corrections-api.md project_docs/generated/openapi-v1.json
git commit -m "feat: add v2 inventory corrections api"
```

## 自检

- Spec coverage：本计划只覆盖 `POST /api/v2/inventory/corrections`，不扩展到 stock-out、audit、outbox。
- Placeholder scan：没有保留 `TBD`、`TODO`、`implement later` 一类占位。
- Type consistency：统一使用 `inventory_item_id`、`expected_quantity`、`corrected_quantity`、`correction_event_id` 这组命名，避免与旧 v1 `item_id` 语义混淆。
