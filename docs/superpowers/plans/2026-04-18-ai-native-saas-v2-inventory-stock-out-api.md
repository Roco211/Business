# AI 原生 SaaS V2 库存出库接口实现计划
> **给智能执行代理（agentic workers）：** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务逐项实现本计划。步骤使用 checkbox（`- [ ]`）语法跟踪。

**Goal:** 为 `/api/v2` 补齐 `POST /api/v2/inventory/stock-out`，支持在显式租户（tenant）/门店（shop）上下文下提交确定性库存出库，并以账本事件（ledger event）追加 `stock_out` 事实。

**Architecture:** 本阶段只实现直接出库工具接口，不引入 audit、outbox 或 runtime draft。API 层复用现有 `Authorization + X-Context-Token` 执行上下文；服务层只在当前 `tenant_id + shop_id` 下读取 `V2InventoryStockSnapshot`，先校验 `expected_quantity` 防止基于过期投影出库，再追加 `event_type="stock_out"` 的 `V2InventoryLedgerEvent` 并更新当前库存投影。

**Tech Stack:** Python、FastAPI、Pydantic、SQLAlchemy、pytest、OpenAPI snapshot

---

## 文件结构

- 新增 `backend/tests/test_v2_inventory_stock_out_api.py`：覆盖出库成功、过期库存冲突、数量校验失败、跨门店不可见。
- 修改 `backend/app/contracts/v2/inventory.py`：新增出库请求与响应模型。
- 修改 `backend/app/services/v2_inventory.py`：新增 V2 出库服务、结果类型与错误类型。
- 修改 `backend/app/api/v2/routes/inventory.py`：新增 `/stock-out` 路由与错误映射。
- 修改 `project_docs/generated/openapi-v1.json`：刷新 OpenAPI 快照。

### Task 1: 固定出库成功行为

**Files:**
- Create: `backend/tests/test_v2_inventory_stock_out_api.py`
- Modify: `backend/app/contracts/v2/inventory.py`
- Modify: `backend/app/services/v2_inventory.py`
- Modify: `backend/app/api/v2/routes/inventory.py`

- [x] **Step 1: 先写失败测试，确认出库会更新 snapshot 并追加 `stock_out` 账本事件**

```python
from decimal import Decimal

from tests.test_v2_inventory_corrections_api import (
    _commit_inventory_stock_in,
    _seed_v2_inventory_api_context,
    _seed_v2_shop,
)


def test_v2_submit_inventory_stock_out_updates_snapshot_and_writes_event(client, db_session) -> None:
    from app.models import V2InventoryLedgerEvent, V2InventoryStockSnapshot

    token, context_token = _seed_v2_inventory_api_context(client, db_session)
    inventory_item_id = _commit_inventory_stock_in(
        db_session,
        task_run_id="vtask_stock_out_seed",
        tenant_id="tenant_a",
        shop_id="shop_a1",
        payload={"item_name": "Cola", "quantity": 5, "unit": "box", "price": 18.5},
    )

    response = client.post(
        "/api/v2/inventory/stock-out",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={
            "inventory_item_id": inventory_item_id,
            "expected_quantity": 5,
            "stock_out_quantity": 2,
            "reason": "counter sale",
        },
    )

    db_session.expire_all()
    snapshot = db_session.query(V2InventoryStockSnapshot).filter_by(
        inventory_item_id=inventory_item_id,
        shop_id="shop_a1",
    ).one()
    event = db_session.query(V2InventoryLedgerEvent).filter_by(
        inventory_item_id=inventory_item_id,
        event_type="stock_out",
    ).one()

    assert response.status_code == 200
    assert response.json()["data"]["inventory_item_id"] == inventory_item_id
    assert response.json()["data"]["new_quantity"] == "3"
    assert response.json()["data"]["stock_out_event_id"].startswith("vevent_")
    assert snapshot.current_quantity == Decimal("3")
    assert event.quantity_delta == Decimal("-2")
    assert event.quantity_after == Decimal("3")
    assert event.reason == "counter sale"
```

- [x] **Step 2: 运行成功测试，确认因为路由或服务缺失而失败**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_inventory_stock_out_api.py::test_v2_submit_inventory_stock_out_updates_snapshot_and_writes_event -q
```

Expected:

- 测试失败，接口当前应返回 `404 Not Found`，因为 `/api/v2/inventory/stock-out` 尚未实现。

- [x] **Step 3: 新增出库请求 / 响应契约**

在 `backend/app/contracts/v2/inventory.py` 中追加：

```python
class V2SubmitInventoryStockOutRequest(BaseModel):
    inventory_item_id: str
    expected_quantity: Decimal
    stock_out_quantity: Decimal
    reason: str


