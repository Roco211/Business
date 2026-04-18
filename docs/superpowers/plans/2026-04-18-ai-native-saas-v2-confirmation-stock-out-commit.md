# AI 原生 SaaS V2 确认通过后出库落账实现计划
> **给智能执行代理（agentic workers）：** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务逐项实现本计划。步骤使用 checkbox（`- [ ]`）语法跟踪。

**Goal:** 让 `POST /api/v2/confirmations/{confirmation_id}/approve` 在 `inventory.stock_out` 场景下调用 V2 确定性库存出库工具，原子完成确认批准、库存账本追加与 `task_run.status -> committed`。

**Architecture:** 本阶段沿用已有 V2 `confirm -> commit` 主链，只新增 `inventory.stock_out` 分支。库存服务拆成“内部落账（不提交事务）”和“直接 API 提交（自行 commit）”两层：`commit_v2_inventory_stock_out()` 只负责在当前事务内更新 snapshot 并追加 `stock_out` ledger event，`submit_v2_inventory_stock_out()` 继续作为 `/api/v2/inventory/stock-out` 的直接提交入口；`approve_v2_confirmation()` 则在同一事务里编排 confirmation 批准、库存落账和 task committed。

**Tech Stack:** Python、FastAPI、SQLAlchemy、pytest

---

## 文件结构

- 修改 `backend/tests/test_v2_clarification_confirmation.py`：新增 stock-out approval 成功与失败回滚测试。
- 修改 `backend/app/services/v2_inventory.py`：新增 `commit_v2_inventory_stock_out()`，让 `submit_v2_inventory_stock_out()` 复用它并保留直接 API 语义。
- 修改 `backend/app/services/v2_conversation.py`：在 approval 入口编排 `inventory.stock_out` 的库存落账。
- 修改 `backend/app/api/v2/routes/conversation.py`：把库存服务的 not found / conflict / validation 错误映射到 404 / 409 / 422，避免 approval 路径暴露 500。

### Task 1: 固定 stock-out confirmation approval 的验收行为

**Files:**
- Modify: `backend/tests/test_v2_clarification_confirmation.py`

- [ ] **Step 1: 先写失败测试，确认批准 `inventory.stock_out` 后会真正写入出库事件并把任务推进到 committed**

```python
def test_v2_approve_stock_out_confirmation_commits_inventory_and_marks_task_committed(client, db_session) -> None:
    from app.models import V2InventoryLedgerEvent, V2InventoryStockSnapshot, V2TaskRun
    from app.services.v2_conversation import create_v2_confirmation
    from app.services.v2_inventory import commit_v2_inventory_stock_in

    token, context_token, task_run_id = _create_api_task_run(client, db_session)
    seed_task_run_id = "vtask_seed_stock_out_confirm"
    _seed_v2_task_run(db_session, task_run_id=seed_task_run_id)
    seeded = commit_v2_inventory_stock_in(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        task_run_id=seed_task_run_id,
        created_by_account_id="acct_001",
        payload={"item_name": "Cola", "quantity": 5, "unit": "box", "price": 18.5},
    )
    db_session.commit()

    confirmation = create_v2_confirmation(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        task_run_id=task_run_id,
        confirmation_type="inventory.stock_out",
        draft_payload={
            "inventory_item_id": seeded.item.inventory_item_id,
            "expected_quantity": 5,
            "stock_out_quantity": 2,
            "reason": "counter sale",
        },
    )

    response = client.post(
        f"/api/v2/confirmations/{confirmation.confirmation_id}/approve",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={
            "resolution_payload": {
                "fields": {
                    "inventory_item_id": seeded.item.inventory_item_id,
                    "expected_quantity": 5,
                    "stock_out_quantity": 2,
                    "reason": "counter sale",
                }
            }
        },
    )

    db_session.expire_all()
    task_run = db_session.get(V2TaskRun, task_run_id)
    snapshot = db_session.query(V2InventoryStockSnapshot).filter_by(
        inventory_item_id=seeded.item.inventory_item_id,
        shop_id="shop_a1",
    ).one()
    event = db_session.query(V2InventoryLedgerEvent).filter_by(
        inventory_item_id=seeded.item.inventory_item_id,
        event_type="stock_out",
    ).order_by(V2InventoryLedgerEvent.occurred_at.desc()).first()

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "approved"
    assert task_run is not None
    assert task_run.status == "committed"
    assert snapshot.current_quantity == 3
    assert event is not None
    assert event.quantity_after == 3
```

