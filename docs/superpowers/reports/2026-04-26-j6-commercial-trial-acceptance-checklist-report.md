# Business J6 商用试运行验收清单报告

日期：2026-04-26
分支：`hermes/ai-native-saas-rewrite`
阶段：Phase J6

## 结论

Business 当前已经具备“商用试运行”入口：可以让老板按真实流程试用登录、经营工作台、商品、库存、销售、采购、客户、财务、AI Command Center、AI任务审批、通知中心、经营日报、执行复盘、审计导出与 Docker 部署能力。

注意：这里的结论是“可商用试运行”，不是“正式规模化生产已全部完成”。正式商用前仍建议继续 Phase K：RBAC、Redis限流、异步导出、结构化日志告警、HTTPS/域名、真实短信验证码、PostgreSQL生产验证等。

## 本阶段新增内容

### 1. H5 新增「试运行验收」页面

入口：左侧导航 `试运行验收`

页面标题：`商用试运行验收清单`

页面分为四块：

1. 验收总览
   - 可试运行能力
   - AI-native闭环
   - 生产前补强
   - 部署状态

2. 核心业务闭环
   - 登录与门店上下文
   - 商品管理
   - 库存账本与快照
   - 销售单闭环
   - 采购单闭环
   - 客户复购分析
   - 财务流水

3. AI-native闭环
   - AI Command Center
   - AI草稿生成
   - 任务中心审批
   - 真实通知中心
   - AI经营日报
   - AI执行复盘

4. 商用硬化与部署
   - 多租户/门店隔离
   - 关键操作审计
   - CSV导出
   - request_id错误追踪
   - Docker 8001部署
   - readiness/preflight
   - Provider trial安全边界
   - 生产前补强

### 2. 页面坚持真实数据边界

页面使用已有真实后端聚合数据与当前 H5 状态：

- `overview.store`
- 商品数量
- 库存快照数量
- 库存流水数量
- 销售单数量
- 供应商数量
- 采购单数量
- 客户数量
- 财务流水数量
- 财务汇总
- pending confirmations 数量
- notifications 数量
- daily advisor report 摘要
- execution recap 总数

不新增假订单、假客户、假财务，不伪造业务结果。

### 3. 商业化状态表达

每个验收项标明状态：

- `已通过`：已有明确能力、验证或安全边界；
- `可试运行`：适合老板按试运行流程使用；
- `生产前补强`：正式规模化生产前需要进一步完善。

## 涉及文件

- `apps/h5/src/App.tsx`
  - 新增 Page：`trial-acceptance`
  - 左侧导航新增：`试运行验收`
  - 新增组件：`CommercialTrialAcceptancePage`
  - 新增组件：`AcceptanceSection`
  - 新增验收项状态模型

- `apps/h5/src/styles.css`
  - 新增试运行验收页面样式
  - 新增验收卡片、总览卡、结论区域样式
  - 保持与当前浅色、圆角、AI员工卡片风格一致

- `docs/superpowers/plans/2026-04-26-phase-j6-commercial-trial-acceptance-checklist.md`
  - J6 实施计划与安全边界

- `docs/superpowers/reports/2026-04-26-j6-commercial-trial-acceptance-checklist-report.md`
  - 本报告

## 已覆盖能力清单

### 核心业务闭环

| 能力 | 当前状态 | 说明 |
|---|---|---|
| 登录与门店上下文 | 已通过 | 演示登录、租户、门店上下文可用 |
| 商品管理 | 可试运行 | 新增、列表、软删除 |
| 库存账本与快照 | 可试运行 | ledger 不可变事实 + snapshot 投影 |
| 销售单闭环 | 可试运行 | 销售单创建、扣库存、记收入 |
| 采购单闭环 | 可试运行 | 采购单创建、入库、记支出 |
| 客户复购分析 | 可试运行 | 客户档案与订单聚合 |
| 财务流水 | 可试运行 | 收入、支出、退款等真实流水 |

### AI-native闭环

