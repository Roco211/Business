# AI 原生 SaaS V2 Outbox 派发领取与 Worker Health 实现计划
> **给智能执行代理（agentic workers）：** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务逐项实现本计划。步骤使用 checkbox（`- [ ]`）语法跟踪。

**Goal:** 让 V2 已落库的 `outbox_event` 具备可领取（claim）与可观测（health）能力，为后续 dispatcher / worker 异步链路提供最小可用基础设施。

**Architecture:** 当前 V2 已经能在库存提交事务里写入 `V2OutboxEvent`，但 dispatcher 还无法按可靠顺序领取 pending 事件，也没有 internal health 接口暴露当前积压状态。本切片保持 tenant / shop 为一等边界，不引入完整 worker 编排，只新增一个 tenant/shop 作用域的 outbox service 和一个只读 internal health 路由；领取规则使用数据库内状态迁移保证幂等方向一致，health 接口复用现有 `Authorization + X-Context-Token` 上下文约束，避免把跨租户全局视角过早带进 V2。

**Tech Stack:** Python、FastAPI、SQLAlchemy、Pydantic、pytest、OpenAPI snapshot

---

## 文件结构

- 创建 `backend/app/services/v2_outbox.py`：封装 outbox claim 与 health 统计逻辑。
- 创建 `backend/app/contracts/v2/internal.py`：定义 internal worker health 响应模型。
- 创建 `backend/app/api/v2/routes/internal.py`：提供 `/api/v2/internal/worker-health`。
- 修改 `backend/app/api/v2/router.py`：注册 internal 路由。
- 创建 `backend/tests/test_v2_outbox.py`：覆盖 service 层 claim / health 规则。
- 创建 `backend/tests/test_v2_internal_api.py`：覆盖 internal worker health API。
- 修改 `project_docs/generated/openapi-v1.json`：更新 OpenAPI 快照。

### Task 1: 固定 V2 outbox claim 规则

**Files:**
- Create: `backend/tests/test_v2_outbox.py`
- Create: `backend/app/services/v2_outbox.py`

- [x] **Step 1: 先写失败测试，定义 claim 只领取当前 tenant/shop 下可用的 pending 事件**

```python
def test_claim_v2_outbox_events_claims_pending_events_in_stable_order(db_session) -> None:
    seed_v2_outbox_event(
        db_session,
        outbox_event_id="evt_oldest",
        tenant_id="tenant_a",
        shop_id="shop_a1",
        status="pending",
        available_at=_dt("2026-04-18T10:00:00"),
        created_at=_dt("2026-04-18T10:00:00"),
    )
    seed_v2_outbox_event(
        db_session,
        outbox_event_id="evt_newer",
        tenant_id="tenant_a",
        shop_id="shop_a1",
        status="pending",
        available_at=_dt("2026-04-18T10:01:00"),
        created_at=_dt("2026-04-18T10:01:00"),
    )
    seed_v2_outbox_event(
        db_session,
        outbox_event_id="evt_future",
        tenant_id="tenant_a",
        shop_id="shop_a1",
        status="pending",
        available_at=_dt("2026-04-18T11:00:00"),
        created_at=_dt("2026-04-18T10:02:00"),
    )

    claimed = claim_v2_outbox_events(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        limit=2,
        now=_dt("2026-04-18T10:05:00"),
    )

    assert [event.outbox_event_id for event in claimed] == ["evt_oldest", "evt_newer"]
    assert all(event.status == "processing" for event in claimed)
    assert all(event.attempt_count == 1 for event in claimed)
```

- [x] **Step 2: 再写失败测试，确认 claim 不会跨 tenant/shop，也不会重复领取非 pending 事件**

```python
def test_claim_v2_outbox_events_skips_other_scope_and_non_pending_rows(db_session) -> None:
    ...
    assert [event.outbox_event_id for event in claimed] == ["evt_scope_match"]
```

- [x] **Step 3: 运行测试，确认当前缺少服务而失败**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_outbox.py -q
```

- [x] **Step 4: 实现最小 outbox service**

`backend/app/services/v2_outbox.py`

```python
PENDING_OUTBOX_STATUS = "pending"
PROCESSING_OUTBOX_STATUS = "processing"