- [ ] **Step 2: 再写失败测试，确认库存不足时 approval 返回 422，且 confirmation 与 task_run 一起回滚**

```python
def test_v2_approve_stock_out_confirmation_rejects_insufficient_stock_and_rolls_back(client, db_session) -> None:
    from app.models import V2Confirmation, V2TaskRun
    from app.services.v2_conversation import create_v2_confirmation
    from app.services.v2_inventory import commit_v2_inventory_stock_in

    token, context_token, task_run_id = _create_api_task_run(client, db_session)
    seed_task_run_id = "vtask_seed_stock_out_insufficient"
    _seed_v2_task_run(db_session, task_run_id=seed_task_run_id)
    seeded = commit_v2_inventory_stock_in(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        task_run_id=seed_task_run_id,
        created_by_account_id="acct_001",
        payload={"item_name": "Cola", "quantity": 1, "unit": "box", "price": 18.5},
    )
    db_session.commit()

    confirmation = create_v2_confirmation(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        task_run_id=task_run_id,
        confirmation_type="inventory.stock_out",
        draft_payload={
            "inventory_item_id": seeded.item.inventory_item_id,
            "expected_quantity": 1,
            "stock_out_quantity": 2,
            "reason": "counter sale",
        },
    )

    response = client.post(
        f"/api/v2/confirmations/{confirmation.confirmation_id}/approve",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={
            "resolution_payload": {
                "fields": {
                    "inventory_item_id": seeded.item.inventory_item_id,
                    "expected_quantity": 1,
                    "stock_out_quantity": 2,
                    "reason": "counter sale",
                }
            }
        },
    )

    db_session.expire_all()
    persisted_confirmation = db_session.get(V2Confirmation, confirmation.confirmation_id)
    persisted_task_run = db_session.get(V2TaskRun, task_run_id)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert persisted_confirmation is not None
    assert persisted_confirmation.status == "pending"
    assert persisted_confirmation.approved_by_account_id is None
    assert persisted_task_run is not None
    assert persisted_task_run.status == "awaiting_confirmation"
```

