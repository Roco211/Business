# Phase I5 AI经营参谋日报 MVP

## 背景

Phase I1/I2/I3/I4 已经完成 AI Command Center、AI员工真实状态、AI Task Flow 和销售/采购/库存三类 AI 草稿闭环。I5 的目标是让系统在首页主动给老板一份“今日经营参谋日报”，把销售、库存、待确认任务和下一步建议聚合成可解释的经营复盘。

## 目标

- [x] 复用 `GET /api/v2/pc-dashboard/overview` BFF，不新增前端多接口拼接。
- [x] 后端返回 `daily_advisor_report`，包含标题、生成员工、摘要、健康状态、分段报告、下一步动作、风险提醒和证据。
- [x] 日报只基于真实数据：销售流水、低库存、待确认 confirmation、AI任务/活动聚合。
- [x] 高风险动作仍只跳转任务中心或相关页面，不直接执行写操作。
- [x] H5 首页展示日报卡片，保持浅色紫色 dashboard 风格。
- [x] focused 后端测试覆盖日报契约。
- [x] `python3 -m compileall -q backend/app && PYTHONPATH=backend pytest backend/tests/test_v2_pc_dashboard_overview_http_flow.py -q` 通过。
- [x] H5 `npm run build` 通过。
- [x] Docker 8001 热更新并浏览器验证日报卡片、无 console error、无横向溢出。
- [x] git diff/status 检查，只提交 I5 相关文件。
- [x] commit + push。

## 安全边界

- 日报是经营建议和复盘，不直接修改销售、采购、库存或财务事实。
- 涉及库存/销售/采购写操作的下一步动作只能跳转到任务中心或业务页面，由老板确认后执行。
- 不展示假订单、假客户、假财务数据。
- 保持 tenant/shop 隔离，日报来源继续走已有 BFF 上下文。
