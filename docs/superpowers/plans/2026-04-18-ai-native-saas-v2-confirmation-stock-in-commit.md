# AI 原生 SaaS V2 确认通过后入库落账实现计划
> **给智能执行代理（agentic workers）：** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务逐项实现本计划。步骤使用 checkbox（`- [ ]`）语法跟踪。

**Goal:** 让 `POST /api/v2/confirmations/{confirmation_id}/approve` 在 `inventory.stock_in` 场景下调用 V2 确定性库存提交工具，原子完成确认批准、库存真相落账与 `task_run.status -> committed`。

**Architecture:** 本阶段把 V2 runtime 的 `confirm -> commit` 主链真正接上，但只覆盖 `inventory.stock_in`。`approve_v2_confirmation()` 负责在单事务内编排确认批准与库存落账；`commit_v2_inventory_stock_in()` 不再自行提交事务，而是返回已 flush 的真相对象供 runtime 统一提交，这样一旦库存提交失败，confirmation 与 task_run 会一起回滚。

**Tech Stack:** Python、FastAPI、SQLAlchemy、pytest、Alembic、SQLite 测试数据库、MySQL 生产目标

---

## 文件结构

- 修改 `backend/tests/test_v2_clarification_confirmation.py`：增加 approval -> commit 的 API 验收测试与失败回滚测试。
- 修改 `backend/app/services/v2_conversation.py`：在 approval 入口编排 inventory commit，并引入 `committed` 状态。
- 修改 `backend/app/services/v2_inventory.py`：移除内部 `commit()`，改为由上层事务统一提交。

### Task 1: 固定 approval -> commit 的验收行为

**Files:**
- Modify: `backend/tests/test_v2_clarification_confirmation.py`

- [ ] **Step 1: 先写失败测试，确认批准后真正写入库存真相并把任务推进到 committed**

```python
def test_v2_approve_confirmation_commits_inventory_and_marks_task_committed(client, db_session) -> None:
    from app.models import V2InventoryItem, V2InventoryLedgerEvent, V2InventoryStockSnapshot, V2TaskRun
    from app.services.v2_conversation import create_v2_confirmation

    token, context_token, task_run_id = _create_api_task_run(client, db_session)
    confirmation = create_v2_confirmation(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        task_run_id=task_run_id,
        confirmation_type="inventory.stock_in",
        draft_payload={"item_name": "Cola", "quantity": 2, "unit": "box", "price": 18.5},
    )

    response = client.post(
        f"/api/v2/confirmations/{confirmation.confirmation_id}/approve",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={"resolution_payload": {"fields": {"item_name": "Cola", "quantity": 2, "unit": "box", "price": 18.5}}},
    )

    db_session.expire_all()
    task_run = db_session.get(V2TaskRun, task_run_id)
    items = db_session.query(V2InventoryItem).all()
    snapshots = db_session.query(V2InventoryStockSnapshot).all()
    events = db_session.query(V2InventoryLedgerEvent).all()

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "approved"
    assert task_run is not None
    assert task_run.status == "committed"
    assert len(items) == 1
    assert snapshots[0].current_quantity == 2
    assert events[0].quantity_after == 2
```

- [ ] **Step 2: 再写失败测试，确认库存提交失败时 confirmation 与 task_run 会一起回滚**

```python
def test_v2_approve_confirmation_rolls_back_when_inventory_commit_fails(db_session, monkeypatch) -> None:
    import pytest

    from app.models import V2TaskRun
    from app.services import v2_conversation as conversation_service
    from app.services.v2_conversation import approve_v2_confirmation, create_v2_confirmation

    _seed_v2_task_run(db_session, task_run_id="vtask_v2_approve_rollback")
    confirmation = create_v2_confirmation(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        task_run_id="vtask_v2_approve_rollback",
        confirmation_type="inventory.stock_in",
        draft_payload={"item_name": "Cola", "quantity": 2, "unit": "box", "price": 18.5},
    )

    def blow_up(*args, **kwargs):
        raise RuntimeError("inventory commit failed")

    monkeypatch.setattr(conversation_service, "commit_v2_inventory_stock_in", blow_up)

    with pytest.raises(RuntimeError, match="inventory commit failed"):
        approve_v2_confirmation(
            db_session,
            tenant_id="tenant_a",
            shop_id="shop_a1",
            confirmation_id=confirmation.confirmation_id,
            resolution_payload={"fields": {"item_name": "Cola", "quantity": 2, "unit": "box", "price": 18.5}},
            approved_by_account_id="acct_001",
        )

    db_session.expire_all()
    persisted_task_run = db_session.get(V2TaskRun, "vtask_v2_approve_rollback")
    persisted_confirmation = db_session.get(type(confirmation), confirmation.confirmation_id)
    assert persisted_confirmation is not None
    assert persisted_confirmation.status == "pending"
    assert persisted_task_run is not None
    assert persisted_task_run.status == "awaiting_confirmation"
```

