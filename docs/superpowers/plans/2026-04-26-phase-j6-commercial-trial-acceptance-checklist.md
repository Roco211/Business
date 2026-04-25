# Phase J6 商用试运行验收清单

日期：2026-04-26
分支：`hermes/ai-native-saas-rewrite`

## 背景

Phase I 已完成 AI-native 体验闭环，Phase J1-J5 已补齐执行复盘、新手引导、真实通知中心、经营日报详情、执行复盘列表。下一步需要把“能试用、能验收、能判断生产前差距”的能力显性化，避免老板只看到很多页面，但不知道哪些能力已经达到商用试运行标准。

## 目标

1. 新增 H5「试运行验收」页面，把核心能力按验收项展示。
2. 每个验收项标明状态：已通过、可试运行、生产前补强。
3. 验收项覆盖：登录/租户上下文、商品、库存、销售、采购、客户、财务、AI Command Center、任务审批、通知中心、经营日报、执行复盘、审计、CSV导出、Docker部署、生产安全边界。
4. 新增文档报告，作为当前项目进度与商用试运行验收依据。
5. 不伪造业务数据，不展示假订单/假客户/假财务；页面只展示能力清单、真实计数与已验证证据。

## 安全边界

- 本阶段不新增业务写操作。
- 不自动审批 confirmation。
- 不修改库存/销售/采购/财务真相。
- 不读取 `.env`，不输出 token/secret。
- Provider trial 仍保持显式 opt-in。

## H5 页面设计

页面名称：`试运行验收`

核心模块：

1. 验收总览
   - 可试运行能力数
   - 生产前补强项数
   - AI-native 闭环项数
   - 当前部署状态

2. 核心业务闭环
   - 登录与门店上下文
   - 商品管理
   - 库存账本与快照
   - 销售单
   - 采购单
   - 客户复购
   - 财务流水

3. AI-native 闭环
   - AI Command Center
   - AI草稿生成
   - 任务中心审批
   - 通知中心
   - 经营日报
   - 执行复盘

4. 商用硬化与部署
   - 多租户/门店隔离
   - confirmation-first
   - 审计日志
   - CSV导出
   - request_id错误追踪
   - Docker 8001部署
   - readiness/preflight
   - Provider trial安全边界

## 红灯契约

在实现前运行静态检查，确认以下内容不存在：

- `Page` 类型中没有 `trial-acceptance`
- 导航中没有 `试运行验收`
- 页面中没有 `CommercialTrialAcceptancePage`
- 页面中没有 `商用试运行验收清单`

## 验收命令

```bash
python3 -m compileall -q backend/app
PYTHONPATH=backend pytest backend/tests/test_v2_pc_dashboard_overview_http_flow.py -q backend/tests/test_v2_commercial_modules_http_flow.py -q backend/tests/test_v2_chat_http_confirmation_flow.py -q
cd apps/h5 && npm run build
```

浏览器验收：

- 登录 8001
- 左侧导航点击「试运行验收」
- 页面包含：商用试运行验收清单、核心业务闭环、AI-native闭环、商用硬化与部署、生产前补强
- console error = 0
- 无横向溢出

## Checklist

- [x] 工作区检查与现有能力发现
- [x] 红灯契约检查通过失败
- [x] H5 页面与入口实现
- [x] 验收报告整理
- [x] build / pytest / Docker / 浏览器验证
- [ ] 精确 stage / commit / push