class V2SubmitInventoryStockOutData(BaseModel):
    stock_out_event_id: str
    inventory_item_id: str
    new_quantity: Decimal
```

- [x] **Step 4: 新增出库服务结果与错误类型**

在 `backend/app/services/v2_inventory.py` 中追加：

```python
class V2InventoryStockOutValidationError(ValueError):
    pass


class V2InventoryStockOutConflictError(ValueError):
    pass


class V2InventoryStockOutItemNotFoundError(LookupError):
    pass


@dataclass(frozen=True)
class V2InventoryStockOutResult:
    snapshot: V2InventoryStockSnapshot
    event: V2InventoryLedgerEvent
```

- [x] **Step 5: 实现最小出库服务**

在 `backend/app/services/v2_inventory.py` 中追加：

```python
def submit_v2_inventory_stock_out(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    inventory_item_id: str,
    expected_quantity: Decimal,
    stock_out_quantity: Decimal,
    reason: str,
    created_by_account_id: str,
) -> V2InventoryStockOutResult:
    normalized_reason = reason.strip()
    if not normalized_reason:
        raise V2InventoryStockOutValidationError("reason is required")
    normalized_expected_quantity = Decimal(expected_quantity)
    normalized_stock_out_quantity = Decimal(stock_out_quantity)
    if normalized_stock_out_quantity <= 0:
        raise V2InventoryStockOutValidationError("stock_out_quantity must be > 0")

    try:
        snapshot = _require_v2_inventory_snapshot(
            db_session,
            tenant_id=tenant_id,
            shop_id=shop_id,
            inventory_item_id=inventory_item_id,
        )
    except V2InventoryCorrectionItemNotFoundError as exc:
        raise V2InventoryStockOutItemNotFoundError(inventory_item_id) from exc

    item = db_session.scalar(
        select(V2InventoryItem).where(
            V2InventoryItem.inventory_item_id == inventory_item_id,
            V2InventoryItem.tenant_id == tenant_id,
        )
    )
    if item is None:
        raise V2InventoryStockOutItemNotFoundError(inventory_item_id)

    current_quantity = Decimal(snapshot.current_quantity)
    if current_quantity != normalized_expected_quantity:
        raise V2InventoryStockOutConflictError("inventory changed since the snapshot was read")
    if normalized_stock_out_quantity > current_quantity:
        raise V2InventoryStockOutValidationError("stock_out_quantity exceeds the current stock")

    now = utc_now_naive()
    quantity_after = current_quantity - normalized_stock_out_quantity
    snapshot.current_quantity = quantity_after
    snapshot.updated_at = now
    item.updated_at = now
    event = V2InventoryLedgerEvent(
        event_id=f"vevent_{uuid.uuid4().hex}"[:40],
        tenant_id=tenant_id,
        shop_id=shop_id,
        inventory_item_id=inventory_item_id,
        event_type="stock_out",
        quantity_delta=-normalized_stock_out_quantity,
        quantity_after=quantity_after,
        unit=item.default_unit,
        price=snapshot.current_price,
        source_type="inventory_stock_out",
        source_id=inventory_item_id,
        reason=normalized_reason,
        created_by_account_id=created_by_account_id,
        occurred_at=now,
    )
    db_session.add(event)
    db_session.commit()
    return V2InventoryStockOutResult(snapshot=snapshot, event=event)
