# AI 原生 SaaS V2 库存提交审计与 Outbox 实现计划
> **给智能执行代理（agentic workers）：** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务逐项实现本计划。步骤使用 checkbox（`- [ ]`）语法跟踪。

**Goal:** 让 V2 `inventory.stock_in` / `inventory.stock_out` confirmation approve 成功提交后，在同一事务内写入 V2 审计日志（audit log）和 outbox 事件（outbox event）。

**Architecture:** 当前 V2 库存提交已经写入账本事件、库存投影和系统结果消息，但缺少 spec 要求的审计与可靠异步投递记录。本切片新增 `V2AuditLog` 与 `V2OutboxEvent` 作为 V2 独立模型，不复用旧 `/api/v1` 的 `audit_logs` 表，避免把 `shop = tenant` 旧边界带入新架构；`approve_v2_confirmation()` 在库存确定性工具提交成功后追加 audit/outbox，并与 confirmation 状态、task 状态、system result message 一起提交。

**Tech Stack:** Python、FastAPI、SQLAlchemy、Alembic、pytest

---

## 文件结构

- 创建 `backend/app/models/v2_governance.py`：定义 `V2AuditLog` 与 `V2OutboxEvent`。
- 修改 `backend/app/models/__init__.py`：导出新增 V2 governance 模型。
- 创建 `backend/alembic/versions/20260418_06_create_v2_audit_outbox.py`：创建 `v2_audit_logs` 与 `v2_outbox_events`。
- 创建 `backend/app/services/v2_commit_records.py`：提供库存 commit 后的 audit/outbox 写入 helper。
- 修改 `backend/app/services/v2_conversation.py`：在 stock-in / stock-out approve 成功后接入 helper。
- 修改 `backend/tests/test_v2_clarification_confirmation.py`：增加 API 级验收，确认 approve 后 audit/outbox 均落库且带 tenant/shop/task/confirmation 边界。

### Task 1: 固定 stock-in commit 的 audit/outbox 记录

**Files:**
- Modify: `backend/tests/test_v2_clarification_confirmation.py`
- Create: `backend/app/models/v2_governance.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/20260418_06_create_v2_audit_outbox.py`
- Create: `backend/app/services/v2_commit_records.py`
- Modify: `backend/app/services/v2_conversation.py`

- [x] **Step 1: 先写失败测试，确认 stock-in approve 后写入 V2 audit/outbox**

```python
def test_v2_approve_stock_in_confirmation_appends_audit_log_and_outbox_event(client, db_session) -> None:
    from sqlalchemy import select

    from app.models import V2AuditLog, V2OutboxEvent
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
        json={
            "resolution_payload": {
                "fields": {"item_name": "Cola", "quantity": 2, "unit": "box", "price": 18.5}
            }
        },
    )

    db_session.expire_all()
    audit_log = db_session.scalar(select(V2AuditLog).where(V2AuditLog.task_run_id == task_run_id))
    outbox_event = db_session.scalar(select(V2OutboxEvent).where(V2OutboxEvent.aggregate_id == task_run_id))

    assert response.status_code == 200
    assert audit_log is not None
    assert audit_log.tenant_id == "tenant_a"
    assert audit_log.shop_id == "shop_a1"
    assert audit_log.session_id is not None
    assert audit_log.action == "inventory.stock_in_committed"
    assert audit_log.actor_id == "acct_001"
    assert audit_log.metadata_json["confirmation_id"] == confirmation.confirmation_id
    assert audit_log.metadata_json["event_type"] == "stock_in"
    assert outbox_event is not None
    assert outbox_event.tenant_id == "tenant_a"
    assert outbox_event.shop_id == "shop_a1"
    assert outbox_event.aggregate_type == "task_run"
    assert outbox_event.aggregate_id == task_run_id
    assert outbox_event.event_type == "inventory.stock_in.committed"
    assert outbox_event.status == "pending"
    assert outbox_event.attempt_count == 0
    assert outbox_event.payload_json["confirmation_id"] == confirmation.confirmation_id
```

- [x] **Step 2: 运行测试，确认当前缺少模型或记录而失败**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_clarification_confirmation.py::test_v2_approve_stock_in_confirmation_appends_audit_log_and_outbox_event -q
```

- [x] **Step 3: 新增 V2 governance 模型与迁移**

`backend/app/models/v2_governance.py`

```python
class V2AuditLog(Base):
    __tablename__ = "v2_audit_logs"
    audit_log_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("v2_tenants.tenant_id"), nullable=False, index=True)
    shop_id: Mapped[str] = mapped_column(ForeignKey("v2_shops.shop_id"), nullable=False, index=True)
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(40), nullable=False)
    session_id: Mapped[str | None] = mapped_column(ForeignKey("v2_conversation_sessions.session_id"), nullable=True)
    task_run_id: Mapped[str | None] = mapped_column(ForeignKey("v2_task_runs.task_run_id"), nullable=True)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    metadata_json: Mapped[dict[str, object]] = mapped_column("metadata", JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now_naive)


class V2OutboxEvent(Base):
    __tablename__ = "v2_outbox_events"
    outbox_event_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("v2_tenants.tenant_id"), nullable=False, index=True)
    shop_id: Mapped[str] = mapped_column(ForeignKey("v2_shops.shop_id"), nullable=False, index=True)
    aggregate_type: Mapped[str] = mapped_column(String(40), nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(40), nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    payload_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    available_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now_naive)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now_naive)