| 能力 | 当前状态 | 说明 |
|---|---|---|
| AI Command Center | 已通过 | 首页自然语言经营入口 |
| AI草稿生成 | 已通过 | 销售/采购/库存写操作先生成 pending confirmation |
| 任务中心审批 | 已通过 | 老板确认后才落账 |
| 真实通知中心 | 已通过 | 聚合真实 pending、库存风险、日报建议 |
| AI经营日报 | 已通过 | BFF 聚合真实证据生成 |
| AI执行复盘 | 已通过 | 只展示已审批且落账的 execution_result |

### 商用硬化与部署

| 能力 | 当前状态 | 说明 |
|---|---|---|
| 多租户/门店隔离 | 已通过 | tenant_id + shop_id 限定 |
| 关键操作审计 | 已通过 | 销售、采购、客户、导出等写审计 |
| CSV导出 | 已通过 | 销售/采购/财务/库存流水导出 |
| request_id错误追踪 | 已通过 | 500响应与日志可追踪 request_id |
| Docker 8001部署 | 已通过 | `business-backend` 提供 H5 + API |
| readiness/preflight | 已通过 | ready_count=18、missing_count=0 |
| Provider trial安全边界 | 生产前补强 | 默认关闭真实 provider 访问，必须显式 opt-in |
| 正式生产能力 | 生产前补强 | RBAC、HTTPS、日志告警等仍建议继续 |

## 验证记录

### 1. 红灯契约

实现前运行静态契约检查，确认 J6 页面不存在：

```bash
python3 - <<'PY'
from pathlib import Path
text = Path('apps/h5/src/App.tsx').read_text()
required = ['trial-acceptance', '试运行验收', 'CommercialTrialAcceptancePage', '商用试运行验收清单']
missing = [item for item in required if item not in text]
if missing:
    print('missing J6 acceptance contract:', ', '.join(missing))
    raise SystemExit(1)
print('J6 acceptance contract exists')
PY
```

结果：

- `missing J6 acceptance contract: trial-acceptance, 试运行验收, CommercialTrialAcceptancePage, 商用试运行验收清单`
- exit code 1，符合红灯预期。

### 2. 前端构建

命令：

```bash
cd apps/h5 && npm run build
```

结果：

- TypeScript build 通过
- Vite build 通过

### 3. 完整相关回归

命令：

```bash
python3 -m compileall -q backend/app
PYTHONPATH=backend pytest backend/tests/test_v2_pc_dashboard_overview_http_flow.py -q backend/tests/test_v2_commercial_modules_http_flow.py -q backend/tests/test_v2_chat_http_confirmation_flow.py -q
cd apps/h5 && npm run build
```

结果：

- `........ [100%]`，即 8 passed。

### 4. H5 构建复验

命令：

```bash
cd apps/h5 && npm run build
```

结果：

- TypeScript build 通过
- Vite build 通过

### 5. Docker 8001 热更新

命令：

```bash
docker exec business-backend sh -lc 'rm -rf /app/app/static/h5/*'
docker cp apps/h5/dist/. business-backend:/app/app/static/h5/
curl http://127.0.0.1:8001/api/v2/health
```

结果：

- HTTP 200
- `{"data":{"status":"ok","api_version":"v2"}}`

### 6. 浏览器验收

访问：`http://127.0.0.1:8001/`

验证结果：

- 左侧导航可见 `试运行验收`
- 页面包含 `商用试运行验收清单`
- 页面包含 `核心业务闭环`
- 页面包含 `AI-native闭环`
- 页面包含 `商用硬化与部署`
- 页面包含 `生产前补强`
- 页面包含 `J6 验收结论`
- console error = 0
- 无横向溢出

## 下一步建议

进入 Phase K「正式商用前补强」：

1. RBAC：老板、店员、财务等角色权限；
2. 真实短信验证码或第三方登录；
3. PostgreSQL 生产环境验证；
4. Redis 限流与缓存；
5. 异步导出与下载中心；
6. 结构化日志、错误告警、审计检索增强；
7. HTTPS、域名、反向代理与备份恢复演练；
8. 首次开店向导与真实空数据初始化流程。
