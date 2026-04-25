# Phase I2 AI员工真实状态化

## 背景

Phase I1/I3/I4 已经完成 AI Command Center、AI Task Flow 和销售/采购/库存三类 AI 草稿闭环。首页“我的AI员工”仍有部分展示感，尤其前端卡片曾使用固定的“今日任务 index+1 / 状态正常”。I2 的目标是让 AI员工状态来自真实后端数据，增强“AI员工真的在工作”的感知。

## 目标

- [x] AI员工卡片状态由后端真实数据驱动，不再使用前端硬编码任务数。
- [x] 后端 PC Dashboard BFF 聚合 V2TaskRun、V2Confirmation、库存/销售等真实数据。
- [x] 每个 AI员工返回可解释状态字段：status_label、today_task_count、pending_confirmation_count、completed_task_count、failed_task_count、last_activity_label。
- [x] H5 首页展示真实 metrics、最近动作和状态标签。
- [x] 保持 duty-based 正式 AI员工命名，不恢复非正式协调员名称。
- [x] 保持 tenant_id + shop_id 隔离。
- [x] 不伪造订单、客户、财务或 AI 结果。

## 员工映射

- AI运营协调官：聚合全局 AI任务、待确认数量、异常数。
- 经营数据分析员：销售、营收、排行、经营查询相关任务。
- 库存风控专员：库存入库/出库/预警相关任务。
- 商品档案管理员：商品档案、SKU、商品维护相关指标。
- 经营策略顾问：基于真实流水和库存活动生成建议。

## 验收

- [x] focused 后端测试覆盖员工状态字段。
- [x] `PYTHONPATH=backend pytest backend/tests/test_v2_pc_dashboard_overview_http_flow.py -q` 通过。
- [x] H5 `npm run build` 通过。
- [x] Docker 8001 热更新并浏览器验证首页员工卡显示真实状态，无 console error、无横向溢出。
- [x] git diff/status 检查，只提交 I2 相关文件。
- [x] commit + push。

## 安全边界

- I2 只读聚合，不新增业务写路径。
- 高风险写操作仍必须走 confirmation-first。
- 不提交 dashboard.jpg、.env、SQLite DB 或 generated dist。
