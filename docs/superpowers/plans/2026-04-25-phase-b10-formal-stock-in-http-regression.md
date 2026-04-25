# Phase B10 - Formal Stock-In HTTP Regression

## 背景

Phase10 后端基线已经包含正式库存入库 API：

- `POST /api/v2/inventory/stock-in`

但此前主要由脚本式 E2E 验收覆盖，缺少 pytest 级 HTTP 回归测试。Phase B10 的目标是补齐这个测试层，确保正式手工入库路径与 AI confirmation-first 路径共同守住库存账本规则。

## 本阶段范围

新增 pytest HTTP 测试文件：

- `backend/tests/test_v2_inventory_stock_in_http_flow.py`

覆盖内容：

1. 通过 V2 登录与 context/select 获取真实认证上下文。
2. 调用 `POST /api/v2/inventory/stock-in`。
3. 验证返回 `stock_in_event_id`、`inventory_item_id`、`new_quantity`。
4. 验证写入 `V2InventoryLedgerEvent(event_type="stock_in")`。
5. 验证更新 `V2InventoryStockSnapshot.current_quantity` 与 `current_price`。
6. 验证 `tenant_id` / `shop_id` 来自当前上下文。
7. 验证传入其他租户的 `inventory_item_id` 会返回 404，不写 ledger，不创建/修改 snapshot。

## 关键结论

新增测试首次运行即通过，说明正式 stock-in API 的核心实现已在 Phase10 基线中存在。本阶段没有修改生产代码，只补齐回归保障。

## 验证命令

```bash
PYTHONPATH=backend pytest -q backend/tests/test_v2_inventory_stock_in_http_flow.py
```

结果：

```text
2 passed in 4.65s
```

组合回归：

```bash
PYTHONPATH=backend python3 -m compileall -q backend/app backend/tests/test_v2_inventory_stock_in_http_flow.py && \
PYTHONPATH=backend pytest -q \
  backend/tests/test_v2_inventory_stock_in_http_flow.py \
  backend/tests/test_v2_chat_http_confirmation_flow.py \
  backend/tests/test_v2_voice_photo_http_confirmation_flow.py \
  backend/tests/test_v2_chat_confirmation_first.py
```

结果：

```text
10 passed in 18.76s
```

## Git 安全边界

本阶段仅应提交：

- `backend/tests/test_v2_inventory_stock_in_http_flow.py`
- `docs/superpowers/plans/2026-04-25-phase-b10-formal-stock-in-http-regression.md`

不得提交：

- `backend/.env`
- `backend/aism-dev.db`

这两个本地状态文件已在 Phase B9 标记为 `skip-worktree`。