- [ ] **Step 3: 运行新增测试，确认因 approval 仍停留在 executing / 无回滚编排而失败**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_clarification_confirmation.py::test_v2_approve_confirmation_commits_inventory_and_marks_task_committed backend/tests/test_v2_clarification_confirmation.py::test_v2_approve_confirmation_rolls_back_when_inventory_commit_fails -q
```

### Task 2: 实现 approval -> commit 的原子编排

**Files:**
- Modify: `backend/app/services/v2_conversation.py`
- Modify: `backend/app/services/v2_inventory.py`

- [ ] **Step 1: 让 `commit_v2_inventory_stock_in()` 改为只 flush，不自行 commit**

```python
def commit_v2_inventory_stock_in(...):
    ...
    db_session.add(event)
    db_session.flush()
    return V2CommittedStockInResult(...)
```

- [ ] **Step 2: 在 `v2_conversation.py` 引入 `COMMITTED_STATUS` 与 inventory commit 编排**

```python
COMMITTED_STATUS = "committed"


def _approve_inventory_stock_in_confirmation(...):
    fields = dict(resolution_payload.get("fields") or {})
    commit_v2_inventory_stock_in(
        db_session,
        tenant_id=tenant_id,
        shop_id=shop_id,
        task_run_id=task_run.task_run_id,
        created_by_account_id=approved_by_account_id,
        payload=fields,
    )
```

- [ ] **Step 3: 在 `approve_v2_confirmation()` 中用单事务包住确认批准和库存落账**

```python
def approve_v2_confirmation(...):
    try:
        ...
        confirmation.status = APPROVED_STATUS
        ...
        if confirmation.confirmation_type == "inventory.stock_in":
            _approve_inventory_stock_in_confirmation(...)
            task_run.status = COMMITTED_STATUS
            task_run.result_summary = "Confirmation approved and inventory committed."
            task_run.completed_at = now
        else:
            task_run.status = EXECUTING_STATUS
            task_run.completed_at = None
        db_session.commit()
        return confirmation
    except Exception:
        db_session.rollback()
        raise
```

- [ ] **Step 4: 重跑新增 approval 测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_clarification_confirmation.py::test_v2_approve_confirmation_commits_inventory_and_marks_task_committed backend/tests/test_v2_clarification_confirmation.py::test_v2_approve_confirmation_rolls_back_when_inventory_commit_fails -q
```

Expected:

- `2 passed`

### Task 3: 阶段验收

**Files:**
- Verify: `backend/tests/test_v2_clarification_confirmation.py`
- Verify: `backend/tests/test_v2_inventory_ledger.py`

- [ ] **Step 1: 运行 clarification / confirmation 全测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_clarification_confirmation.py -q
```

- [ ] **Step 2: 运行 inventory ledger 测试，确认移除内部 commit 后仍保持 green**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_inventory_ledger.py -q
```

- [ ] **Step 3: 运行关键 V2 回归**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_identity_context.py backend/tests/test_v2_conversation_runtime.py backend/tests/test_v2_clarification_confirmation.py backend/tests/test_v2_inventory_ledger.py -q
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
git add backend/app/services/v2_conversation.py backend/app/services/v2_inventory.py backend/tests/test_v2_clarification_confirmation.py docs/superpowers/plans/2026-04-18-ai-native-saas-v2-confirmation-stock-in-commit.md
git commit -m "feat: commit v2 stock-in confirmations"
```

## 自检

- Spec coverage：本计划补上 V2 runtime 的 `confirm -> commit` 主链，但只覆盖 `inventory.stock_in`，不扩展到 stock_out、audit、outbox、message projection。
- Placeholder scan：没有保留 `TBD`、`TODO`、`implement later` 一类占位。
- Type consistency：统一使用 `inventory.stock_in`、`committed`、`resolution_payload["fields"]`、`commit_v2_inventory_stock_in()` 这组命名，避免与旧 v1 `approved_stock_in_commits.py` 语义混淆。
