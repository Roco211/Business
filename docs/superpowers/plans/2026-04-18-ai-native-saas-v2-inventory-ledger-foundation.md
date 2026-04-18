# AI 原生 SaaS V2 库存账本基础实现计划
> **给智能执行代理（agentic workers）：** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务逐项实现本计划。步骤使用 checkbox（`- [ ]`）语法跟踪。

**Goal:** 为 `/api/v2` 建立 tenant 级商品档案、shop 级库存投影和不可变库存账本事件的最小基础层，使后续 confirmation approval 可以接入确定性库存提交工具。

**Architecture:** 本阶段只建设 `inventory_ledger` 基础真相层，不把 runtime approval 直接接到落账流程。`V2InventoryItem` 作为 tenant 级商品身份，`V2InventoryStockSnapshot` 作为 shop 级当前库存投影，`V2InventoryLedgerEvent` 作为不可变业务事实；服务层显式接收 `tenant_id / shop_id / task_run_id / account_id`，确保 AI 草稿不会直接写业务真相。

**Tech Stack:** Python、SQLAlchemy、Alembic、pytest、FastAPI 后端、SQLite 测试数据库、MySQL 生产目标

---

## 文件结构

- 修改 `backend/app/models/v2_inventory.py`：新增 V2 库存账本三类模型。
- 修改 `backend/app/models/__init__.py`：导出 V2 库存模型。
- 新增 `backend/alembic/versions/20260418_05_create_v2_inventory_ledger_foundation.py`：创建 V2 库存账本相关表。
- 新增 `backend/app/services/v2_inventory.py`：实现 V2 库存确定性提交工具。
- 新增 `backend/tests/test_v2_inventory_ledger.py`：覆盖 schema、提交、跨门店投影边界。

### Task 1: 建立 V2 库存账本 schema

**Files:**
- Create: `backend/tests/test_v2_inventory_ledger.py`
- Create: `backend/app/models/v2_inventory.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/20260418_05_create_v2_inventory_ledger_foundation.py`

- [x] **Step 1: 先写失败测试，固定 tenant / shop 边界**

```python
def test_v2_inventory_ledger_schema_persists_tenant_and_shop_boundaries(db_session) -> None:
    from sqlalchemy import select

    from app.models import V2InventoryItem, V2InventoryLedgerEvent, V2InventoryStockSnapshot

    now = _utc_now_naive()
    _seed_v2_inventory_context(db_session, task_run_id="vtask_v2_inventory_schema")
    item = V2InventoryItem(
        inventory_item_id="vitem_001",
        tenant_id="tenant_a",
        sku="COLA-001",
        name="Cola",
        barcode="690000000001",
        default_unit="box",
        status="active",
        created_at=now,
        updated_at=now,
    )
    snapshot = V2InventoryStockSnapshot(
        snapshot_id="vsnapshot_001",
        tenant_id="tenant_a",
        shop_id="shop_a1",
        inventory_item_id="vitem_001",
        current_quantity=2,
        current_price=18.5,
        low_stock_threshold=1,
        updated_at=now,
    )
    event = V2InventoryLedgerEvent(
        event_id="vevent_001",
        tenant_id="tenant_a",
        shop_id="shop_a1",
        inventory_item_id="vitem_001",
        event_type="stock_in",
        quantity_delta=2,
        quantity_after=2,
        unit="box",
        price=18.5,
        source_type="task_run",
        source_id="vtask_v2_inventory_schema",
        reason="approved stock in",
        created_by_account_id="acct_001",
        occurred_at=now,
    )
    db_session.add_all([item, snapshot, event])
    db_session.commit()

    persisted = db_session.scalar(
        select(V2InventoryLedgerEvent).where(V2InventoryLedgerEvent.event_id == "vevent_001")
    )
    assert persisted is not None
    assert persisted.tenant_id == "tenant_a"
    assert persisted.shop_id == "shop_a1"
```

- [x] **Step 2: 运行 schema 测试，确认因模型或迁移缺失而失败**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_inventory_ledger.py::test_v2_inventory_ledger_schema_persists_tenant_and_shop_boundaries -q
```

- [x] **Step 3: 新增模型与迁移**

`backend/app/models/v2_inventory.py`

```python
class V2InventoryItem(Base):
    __tablename__ = "v2_inventory_items"
    ...


class V2InventoryStockSnapshot(Base):
    __tablename__ = "v2_inventory_stock_snapshots"
    ...


class V2InventoryLedgerEvent(Base):
    __tablename__ = "v2_inventory_ledger_events"
    ...
```

`backend/alembic/versions/20260418_05_create_v2_inventory_ledger_foundation.py`

```python
revision = "20260418_05"
down_revision = "20260418_04"
```

- [x] **Step 4: 重跑 schema 测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_inventory_ledger.py::test_v2_inventory_ledger_schema_persists_tenant_and_shop_boundaries -q
```

Expected:

- `1 passed`

### Task 2: 实现 V2 入库确定性提交工具

**Files:**
- Modify: `backend/tests/test_v2_inventory_ledger.py`
- Create: `backend/app/services/v2_inventory.py`

- [x] **Step 1: 先写失败测试，固定“首次入库创建 tenant 级商品 + shop 级 snapshot + ledger event”**

```python
def test_v2_commit_stock_in_creates_item_snapshot_and_ledger_event(db_session) -> None:
    from app.services.v2_inventory import commit_v2_inventory_stock_in

    _seed_v2_inventory_context(db_session, task_run_id="vtask_v2_stock_in_create")

    result = commit_v2_inventory_stock_in(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        task_run_id="vtask_v2_stock_in_create",
        created_by_account_id="acct_001",
        payload={"item_name": "Cola", "quantity": 3, "unit": "box", "price": 18.5},
    )

    assert result.item.tenant_id == "tenant_a"
    assert result.snapshot.shop_id == "shop_a1"
    assert result.snapshot.current_quantity == 3
    assert result.event.quantity_after == 3
```