```

- [x] **Step 6: 实现出库路由与成功响应**

在 `backend/app/api/v2/routes/inventory.py` 中新增 imports：

```python
V2SubmitInventoryStockOutData,
V2SubmitInventoryStockOutRequest,
```

```python
V2InventoryStockOutConflictError,
V2InventoryStockOutItemNotFoundError,
V2InventoryStockOutValidationError,
submit_v2_inventory_stock_out,
```

追加路由：

```python
@router.post("/stock-out", response_model=V2DataEnvelope[V2SubmitInventoryStockOutData])
def submit_inventory_stock_out_v2(
    payload: V2SubmitInventoryStockOutRequest,
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    db_session: Session = Depends(get_db_session),
) -> V2DataEnvelope[V2SubmitInventoryStockOutData] | JSONResponse:
    if account.account_id != context.account_id:
        return _context_account_mismatch()

    try:
        result = submit_v2_inventory_stock_out(
            db_session,
            tenant_id=context.tenant_id,
            shop_id=context.shop_id,
            inventory_item_id=payload.inventory_item_id,
            expected_quantity=payload.expected_quantity,
            stock_out_quantity=payload.stock_out_quantity,
            reason=payload.reason,
            created_by_account_id=account.account_id,
        )
    except V2InventoryStockOutItemNotFoundError:
        return JSONResponse(
            status_code=404,
            content=V2ErrorEnvelope(
                error=V2ErrorBody(code="inventory_item_not_found", message="Inventory item not found")
            ).model_dump(),
        )
    except V2InventoryStockOutConflictError:
        return JSONResponse(
            status_code=409,
            content=V2ErrorEnvelope(
                error=V2ErrorBody(code="inventory_conflict", message="Inventory stock-out conflicts with current stock")
            ).model_dump(),
        )
    except V2InventoryStockOutValidationError as exc:
        return JSONResponse(
            status_code=422,
            content=V2ErrorEnvelope(
                error=V2ErrorBody(code="validation_error", message=str(exc))
            ).model_dump(),
        )

    return V2DataEnvelope(
        data=V2SubmitInventoryStockOutData(
            stock_out_event_id=result.event.event_id,
            inventory_item_id=result.event.inventory_item_id,
            new_quantity=result.snapshot.current_quantity,
        )
    )
```

- [x] **Step 7: 重跑成功测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_inventory_stock_out_api.py::test_v2_submit_inventory_stock_out_updates_snapshot_and_writes_event -q
```

Expected:

- `1 passed`

### Task 2: 固定冲突、校验和门店边界

**Files:**
- Modify: `backend/tests/test_v2_inventory_stock_out_api.py`
- Modify: `backend/app/services/v2_inventory.py`
- Modify: `backend/app/api/v2/routes/inventory.py`

- [x] **Step 1: 写失败测试，确认过期 `expected_quantity` 返回 409**

```python
def test_v2_submit_inventory_stock_out_rejects_stale_expected_quantity(client, db_session) -> None:
    token, context_token = _seed_v2_inventory_api_context(client, db_session)
    inventory_item_id = _commit_inventory_stock_in(
        db_session,
        task_run_id="vtask_stock_out_stale",
        tenant_id="tenant_a",
        shop_id="shop_a1",
        payload={"item_name": "Cola", "quantity": 5, "unit": "box", "price": 18.5},
    )

    response = client.post(
        "/api/v2/inventory/stock-out",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={
            "inventory_item_id": inventory_item_id,
            "expected_quantity": 4,
            "stock_out_quantity": 2,
            "reason": "counter sale",
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "inventory_conflict"
```

- [x] **Step 2: 写失败测试，确认出库数量超过当前库存返回 422**

```python
def test_v2_submit_inventory_stock_out_rejects_excessive_quantity(client, db_session) -> None:
    token, context_token = _seed_v2_inventory_api_context(client, db_session)
    inventory_item_id = _commit_inventory_stock_in(
        db_session,
        task_run_id="vtask_stock_out_excessive",
        tenant_id="tenant_a",
        shop_id="shop_a1",
        payload={"item_name": "Cola", "quantity": 5, "unit": "box", "price": 18.5},
    )

    response = client.post(
        "/api/v2/inventory/stock-out",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={
            "inventory_item_id": inventory_item_id,
            "expected_quantity": 5,
            "stock_out_quantity": 6,
            "reason": "counter sale",
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
```

- [x] **Step 3: 写失败测试，确认非正数出库数量返回 422**

```python
def test_v2_submit_inventory_stock_out_rejects_non_positive_quantity(client, db_session) -> None:
    token, context_token = _seed_v2_inventory_api_context(client, db_session)
    inventory_item_id = _commit_inventory_stock_in(
        db_session,
        task_run_id="vtask_stock_out_non_positive",
        tenant_id="tenant_a",
        shop_id="shop_a1",
        payload={"item_name": "Cola", "quantity": 5, "unit": "box", "price": 18.5},
    )

    response = client.post(
        "/api/v2/inventory/stock-out",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={
            "inventory_item_id": inventory_item_id,
            "expected_quantity": 5,
            "stock_out_quantity": 0,
            "reason": "counter sale",
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
```

