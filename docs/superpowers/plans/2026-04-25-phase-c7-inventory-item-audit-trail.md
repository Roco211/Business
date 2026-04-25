# Phase C7 — 单商品审计轨迹 API

日期：2026-04-25
分支：hermes/ai-native-saas-rewrite

## 目标

在 C6 商品主数据 CRUD 与软删除闭环之后，补齐单商品库存审计轨迹 API，让用户可以追溯某个商品在当前门店中的历史库存变化。

本阶段仍然坚持后端优先，暂不推进前端。

## 范围

新增正式审计 API：

- `GET /api/v2/inventory/items/{inventory_item_id}/audit`

查询结果直接来自库存事件账本：

- `V2InventoryLedgerEvent`

不新建重复 audit 表，避免事实源不一致。

## 关键业务规则

1. 所有请求必须带：
   - `Authorization: Bearer <token>`
   - `X-Context-Token: <context_session_id>`

2. audit 查询必须限定当前执行上下文：
   - `tenant_id == context.tenant_id`
   - `shop_id == context.shop_id`
   - `inventory_item_id == path.inventory_item_id`

3. audit 是历史追溯视图，不是普通业务列表：
   - active 商品可查
   - deleted 商品也可查
   - 跨租户商品返回 404
   - 同租户其他门店流水不返回
   - 同门店其他商品流水不返回

4. 排序：
   - `occurred_at desc`
   - `event_id desc`

5. 分页：
   - `limit` 默认 20
   - 范围 1 到 50

## TDD 红灯

新增测试：

- `backend/tests/test_v2_inventory_item_audit_http_flow.py`

红灯结果：

- `GET /api/v2/inventory/items/{deleted_item_id}/audit?limit=10` 返回 404
- 原因：audit API 尚不存在

## 实现

修改 contract：

- `backend/app/contracts/v2/inventory.py`
  - 新增 `V2InventoryItemAuditData`

修改 service：

- `backend/app/services/v2_inventory.py`
  - 新增 `get_v2_inventory_item_for_audit(...)`
    - 只校验 tenant 归属
    - 不过滤 `status == active`
  - 新增 `list_v2_inventory_item_audit_events(...)`
    - 直接查询 `V2InventoryLedgerEvent`
    - 限定 tenant/shop/item
    - 支持 limit
    - 按 occurred_at/event_id 倒序

修改 route：

- `backend/app/api/v2/routes/inventory.py`
  - 新增 `GET /items/{inventory_item_id}/audit`
  - 复用 V2 权限上下文
  - 跨租户/不存在商品统一返回 404

## 验证

Focused C7：

```bash
PYTHONPATH=backend pytest -q backend/tests/test_v2_inventory_item_audit_http_flow.py
```

结果：

- `2 passed in 5.16s`

C6+C7+库存/Dashboard 组合回归：

```bash
PYTHONPATH=backend pytest -vv \
  backend/tests/test_v2_inventory_item_audit_http_flow.py \
  backend/tests/test_v2_inventory_item_crud_http_flow.py \
  backend/tests/test_v2_inventory_query_isolation_http_flow.py \
  backend/tests/test_v2_inventory_stock_in_http_flow.py \
  backend/tests/test_v2_inventory_stock_out_http_flow.py \
  backend/tests/test_v2_dashboard_analytics_isolation_http_flow.py
```

结果：

- `14 passed in 30.28s`

提交前完整相关验证：

```bash
PYTHONPATH=backend python3 -m compileall -q backend/app backend/tests backend/scripts && \
PYTHONPATH=backend pytest -vv \
  backend/tests/test_v2_inventory_item_audit_http_flow.py \
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

- `22 passed in 60.25s`

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

下一阶段建议 Phase C8：本地 preflight / CI 门禁固化。

原因：C1-C7 已补齐 inventory/query/dashboard/item/audit 多条核心后端安全边界，下一步应该把 compileall、核心 pytest、Docker acceptance 固化成标准门禁，避免后续真实 Provider 或前端接入时破坏现有边界。