- [x] **Step 2: 运行测试，确认因为服务缺失而失败**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_inventory_ledger.py::test_v2_commit_stock_in_creates_item_snapshot_and_ledger_event -q
```

- [x] **Step 3: 实现最小服务**

`backend/app/services/v2_inventory.py`

```python
@dataclass(frozen=True)
class V2CommittedStockInResult:
    item: V2InventoryItem
    snapshot: V2InventoryStockSnapshot
    event: V2InventoryLedgerEvent


def commit_v2_inventory_stock_in(...):
    # 校验 task_run 属于显式 tenant / shop
    # 按 tenant 解析或创建商品
    # 按 shop 解析或创建 snapshot
    # 追加 ledger event
    # 更新 snapshot 投影
```

- [x] **Step 4: 重跑提交测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_inventory_ledger.py::test_v2_commit_stock_in_creates_item_snapshot_and_ledger_event -q
```

Expected:

- `1 passed`

### Task 3: 固定 tenant 级商品共享与 shop 级投影隔离

**Files:**
- Modify: `backend/tests/test_v2_inventory_ledger.py`
- Modify: `backend/app/services/v2_inventory.py`

- [x] **Step 1: 先写失败测试，确认同 tenant 下复用商品、不同 shop 的 snapshot 分离**

```python
def test_v2_commit_stock_in_reuses_tenant_item_and_keeps_shop_snapshots_isolated(db_session) -> None:
    from sqlalchemy import select

    from app.models import V2InventoryItem, V2InventoryStockSnapshot
    from app.services.v2_inventory import commit_v2_inventory_stock_in

    _seed_v2_inventory_context(db_session, task_run_id="vtask_v2_shop_a1")
    _seed_v2_shop(db_session, shop_id="shop_a2", tenant_id="tenant_a", code="a-2", name="Shop A2")
    _seed_v2_task_run_for_inventory(
        db_session,
        task_run_id="vtask_v2_shop_a2",
        tenant_id="tenant_a",
        shop_id="shop_a2",
    )

    first = commit_v2_inventory_stock_in(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        task_run_id="vtask_v2_shop_a1",
        created_by_account_id="acct_001",
        payload={"item_name": "Cola", "quantity": 3, "unit": "box", "price": 18.5},
    )
    second = commit_v2_inventory_stock_in(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a2",
        task_run_id="vtask_v2_shop_a2",
        created_by_account_id="acct_001",
        payload={"item_name": "Cola", "quantity": 5, "unit": "box", "price": 19},
    )

    assert first.item.inventory_item_id == second.item.inventory_item_id
    snapshots = list(
        db_session.scalars(
            select(V2InventoryStockSnapshot).where(
                V2InventoryStockSnapshot.inventory_item_id == first.item.inventory_item_id
            )
        )
    )
    assert {(item.shop_id, item.current_quantity) for item in snapshots} == {
        ("shop_a1", 3),
        ("shop_a2", 5),
    }
```

- [x] **Step 2: 运行隔离测试，确认失败原因是解析 / 投影逻辑尚未完整**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_inventory_ledger.py::test_v2_commit_stock_in_reuses_tenant_item_and_keeps_shop_snapshots_isolated -q
```

- [x] **Step 3: 补足 tenant 级商品匹配与 shop 级 snapshot upsert 逻辑**

```python
def _resolve_v2_inventory_item_for_stock_in(...):
    # tenant 级按 item_id 或精确 name 复用


def _get_or_create_v2_snapshot(...):
    # shop 级逐门店维护 current_quantity / current_price
```

- [x] **Step 4: 重跑隔离测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_inventory_ledger.py::test_v2_commit_stock_in_reuses_tenant_item_and_keeps_shop_snapshots_isolated -q
```

Expected:

- `1 passed`

### Task 4: 阶段验收

**Files:**
- Verify: `backend/tests/test_v2_inventory_ledger.py`

- [x] **Step 1: 运行 V2 inventory 账本测试文件**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_inventory_ledger.py -q
```

- [x] **Step 2: 运行关键 V2 回归**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_identity_context.py backend/tests/test_v2_conversation_runtime.py backend/tests/test_v2_clarification_confirmation.py backend/tests/test_v2_inventory_ledger.py -q
```

- [x] **Step 3: 运行后端全量测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests -q
```

- [x] **Step 4: 检查 git 状态并提交**

Run:

```powershell
git status --short
git add backend/app/models/v2_inventory.py backend/app/models/__init__.py backend/alembic/versions/20260418_05_create_v2_inventory_ledger_foundation.py backend/app/services/v2_inventory.py backend/tests/test_v2_inventory_ledger.py docs/superpowers/plans/2026-04-18-ai-native-saas-v2-inventory-ledger-foundation.md
git commit -m "feat: add v2 inventory ledger foundation"
```

## 自检

- Spec coverage：本计划只覆盖阶段 4 的最小库存真相层基础，不在本阶段引入 approval -> commit、audit、outbox、API 查询。
- Placeholder scan：没有使用 `TBD`、`TODO`、`implement later` 一类占位符。
- Type consistency：统一使用 `V2InventoryItem`、`V2InventoryStockSnapshot`、`V2InventoryLedgerEvent`、`commit_v2_inventory_stock_in` 这组命名，避免和旧 v1 `InventoryItem` / `InventoryEvent` 混淆。