```

- [x] **Step 4: 新增写入 helper 并接入 stock-in approve**

`backend/app/services/v2_commit_records.py`

```python
def append_v2_inventory_commit_records(...):
    audit_log = V2AuditLog(...)
    outbox_event = V2OutboxEvent(...)
    db_session.add(audit_log)
    db_session.add(outbox_event)
    db_session.flush()
    return V2InventoryCommitRecords(audit_log=audit_log, outbox_event=outbox_event)
```

`backend/app/services/v2_conversation.py`

```python
append_v2_inventory_commit_records(
    db_session,
    task_run=task_run,
    confirmation=confirmation,
    actor_id=approved_by_account_id,
    inventory_item=commit_result.item,
    ledger_event=commit_result.event,
)
```

- [x] **Step 5: 重跑 stock-in 测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_clarification_confirmation.py::test_v2_approve_stock_in_confirmation_appends_audit_log_and_outbox_event -q
```

Expected:

- `1 passed`

### Task 2: 覆盖 stock-out commit 的 audit/outbox 记录

**Files:**
- Modify: `backend/tests/test_v2_clarification_confirmation.py`
- Modify: `backend/app/services/v2_inventory.py`
- Modify: `backend/app/services/v2_conversation.py`
- Modify: `backend/app/services/v2_commit_records.py`

- [x] **Step 1: 写失败测试，确认 stock-out approve 后写入 V2 audit/outbox**

```python
def test_v2_approve_stock_out_confirmation_appends_audit_log_and_outbox_event(client, db_session) -> None:
    ...
    assert audit_log.action == "inventory.stock_out_committed"
    assert audit_log.metadata_json["event_type"] == "stock_out"
    assert outbox_event.event_type == "inventory.stock_out.committed"
```

- [x] **Step 2: 运行测试，确认 stock-out 缺少库存 item 上下文或记录而失败**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_clarification_confirmation.py::test_v2_approve_stock_out_confirmation_appends_audit_log_and_outbox_event -q
```

- [x] **Step 3: 让 stock-out commit result 返回 item，并接入同一个 helper**

`backend/app/services/v2_inventory.py`

```python
@dataclass(frozen=True)
class V2InventoryStockOutResult:
    item: V2InventoryItem
    snapshot: V2InventoryStockSnapshot
    event: V2InventoryLedgerEvent
```

`backend/app/services/v2_conversation.py`

```python
commit_result = commit_v2_inventory_stock_out(...)
append_v2_inventory_commit_records(
    db_session,
    task_run=task_run,
    confirmation=confirmation,
    actor_id=approved_by_account_id,
    inventory_item=commit_result.item,
    ledger_event=commit_result.event,
)
```

- [x] **Step 4: 重跑 stock-out 测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_clarification_confirmation.py::test_v2_approve_stock_out_confirmation_appends_audit_log_and_outbox_event -q
```

Expected:

- `1 passed`

### Task 3: 阶段验收

**Files:**
- Verify: `backend/tests/test_v2_clarification_confirmation.py`
- Verify: `backend/tests/test_v2_inventory_ledger.py`
- Verify: `backend/tests/test_alembic_bootstrap.py`

- [x] **Step 1: 运行新增目标测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_clarification_confirmation.py -k "audit_log_and_outbox_event" -q
```

- [x] **Step 2: 运行 clarification / confirmation 全测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_clarification_confirmation.py -q
```

- [x] **Step 3: 运行 migration / V2 关键回归**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_alembic_bootstrap.py backend/tests/test_v2_identity_context.py backend/tests/test_v2_conversation_runtime.py backend/tests/test_v2_clarification_confirmation.py backend/tests/test_v2_inventory_ledger.py backend/tests/test_v2_inventory_read_api.py backend/tests/test_v2_inventory_corrections_api.py backend/tests/test_v2_inventory_stock_out_api.py -q
```

- [x] **Step 4: 运行后端全量测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests -q
```

- [x] **Step 5: 检查 git 状态并提交**

Run:

```powershell
git status --short
git add backend/app/models/v2_governance.py backend/app/models/__init__.py backend/alembic/versions/20260418_06_create_v2_audit_outbox.py backend/app/services/v2_commit_records.py backend/app/services/v2_conversation.py backend/app/services/v2_inventory.py backend/tests/test_v2_clarification_confirmation.py docs/superpowers/plans/2026-04-18-ai-native-saas-v2-inventory-commit-audit-outbox.md
git commit -m "feat: add v2 inventory commit audit outbox"
```

## 自检

- Spec coverage：本计划覆盖 `commit` 阶段的“审计日志”和“outbox 事件”，并复用上一切片已经完成的系统结果消息。
- Placeholder scan：没有保留 `TBD`、`TODO`、`implement later` 一类占位。
- Type consistency：统一使用 `V2AuditLog`、`V2OutboxEvent`、`metadata_json`、`payload_json`、`inventory.stock_in_committed`、`inventory.stock_out_committed`。
- Architecture check：V2 audit/outbox 独立于 V1 表，不复用旧 `shop = tenant` 边界；outbox 只创建待投递事实，不在本切片实现 dispatcher / worker。
