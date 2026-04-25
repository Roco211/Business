# Phase J4：AI经营日报详情与历史复盘

## 背景

I5 已在首页提供今日经营参谋日报摘要，J3 已把日报/待确认/库存风险纳入通知中心。当前日报还停留在首页卡片，老板无法进入完整详情，也无法查看历史复盘。

## 目标

- 后端新增日报详情与历史接口，继续使用真实销售、库存、confirmation、AI执行复盘数据聚合。
- H5 新增“AI经营日报”详情页，从首页日报卡片和通知中心可进入。
- 支持查看近 7 天历史日报列表，历史项允许数据较少但必须来自真实业务查询。
- 日报强调 AI-native：经营策略顾问汇总，多 AI 员工分段，证据、风险、下一步行动、执行复盘清晰展示。

## 安全边界

- 日报只读，不执行写操作。
- 不伪造销售、库存、客户、财务、AI任务数据。
- 涉及销售/采购/库存写操作仍必须进入 confirmation-first。
- 查询必须限定 tenant_id 与 shop_id。
- 不输出 token、secret、`.env` 或连接串。

## 后端契约

新增：

- `GET /api/v2/pc-dashboard/daily-reports/today`
- `GET /api/v2/pc-dashboard/daily-reports/history?days=7`

今日详情返回：

- `report_date`
- `generated_at`
- `title`
- `generated_by`
- `summary`
- `business_health`
- `sections`
- `next_actions`
- `risk_notes`
- `execution_recaps`
- `timeline`
- `history`
- `evidence`

历史返回：

- `items[]`
- 每项包含 `report_date`、`summary`、`business_health`、销售额、销售笔数、低库存、待确认任务、跳转路由。

## 前端验收

- 侧边栏/首页日报卡片可进入 AI经营日报详情页。
- 详情页展示完整日报、历史日报、执行复盘、证据来源。
- 无历史数据时显示真实空状态。
- 点击下一步建议可跳转到任务中心/库存/工作台等现有页面。
- 8001 热更新后浏览器 console 0 error，无横向溢出。

## 验收清单

- [ ] 失败契约测试先出现：日报详情接口尚未存在时返回 404。
- [ ] 后端契约测试通过。
- [ ] H5 TypeScript build 通过。
- [ ] 后端相关回归通过。
- [ ] Docker 8001 热更新并健康检查通过。
- [ ] 浏览器验证日报详情页、历史列表、跳转和 console 0 error。
- [ ] 精确提交并推送，不提交 `dashboard.jpg`。