def claim_v2_outbox_events(...):
    candidate_ids = db_session.scalars(
        select(V2OutboxEvent.outbox_event_id)
        .where(
            V2OutboxEvent.tenant_id == tenant_id,
            V2OutboxEvent.shop_id == shop_id,
            V2OutboxEvent.status == PENDING_OUTBOX_STATUS,
            V2OutboxEvent.available_at <= now,
        )
        .order_by(V2OutboxEvent.available_at.asc(), V2OutboxEvent.created_at.asc(), V2OutboxEvent.outbox_event_id.asc())
        .limit(limit)
    ).all()
    if not candidate_ids:
        return []

    db_session.execute(
        update(V2OutboxEvent)
        .where(
            V2OutboxEvent.outbox_event_id.in_(candidate_ids),
            V2OutboxEvent.status == PENDING_OUTBOX_STATUS,
        )
        .values(
            status=PROCESSING_OUTBOX_STATUS,
            attempt_count=V2OutboxEvent.attempt_count + 1,
        )
    )
    db_session.flush()
    return db_session.scalars(
        select(V2OutboxEvent)
        .where(V2OutboxEvent.outbox_event_id.in_(candidate_ids))
        .order_by(V2OutboxEvent.available_at.asc(), V2OutboxEvent.created_at.asc(), V2OutboxEvent.outbox_event_id.asc())
    ).all()
```

- [x] **Step 5: 重跑 outbox service 测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_outbox.py -q
```

Expected:

- `2 passed`

### Task 2: 暴露 tenant/shop 作用域的 internal worker health

**Files:**
- Create: `backend/tests/test_v2_internal_api.py`
- Create: `backend/app/contracts/v2/internal.py`
- Create: `backend/app/api/v2/routes/internal.py`
- Modify: `backend/app/api/v2/router.py`
- Modify: `backend/app/services/v2_outbox.py`

- [x] **Step 1: 写失败测试，确认 worker-health 需要 Authorization 与 X-Context-Token，并返回当前上下文的 outbox 积压**

```python
def test_v2_worker_health_returns_scoped_outbox_counts(client, db_session) -> None:
    token, context_token = _seed_v2_internal_context(client, db_session)
    seed_v2_outbox_event(...)
    seed_v2_outbox_event(...)

    response = client.get(
        "/api/v2/internal/worker-health",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
    )

    assert response.status_code == 200
    assert response.json()["data"] == {
        "tenant_id": "tenant_a",
        "shop_id": "shop_a1",
        "pending_count": 1,
        "processing_count": 1,
        "oldest_pending_at": "2026-04-18T10:00:00",
        "oldest_available_pending_at": "2026-04-18T10:00:00",
    }
```

- [x] **Step 2: 运行 API 测试，确认当前缺少 internal route 而失败**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_internal_api.py -q
```

- [x] **Step 3: 在 outbox service 中增加 health 聚合，并新增 internal contract / route**

`backend/app/services/v2_outbox.py`

```python
@dataclass(frozen=True)
class V2OutboxHealthSummary:
    tenant_id: str
    shop_id: str
    pending_count: int
    processing_count: int
    oldest_pending_at: datetime | None
    oldest_available_pending_at: datetime | None
```

`backend/app/api/v2/routes/internal.py`

```python
@router.get("/worker-health", response_model=V2DataEnvelope[V2WorkerHealthData])
def get_v2_worker_health(...):
    summary = get_v2_outbox_health_summary(...)
    return V2DataEnvelope(
        data=V2WorkerHealthData(
            tenant_id=summary.tenant_id,
            shop_id=summary.shop_id,
            pending_count=summary.pending_count,
            processing_count=summary.processing_count,
            oldest_pending_at=summary.oldest_pending_at,
            oldest_available_pending_at=summary.oldest_available_pending_at,
        )
    )
```

- [x] **Step 4: 重跑 internal API 测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_internal_api.py -q
```

Expected:

- `1 passed`

### Task 3: 更新契约快照并做阶段验收

**Files:**
- Verify: `backend/tests/test_v2_outbox.py`
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
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_outbox.py backend/tests/test_v2_internal_api.py -q
```

- [x] **Step 3: 运行 OpenAPI 快照测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_openapi_contract_snapshot.py -q
```

- [x] **Step 4: 运行关键 V2 回归**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_alembic_bootstrap.py backend/tests/test_v2_identity_context.py backend/tests/test_v2_conversation_runtime.py backend/tests/test_v2_clarification_confirmation.py backend/tests/test_v2_inventory_ledger.py backend/tests/test_v2_inventory_read_api.py backend/tests/test_v2_inventory_corrections_api.py backend/tests/test_v2_inventory_stock_out_api.py backend/tests/test_v2_outbox.py backend/tests/test_v2_internal_api.py backend/tests/test_openapi_contract_snapshot.py -q
```

- [x] **Step 5: 如关键 V2 回归通过，再运行完整 backend 测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests -q
```