- [x] **Step 4: 写失败测试，确认其他门店的 snapshot 在当前上下文不可见**

```python
def test_v2_submit_inventory_stock_out_rejects_item_outside_current_shop(client, db_session) -> None:
    token, context_token = _seed_v2_inventory_api_context(client, db_session)
    _seed_v2_shop(db_session, shop_id="shop_a2", code="a-2", name="Shop A2")
    inventory_item_id = _commit_inventory_stock_in(
        db_session,
        task_run_id="vtask_stock_out_other_shop",
        tenant_id="tenant_a",
        shop_id="shop_a2",
        payload={"item_name": "Grape", "quantity": 4, "unit": "box", "price": 15},
    )

    response = client.post(
        "/api/v2/inventory/stock-out",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={
            "inventory_item_id": inventory_item_id,
            "expected_quantity": 4,
            "stock_out_quantity": 1,
            "reason": "counter sale",
        },
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "inventory_item_not_found"
```

- [x] **Step 5: 运行四条错误路径测试，确认失败原因准确**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_inventory_stock_out_api.py::test_v2_submit_inventory_stock_out_rejects_stale_expected_quantity backend/tests/test_v2_inventory_stock_out_api.py::test_v2_submit_inventory_stock_out_rejects_excessive_quantity backend/tests/test_v2_inventory_stock_out_api.py::test_v2_submit_inventory_stock_out_rejects_non_positive_quantity backend/tests/test_v2_inventory_stock_out_api.py::test_v2_submit_inventory_stock_out_rejects_item_outside_current_shop -q
```

Expected:

- 在实现路由前失败；在 Task 1 的服务和路由补齐后应全部通过。

- [x] **Step 6: 重跑出库 API 测试文件**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_inventory_stock_out_api.py -q
```

Expected:

- `5 passed`

### Task 3: 阶段验收与提交

**Files:**
- Verify: `backend/tests/test_v2_inventory_stock_out_api.py`
- Modify: `project_docs/generated/openapi-v1.json`

- [x] **Step 1: 运行库存相关 V2 回归**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_inventory_ledger.py backend/tests/test_v2_inventory_read_api.py backend/tests/test_v2_inventory_corrections_api.py backend/tests/test_v2_inventory_stock_out_api.py -q
```

Expected:

- 全部通过。

- [x] **Step 2: 运行关键 V2 回归**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_identity_context.py backend/tests/test_v2_conversation_runtime.py backend/tests/test_v2_clarification_confirmation.py backend/tests/test_v2_inventory_ledger.py backend/tests/test_v2_inventory_read_api.py backend/tests/test_v2_inventory_corrections_api.py backend/tests/test_v2_inventory_stock_out_api.py -q
```

Expected:

- 全部通过。

- [x] **Step 3: 刷新 OpenAPI 快照并校验**

Run:

```powershell
$env:PYTHONPATH="backend"; python backend/scripts/generate_openapi_snapshot.py
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_openapi_contract_snapshot.py -q
```

Expected:

- OpenAPI snapshot 测试通过；如果 snapshot 有差异，确认只来自新增 `/api/v2/inventory/stock-out`。

- [x] **Step 4: 运行后端全量测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests -q
```

Expected:

- 全量测试通过。

- [x] **Step 5: 检查 git 状态并提交**

Run:

```powershell
git status --short
git add backend/app/contracts/v2/inventory.py backend/app/services/v2_inventory.py backend/app/api/v2/routes/inventory.py backend/tests/test_v2_inventory_stock_out_api.py docs/superpowers/plans/2026-04-18-ai-native-saas-v2-inventory-stock-out-api.md project_docs/generated/openapi-v1.json
git commit -m "feat: add v2 inventory stock-out api"
```

## 自检

- Spec coverage：本计划覆盖阶段 4（Inventory Ledger V2）中的 `inventory.stock_out.commit` 直接工具接口，不扩展到 AI draft、confirmation、audit 或 outbox。
- Placeholder scan：没有保留 `TBD`、`TODO`、`implement later` 一类占位。
- Type consistency：统一使用 `inventory_item_id`、`expected_quantity`、`stock_out_quantity`、`stock_out_event_id`、`new_quantity`，与 correction API 的命名方式保持一致。
- Architecture check：所有读写都通过 `tenant_id + shop_id` 执行上下文限定，出库通过追加 `stock_out` 事件表达业务事实，符合“AI 不能直接修改业务真相”和“关键业务事实事件化”的原则。
