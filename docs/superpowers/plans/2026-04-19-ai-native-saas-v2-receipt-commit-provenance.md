# AI 原生 SaaS V2 票据审批提交来源闭环实施计划

> **给智能执行代理（agentic workers）：** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务逐项实现本计划。步骤使用 checkbox（`- [ ]`）语法跟踪。

**Goal:** 让 receipt-derived `inventory.stock_in` confirmation 在审批提交后，把票据文档与媒体来源写入 audit log / outbox metadata，同时保持 inventory ledger 仍以 `task_run` 作为确定性写入来源。

**Architecture:** 在 `backend/app/services/v2_commit_records.py` 增加 provenance 归一化 helper，优先从 `confirmation.resolution_payload["fields"]` 读取来源字段，缺失时回退到 `confirmation.draft_payload`。commit records 对外暴露 receipt provenance，并额外保留 `ledger_source_type` / `ledger_source_id` 以免丢失底层 ledger 线索。

**Tech Stack:** Python、FastAPI、SQLAlchemy、pytest、现有 V2 conversation / inventory / media_ai 服务

---

## 文件结构

- 修改 `backend/app/services/v2_commit_records.py`：补充 confirmation provenance 提取与 metadata/payload 写入。
- 修改 `backend/tests/test_v2_clarification_confirmation.py`：新增 receipt-derived stock-in confirmation 审批后的 provenance 回归测试。
- 验证 `backend/tests/test_v2_media_ai_platform.py`：确认已有 receipt extraction -> confirmation 流程测试继续保持通过。

### Task 1: 用失败测试钉住 receipt provenance 丢失点

**Files:**
- Modify: `backend/tests/test_v2_clarification_confirmation.py`
- Test: `backend/tests/test_v2_clarification_confirmation.py::test_v2_approve_receipt_derived_stock_in_confirmation_appends_receipt_provenance_to_audit_log_and_outbox_event`

- [x] **Step 1: 写失败测试，模拟 receipt-derived confirmation 但审批时不重复提交 provenance 字段**

```python
def test_v2_approve_receipt_derived_stock_in_confirmation_appends_receipt_provenance_to_audit_log_and_outbox_event(
    client, db_session
) -> None:
    confirmation = create_v2_confirmation(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        task_run_id=task_run_id,
        confirmation_type="inventory.stock_in",
        draft_payload={
            "item_name": "Cola",
            "quantity": 2,
            "unit": "box",
            "price": 18.5,
            "source_type": "receipt-document",
            "source_document_id": "vdoc_receipt_001",
            "source_media_asset_id": "vmedia_receipt_001",
        },
    )

    response = client.post(
        f"/api/v2/confirmations/{confirmation.confirmation_id}/approve",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={"resolution_payload": {"fields": {"item_name": "Cola", "quantity": 2, "unit": "box", "price": 18.5}}},
    )

    assert response.status_code == 200
    assert audit_log.metadata_json["source_type"] == "receipt-document"
    assert audit_log.metadata_json["source_document_id"] == "vdoc_receipt_001"
    assert outbox_event.payload_json["source_media_asset_id"] == "vmedia_receipt_001"
```

- [x] **Step 2: 运行红灯测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_clarification_confirmation.py::test_v2_approve_receipt_derived_stock_in_confirmation_appends_receipt_provenance_to_audit_log_and_outbox_event -q
```

Expected: FAIL，因为当前 `append_v2_inventory_commit_records(...)` 只写入 ledger 的 `source_type == "task_run"`，且 outbox payload 中还没有 receipt provenance 字段。

### Task 2: 在 commit records 中补齐 provenance 归一化

**Files:**
- Modify: `backend/app/services/v2_commit_records.py`
- Test: `backend/tests/test_v2_clarification_confirmation.py::test_v2_approve_receipt_derived_stock_in_confirmation_appends_receipt_provenance_to_audit_log_and_outbox_event`

- [x] **Step 1: 写最小 helper，从 confirmation 里提取 commit provenance**

```python
def _build_inventory_commit_provenance(
    confirmation: V2Confirmation,
    ledger_event: V2InventoryLedgerEvent,
) -> dict[str, str | None]:
    resolved_fields = dict(confirmation.resolution_payload.get("fields") or {})
    draft_fields = dict(confirmation.draft_payload or {})
    source_type = resolved_fields.get("source_type") or draft_fields.get("source_type") or ledger_event.source_type
    source_document_id = resolved_fields.get("source_document_id") or draft_fields.get("source_document_id")
    source_media_asset_id = resolved_fields.get("source_media_asset_id") or draft_fields.get("source_media_asset_id")
    source_id = source_document_id or ledger_event.source_id
    return {
        "source_type": str(source_type),
        "source_id": str(source_id),
        "source_document_id": str(source_document_id) if source_document_id else None,
        "source_media_asset_id": str(source_media_asset_id) if source_media_asset_id else None,
        "ledger_source_type": ledger_event.source_type,
        "ledger_source_id": ledger_event.source_id,
    }
```

- [x] **Step 2: 把 helper 结果并入 audit metadata 与 outbox payload**

```python
provenance = _build_inventory_commit_provenance(confirmation, ledger_event)

metadata_json = {
    ...,
    **provenance,
    "reason": ledger_event.reason,
}

payload_json = {
    ...,
    **provenance,
    "reason": ledger_event.reason,
}
```

- [x] **Step 3: 重跑目标测试，确认绿灯**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_clarification_confirmation.py::test_v2_approve_receipt_derived_stock_in_confirmation_appends_receipt_provenance_to_audit_log_and_outbox_event -q
```

Expected: PASS。

### Task 3: 局部回归与整理

**Files:**
- Verify: `backend/tests/test_v2_clarification_confirmation.py`
- Verify: `backend/tests/test_v2_media_ai_platform.py`
- Verify: `backend/app/services/v2_commit_records.py`

- [x] **Step 1: 运行与本刀相关的测试切片**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_clarification_confirmation.py backend/tests/test_v2_media_ai_platform.py -q
```

Expected: PASS。

- [x] **Step 2: 检查 diff 与工作区状态**

Run:

```powershell
git diff --check
git status --short
```

Expected: 无格式错误，只包含本刀相关改动。

- [ ] **Step 3: 提交本刀**

Run:

```powershell
git add docs/superpowers/plans/2026-04-19-ai-native-saas-v2-receipt-commit-provenance.md backend/app/services/v2_commit_records.py backend/tests/test_v2_clarification_confirmation.py
git commit -m "feat: preserve v2 receipt commit provenance"
```

Expected: 生成一笔只包含 receipt commit provenance 闭环的提交，便于后续继续推进审批后的 projection / worker 消费链路。