- [ ] **Step 3: 运行新增测试，确认因 approval 还没有 stock-out 分支而失败**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_clarification_confirmation.py::test_v2_approve_stock_out_confirmation_commits_inventory_and_marks_task_committed backend/tests/test_v2_clarification_confirmation.py::test_v2_approve_stock_out_confirmation_rejects_insufficient_stock_and_rolls_back -q
```

### Task 2: 实现 stock-out confirmation 的原子编排

**Files:**
- Modify: `backend/app/services/v2_inventory.py`
- Modify: `backend/app/services/v2_conversation.py`
- Modify: `backend/app/api/v2/routes/conversation.py`

- [ ] **Step 1: 抽出不自动提交事务的 `commit_v2_inventory_stock_out()`，让 API 与 confirmation 复用同一套落账逻辑**

```python
def commit_v2_inventory_stock_out(
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
    ...
    db_session.add(event)
    db_session.flush()
    return V2InventoryStockOutResult(snapshot=snapshot, event=event)


def submit_v2_inventory_stock_out(...):
    try:
        result = commit_v2_inventory_stock_out(...)
        db_session.commit()
        return result
    except Exception:
        db_session.rollback()
        raise
```

- [ ] **Step 2: 在 `approve_v2_confirmation()` 中增加 `inventory.stock_out` 分支，并把成功结果推进到 committed**

```python
if confirmation.confirmation_type == "inventory.stock_in":
    ...
    task_run.status = COMMITTED_STATUS
    task_run.result_summary = "Confirmation approved and inventory committed."
    task_run.completed_at = now
elif confirmation.confirmation_type == "inventory.stock_out":
    resolved_fields = dict(resolution_payload.get("fields") or {})
    commit_v2_inventory_stock_out(
        db_session,
        tenant_id=tenant_id,
        shop_id=shop_id,
        inventory_item_id=str(resolved_fields["inventory_item_id"]),
        expected_quantity=resolved_fields["expected_quantity"],
        stock_out_quantity=resolved_fields["stock_out_quantity"],
        reason=str(resolved_fields["reason"]),
        created_by_account_id=approved_by_account_id,
    )
    task_run.status = COMMITTED_STATUS
    task_run.result_summary = "Confirmation approved and inventory committed."
    task_run.completed_at = now
else:
    ...
```

- [ ] **Step 3: 在 approval 路由映射库存错误，避免 stock-out confirmation 失败时返回 500**

```python
except (V2InventoryItemNotFoundError, V2InventoryStockOutItemNotFoundError):
    return JSONResponse(
        status_code=404,
        content=V2ErrorEnvelope(
            error=V2ErrorBody(code="inventory_item_not_found", message="Inventory item not found")
        ).model_dump(),
    )
except (V2InventoryUnitMismatchError, V2InventoryPayloadValidationError, V2InventoryStockOutValidationError) as exc:
    return JSONResponse(
        status_code=422,
        content=V2ErrorEnvelope(
            error=V2ErrorBody(code="validation_error", message=str(exc))
        ).model_dump(),
    )
except V2InventoryStockOutConflictError:
    return JSONResponse(
        status_code=409,
        content=V2ErrorEnvelope(
            error=V2ErrorBody(code="inventory_conflict", message="Inventory stock-out conflicts with current stock")
        ).model_dump(),
    )
```

- [ ] **Step 4: 重跑新增 approval 测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_clarification_confirmation.py::test_v2_approve_stock_out_confirmation_commits_inventory_and_marks_task_committed backend/tests/test_v2_clarification_confirmation.py::test_v2_approve_stock_out_confirmation_rejects_insufficient_stock_and_rolls_back -q
```

Expected:

- `2 passed`

### Task 3: 阶段验收

**Files:**
- Verify: `backend/tests/test_v2_clarification_confirmation.py`
- Verify: `backend/tests/test_v2_inventory_stock_out_api.py`
- Verify: `backend/tests/test_v2_inventory_ledger.py`

- [ ] **Step 1: 运行 clarification / confirmation 全测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_clarification_confirmation.py -q
```

- [ ] **Step 2: 运行 stock-out API 测试，确认 direct API 仍然保持 green**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_inventory_stock_out_api.py -q
```

- [ ] **Step 3: 运行关键 inventory / runtime V2 回归**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_identity_context.py backend/tests/test_v2_conversation_runtime.py backend/tests/test_v2_clarification_confirmation.py backend/tests/test_v2_inventory_ledger.py backend/tests/test_v2_inventory_read_api.py backend/tests/test_v2_inventory_corrections_api.py backend/tests/test_v2_inventory_stock_out_api.py -q
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
git add backend/app/services/v2_inventory.py backend/app/services/v2_conversation.py backend/app/api/v2/routes/conversation.py backend/tests/test_v2_clarification_confirmation.py docs/superpowers/plans/2026-04-18-ai-native-saas-v2-confirmation-stock-out-commit.md
git commit -m "feat: commit v2 stock-out confirmations"
```

## 自检

- Spec coverage：本计划补上 V2 runtime 的 `inventory.stock_out.commit` 主链，不扩展到新的 confirmation 创建策略、audit、outbox 或 realtime projection。
- Placeholder scan：没有保留 `TBD`、`TODO`、`implement later` 一类占位。
- Type consistency：统一使用 `inventory.stock_out`、`stock_out_quantity`、`expected_quantity`、`inventory_item_id` 与 `commit_v2_inventory_stock_out()` 这组命名，和已落地的 direct stock-out API 保持一致。
- Architecture check：库存变更仍通过 ledger event 追加事实完成，approval 只是编排确定性工具，符合“AI 不能直接修改业务真相”和“确认通过后才落账”的边界。
