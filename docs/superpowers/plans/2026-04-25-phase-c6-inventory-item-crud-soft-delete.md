# Phase C6 — 商品主数据 CRUD 与软删除闭环

日期：2026-04-25
分支：hermes/ai-native-saas-rewrite

## 目标

补齐 V2 商品主数据正式 HTTP API，让商品页和后续 AI 识别/入库/出库流程拥有稳定的商品档案基础。

本阶段坚持后端优先，暂不推进前端。

## 范围

新增正式商品 API：

- `POST /api/v2/inventory/items`：创建商品
- `GET /api/v2/inventory/items/{inventory_item_id}`：商品详情
- `PATCH /api/v2/inventory/items/{inventory_item_id}`：更新商品
- `DELETE /api/v2/inventory/items/{inventory_item_id}`：软删除商品

## 关键业务规则

1. 所有接口必须要求：
   - `Authorization: Bearer <token>`
   - `X-Context-Token: <context_session_id>`

2. 所有商品主数据操作必须限定当前执行上下文：
   - `tenant_id == context.tenant_id`

3. 删除为 soft delete：
   - 只将 `V2InventoryItem.status` 改为 `deleted`
   - 不硬删数据库记录
   - 不删除 ledger event
   - 不删除 stock snapshot

4. 已删除商品：
   - 详情 API 返回 404
   - 普通商品列表不可见
   - 库存列表不可见
   - 库存流水业务视图不可见
   - 历史 ledger/snapshot 数据仍保留在数据库中，供后续审计 API 使用

5. 跨租户商品访问必须统一返回 404，避免泄露资源存在性。

## TDD 红灯

新增测试：

- `backend/tests/test_v2_inventory_item_crud_http_flow.py`

红灯结果：

- `POST /api/v2/inventory/items` 返回 405，因为只存在 GET list
- `DELETE /api/v2/inventory/items/{id}` 返回 404，因为缺少详情/更新/删除路由

## 实现

修改 contract：

- `backend/app/contracts/v2/inventory.py`
  - `V2InventoryItemDetailData`
  - `V2CreateInventoryItemRequest`
  - `V2UpdateInventoryItemRequest`

修改 service：

- `backend/app/services/v2_inventory.py`
  - `get_v2_inventory_item(...)`
  - `create_v2_inventory_item(...)`
  - `update_v2_inventory_item(...)`
  - `delete_v2_inventory_item(...)`
  - 文本字段归一化与 required 校验
  - update 支持显式 `null` 清空可空字段，例如 `barcode: null`

修改 route：

- `backend/app/api/v2/routes/inventory.py`
  - 新增 create/detail/update/delete 商品主数据 HTTP API
  - 统一 404/422 错误 envelope
  - 复用现有上下文账号一致性校验

## 验证

Focused C6：

```bash
PYTHONPATH=backend pytest -q backend/tests/test_v2_inventory_item_crud_http_flow.py
```

结果：

- `2 passed in 5.14s`

商品/库存/Dashboard 组合回归：

```bash
PYTHONPATH=backend pytest -vv \
  backend/tests/test_v2_inventory_item_crud_http_flow.py \
  backend/tests/test_v2_inventory_query_isolation_http_flow.py \
  backend/tests/test_v2_inventory_stock_in_http_flow.py \
  backend/tests/test_v2_inventory_stock_out_http_flow.py \
  backend/tests/test_v2_dashboard_analytics_isolation_http_flow.py
```

结果：

- `12 passed in 24.44s`

提交前完整相关验证：

```bash
PYTHONPATH=backend python3 -m compileall -q backend/app backend/tests backend/scripts && \
PYTHONPATH=backend pytest -vv \
  backend/tests/test_v2_inventory_item_crud_http_flow.py \
  backend/tests/test_v2_inventory_query_isolation_http_flow.py \
  backend/tests/test_v2_inventory_stock_in_http_flow.py \
  backend/tests/test_v2_inventory_stock_out_http_flow.py \
  backend/tests/test_v2_dashboard_analytics_isolation_http_flow.py \
  backend/tests/test_v2_chat_http_confirmation_flow.py \
  backend/tests/test_v2_voice_photo_http_confirmation_flow.py \
  backend/tests/test_v2_chat_confirmation_first.py
```

结果：

- `20 passed in 38.63s`

Docker acceptance：

```bash
bash backend/scripts/run_docker_backend_acceptance.sh
```

结果：

- Health OK
- Alembic version：`20260419_05`
- Table count：`40`
- Phase 8：`8/8 passed`
- Phase 9：`5/5 passed`
- Phase 10：`6/6 tests passed`
- `All tests PASSED`

## 后续建议

下一阶段建议 Phase C7：单商品审计轨迹 API。

原因：C6 已确保商品可软删除且历史 ledger/snapshot 保留；C7 应提供正式审计查询接口，让 deleted 商品的历史变化可追溯，但不泄露到普通业务视图。
