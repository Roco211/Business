# AI 原生 SaaS V2 Outbox 生命周期实现计划
> **给智能执行代理（agentic workers）：** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务逐项实现本计划。步骤使用 checkbox（`- [ ]`）语法跟踪。

**Goal:** 让 V2 outbox 从“可领取”推进到“可完成、可失败、可重试”的最小生命周期闭环，并让 worker health 暴露完成/失败积压概览。

**Architecture:** 当前 V2 outbox 已经支持 `pending -> processing` claim，但还无法表达 worker 成功完成、终止失败或延迟重试。本切片为 `v2_outbox_events` 增补最小生命周期字段，并把所有状态迁移集中在 `v2_outbox.py` 内完成；不新增 public API，也不引入完整 dispatcher，仅扩展现有 internal `worker-health` 契约以暴露 `completed_count` 与 `failed_count`，为后续 dispatcher / worker 闭环打下状态管理基础。

**Tech Stack:** Python、FastAPI、SQLAlchemy、Alembic、Pydantic、pytest、OpenAPI snapshot

---

## 文件结构

- 修改 `backend/app/models/v2_governance.py`：给 `V2OutboxEvent` 增加生命周期字段。
- 创建 `backend/alembic/versions/20260418_07_add_v2_outbox_lifecycle_fields.py`：迁移新增列。
- 修改 `backend/app/services/v2_commit_records.py`：写入新 outbox 记录时补齐 `updated_at`。
- 修改 `backend/app/services/v2_outbox.py`：实现 complete / fail / retry 状态转换，并扩展 health 统计。
- 修改 `backend/app/contracts/v2/internal.py`：扩展 worker health 响应字段。
- 修改 `backend/app/api/v2/routes/internal.py`：返回扩展后的 worker health 数据。
- 修改 `backend/tests/test_v2_outbox.py`：覆盖完成、终止失败、延迟重试。
- 修改 `backend/tests/test_v2_internal_api.py`：覆盖 worker health 的 completed/failed 计数。
- 修改 `backend/tests/test_alembic_bootstrap.py`：校验新迁移列存在。
- 修改 `project_docs/generated/openapi-v1.json`：更新 OpenAPI 快照。

### Task 1: 固定 outbox lifecycle 状态迁移

**Files:**
- Modify: `backend/tests/test_v2_outbox.py`
- Modify: `backend/app/models/v2_governance.py`
- Create: `backend/alembic/versions/20260418_07_add_v2_outbox_lifecycle_fields.py`
- Modify: `backend/app/services/v2_commit_records.py`
- Modify: `backend/app/services/v2_outbox.py`

- [x] **Step 1: 先写失败测试，确认 processing 事件可以被标记为 completed**

```python
def test_complete_v2_outbox_event_marks_processing_event_completed(db_session) -> None:
    outbox_service = _load_v2_outbox_service()
    _seed_v2_outbox_scope(db_session)
    _seed_v2_outbox_event(... status="processing", attempt_count=1)
    completed = outbox_service.complete_v2_outbox_event(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        outbox_event_id="evt_processing",
        now=_dt("2026-04-18T10:10:00"),
    )

    assert completed.status == "completed"
    assert completed.processed_at == _dt("2026-04-18T10:10:00")
    assert completed.updated_at == _dt("2026-04-18T10:10:00")
    assert completed.last_error_code is None
```

- [x] **Step 2: 再写失败测试，确认 processing 事件可以终止失败或带延迟重试回到 pending**

```python
def test_fail_v2_outbox_event_without_retry_marks_terminal_failed(db_session) -> None:
    failed = outbox_service.fail_v2_outbox_event(..., error_code="projection_failed", error_message="projection failed")
    assert failed.status == "failed"
    assert failed.processed_at == _dt("2026-04-18T10:10:00")
    assert failed.last_error_code == "projection_failed"


def test_fail_v2_outbox_event_with_retry_returns_to_pending_after_delay(db_session) -> None:
    retried = outbox_service.fail_v2_outbox_event(..., retry_after_seconds=300)
    assert retried.status == "pending"
    assert retried.available_at == _dt("2026-04-18T10:15:00")
    assert retried.processed_at is None
```

