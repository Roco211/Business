# Phase C5 — Dashboard / Analytics 查询侧隔离加固

日期：2026-04-25
分支：hermes/ai-native-saas-rewrite

## 目标

加固 V2 Dashboard 首页聚合接口 `/api/v2/dashboard/summary` 的查询侧边界，确保首页营业数据、热销排行、库存预警、日趋势只展示当前执行上下文的当前业务视图：

- 当前 tenant
- 当前 shop
- active 商品
- 不泄露同租户其他门店数据
- 不泄露其他租户数据
- 不把 deleted / 非 active 商品纳入 Dashboard 聚合

## 审计范围

- `backend/app/api/v2/routes/dashboard.py`
- `backend/app/services/v2_analytics.py`
- `backend/tests/test_v2_dashboard_analytics_isolation_http_flow.py`

## 发现的问题

新增 HTTP 回归测试红灯确认：

- `get_revenue_summary()` 仅按 ledger event 的 tenant/shop 过滤，未 join 商品表过滤 `V2InventoryItem.status == "active"`。
- `get_sales_ranking()` 未过滤商品 active 状态，deleted 商品的销售流水会进入热销榜。
- `get_low_stock_alerts()` 未过滤商品 active 状态，deleted 商品快照可能进入库存预警。
- `get_daily_revenue_series()` 未过滤商品 active 状态，deleted 商品流水会进入日趋势。
- `gross_profit` 使用负数 stock_out revenue 原值计算，导致利润方向错误；应使用归一化后的销售额减成本。

## 修复内容

- Revenue summary：stock_out / stock_in 聚合都 join `V2InventoryItem`，并限定：
  - `V2InventoryLedgerEvent.tenant_id == tenant_id`
  - `V2InventoryLedgerEvent.shop_id == shop_id`
  - `V2InventoryItem.tenant_id == tenant_id`
  - `V2InventoryItem.status == "active"`
- Sales ranking：增加 `V2InventoryItem.tenant_id == tenant_id` 与 `status == "active"`。
- Low stock alerts：增加 `V2InventoryItem.status == "active"` 与 `V2InventoryStockSnapshot.tenant_id == tenant_id`。
- Daily revenue series：join `V2InventoryItem`，增加 active 商品过滤。
- Gross profit：使用 `abs(total_revenue) - total_cost`。

## 新增测试

新增：`backend/tests/test_v2_dashboard_analytics_isolation_http_flow.py`

测试通过真实 HTTP 流：

1. 创建 V2 account / tenant / membership / shop / shop_access。
2. 创建当前门店 active 商品、deleted 商品、同租户其他门店数据、其他租户数据。
3. 登录 `/api/v2/auth/login`。
4. 选择上下文 `/api/v2/context/select`。
5. 调用 `/api/v2/dashboard/summary?days=30`。
6. 断言：
   - revenue 只计算 active 当前门店商品。
   - sales_ranking 只包含 active 当前门店商品。
   - low_stock 只包含 active 当前门店商品。
   - pending_tasks 只基于过滤后的低库存和交易数。
   - daily_revenue_series 只包含 active 当前门店商品流水。

## 验证记录

红灯：

```bash
PYTHONPATH=backend pytest -q backend/tests/test_v2_dashboard_analytics_isolation_http_flow.py
# FAILED: revenue total_revenue 为 7300.0，期望 300.0，说明 deleted 商品销售流水泄露进 Dashboard 聚合。
```

绿灯：

```bash
PYTHONPATH=backend pytest -q backend/tests/test_v2_dashboard_analytics_isolation_http_flow.py
# 1 passed in 4.28s
```

相关组合回归：

```bash
PYTHONPATH=backend pytest -vv \
  backend/tests/test_v2_dashboard_analytics_isolation_http_flow.py \
  backend/tests/test_v2_inventory_query_isolation_http_flow.py \
  backend/tests/test_v2_inventory_stock_in_http_flow.py \
  backend/tests/test_v2_inventory_stock_out_http_flow.py
# 10 passed in 19.78s
```

## 安全边界

- 本阶段没有读取或提交 `.env`。
- 本阶段没有记录任何 API key / token / password / secret。
- `backend/.env` 与 `backend/aism-dev.db` 继续作为本地状态文件隔离，不应提交。
