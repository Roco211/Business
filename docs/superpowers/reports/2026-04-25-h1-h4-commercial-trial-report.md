# Business H1-H4 商用体验补强与生产试运行报告

时间：2026-04-25 20:52:11 CST
分支：hermes/ai-native-saas-rewrite

## 本轮范围

按 H1-H4 顺序推进：

1. H1：H5 销售单详情 / 取消 / 退货退款 UI 深化
2. H2：采购 / 客户 / 财务页面增强
3. H3：销售单 customer_id 关联与复购分析升级
4. H4：生产部署演练与报告

## H1 完成项

- H5 销售单页面升级为销售单生命周期管理页。
- 支持从销售单列表进入销售单详情。
- 详情页展示：客户、状态、金额、备注、销售单明细。
- 支持取消整单：调用后端取消接口，回补库存并生成退款财务流水。
- 支持退货 / 退款：按销售单明细提交退货数量，回补库存并更新财务流水。
- 操作后自动刷新全局业务数据。
- 页面明确提示库存与财务流水联动结果。

## H2 完成项

- 采购 / 供应商页面增强：
  - 供应商选择；
  - 创建采购入库单；
  - 供应商数量、采购单数量、当前供应商采购单统计；
  - 当前供应商采购单列表；
  - 全部采购单列表。
- 客户 / 复购页面增强：
  - 客户列表可选择客户；
  - 展示当前客户购买记录；
  - 展示客户数量、匹配订单数、当前客户订单数；
  - 复购分析继续展示真实后端统计。
- 财务页面增强：
  - 总收入、总支出、净现金流；
  - 财务流水按 transaction_type 筛选；
  - 财务流水按 direction 筛选；
  - 前后端均接入真实数据，不展示假财务数据。

## H3 完成项

- 新增 Alembic 迁移：`20260425_03_add_sales_order_customer_id.py`。
- `v2_sales_orders` 增加 `customer_id` 字段和索引。
- 销售单创建 API 支持 `customer_id`。
- 创建销售单时校验 customer_id 必须属于当前 tenant/shop 且为 active 客户。
- 销售单列表 / 详情响应返回 customer_id。
- AI 销售单 confirmation approve 流程支持传递 customer_id。
- 复购分析升级：优先按 customer_id 统计，兼容旧销售单按 customer_name 回退匹配。
- H5 创建销售单时可选择客户，关联 customer_id，提升复购统计准确性。

## H4 完成项

- 新增生产试运行演练脚本：`backend/scripts/run_production_trial_rehearsal.sh`。
- 演练覆盖：
  - production compose YAML 静态校验；
  - PostgreSQL / Redis / migrator / api 服务存在性校验；
  - API 端口映射 `0.0.0.0:${HOST_PORT:-8001}:8001` 校验；
  - 备份脚本语法校验；
  - 恢复脚本语法校验；
  - 生产安全 / CORS / 限流回归测试；
  - backend readiness summary 校验；
  - 可选 Docker 镜像构建与运行验收。
- Docker acceptance 升级到 Alembic revision `20260425_03`。
- backend readiness artifact 新增 production trial rehearsal script。

## 验证结果

- H5 构建：通过。
  - `npm run build`
- 重点后端回归：通过。
  - `backend/tests/test_v2_sales_orders_http_flow.py`
  - `backend/tests/test_v2_commercial_modules_http_flow.py`
  - `backend/tests/test_backend_readiness_summary.py`
  - 结果：8 passed
- 生产试运行演练脚本：通过。
  - `RUN_DOCKER_ACCEPTANCE=0 bash backend/scripts/run_production_trial_rehearsal.sh`
  - readiness：ready_count=17，missing_count=0
- 默认 preflight：通过。
  - `RUN_DOCKER_ACCEPTANCE=0 RUN_PROVIDER_TRIAL_PREFLIGHT=0 bash backend/scripts/run_backend_preflight.sh`
  - 结果：36 passed，H5 build 通过，readiness ready
- 完整 Docker preflight：通过。
  - `RUN_DOCKER_ACCEPTANCE=1 RUN_PROVIDER_TRIAL_PREFLIGHT=0 bash backend/scripts/run_backend_preflight.sh`
  - 结果：36 passed，Docker build 通过，Docker acceptance 通过
  - Alembic version：20260425_03
  - TABLE_COUNT：48
  - Phase 8：8/8 passed
  - Phase 9：5/5 passed
  - Phase 10：6/6 passed
- 浏览器冒烟：通过。
  - URL：`http://127.0.0.1:8001/`
  - 登录页正常
  - 登录后导航包含销售单、采购单、客户复购、财务流水
  - 销售单页面显示“销售单生命周期管理”
  - console errors：0

## 结论

H1-H4 已完成。当前 Business 已具备更完整的商用试运行体验：销售单生命周期、采购入库、客户复购、财务对账、customer_id 级复购统计，以及可重复执行的生产试运行演练脚本。

后续建议进入 H5：权限、关键操作审计、CSV 导出、错误日志与轻量压测。