- [x] **Step 3: 运行 outbox 测试，确认当前缺少生命周期函数或字段而失败**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_outbox.py -q
```

- [x] **Step 4: 实现最小模型迁移与状态转换**

`backend/app/models/v2_governance.py`

```python
last_error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
last_error_message: Mapped[str | None] = mapped_column(String(255), nullable=True)
processed_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
updated_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now_naive)
```

`backend/app/services/v2_outbox.py`

```python
COMPLETED_OUTBOX_STATUS = "completed"
FAILED_OUTBOX_STATUS = "failed"


def complete_v2_outbox_event(...):
    update(... where status == "processing").values(
        status=COMPLETED_OUTBOX_STATUS,
        processed_at=now,
        updated_at=now,
        last_error_code=None,
        last_error_message=None,
    )


def fail_v2_outbox_event(...):
    if retry_after_seconds is None:
        next_status = FAILED_OUTBOX_STATUS
        next_available_at = now
        processed_at = now
    else:
        next_status = PENDING_OUTBOX_STATUS
        next_available_at = now + timedelta(seconds=retry_after_seconds)
        processed_at = None
```

- [x] **Step 5: 重跑 outbox lifecycle 测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_outbox.py -q
```

Expected:

- `5 passed`

### Task 2: 扩展 worker-health 计数

**Files:**
- Modify: `backend/tests/test_v2_internal_api.py`
- Modify: `backend/app/contracts/v2/internal.py`
- Modify: `backend/app/api/v2/routes/internal.py`
- Modify: `backend/app/services/v2_outbox.py`

- [x] **Step 1: 写失败测试，确认 worker-health 返回 completed/failed 计数**

```python
def test_v2_worker_health_returns_scoped_outbox_counts(client, db_session) -> None:
    ...
    assert response.json()["data"] == {
        "tenant_id": "tenant_a",
        "shop_id": "shop_a1",
        "pending_count": 1,
        "processing_count": 1,
        "completed_count": 1,
        "failed_count": 1,
        "oldest_pending_at": ...,
        "oldest_available_pending_at": ...,
    }
```

- [x] **Step 2: 运行 internal API 测试，确认当前契约尚未扩展而失败**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_internal_api.py -k "worker_health" -q
```

- [x] **Step 3: 扩展 health summary / contract / route**

`backend/app/services/v2_outbox.py`

```python
completed_count = db_session.scalar(select(func.count()).where(... status == "completed")) or 0
failed_count = db_session.scalar(select(func.count()).where(... status == "failed")) or 0
```

`backend/app/contracts/v2/internal.py`

```python
class V2WorkerHealthData(BaseModel):
    ...
    completed_count: int
    failed_count: int
```

- [x] **Step 4: 重跑 worker-health 测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_internal_api.py -k "worker_health" -q
```

Expected:

- `1 passed`

### Task 3: 更新迁移断言、快照并做阶段验收

**Files:**
- Modify: `backend/tests/test_alembic_bootstrap.py`
- Verify: `backend/tests/test_v2_outbox.py`
- Verify: `backend/tests/test_v2_internal_api.py`
- Verify: `backend/tests/test_openapi_contract_snapshot.py`
- Modify: `project_docs/generated/openapi-v1.json`

- [x] **Step 1: 补迁移断言**

```python
assert {"last_error_code", "last_error_message", "processed_at", "updated_at"} <= {
    column["name"] for column in inspector.get_columns("v2_outbox_events")
}
```

- [x] **Step 2: 更新 OpenAPI 快照**

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

- [x] **Step 3: 运行新增目标测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_outbox.py backend/tests/test_v2_internal_api.py backend/tests/test_alembic_bootstrap.py -q
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
