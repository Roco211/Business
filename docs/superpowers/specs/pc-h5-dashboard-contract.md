# PC/H5 Dashboard Product Contract

## Purpose

This contract adapts `dashboard.jpg` into a truthful, backend-backed PC/H5 commercial dashboard for Business. The first version must look like an AI-native SaaS workbench, but every visible operational number must come from the current V2 backend or be marked as coming soon.

## Official AI Role Names

Do not use the former informal coordinator nickname in the commercial PC/H5 product. Use official duty-based role names:

1. AI运营协调官
   - Duties: global command entry, task orchestration, pending confirmation routing, today priority summary.
   - Former informal role: coordinator.

2. 经营数据分析员
   - Duties: revenue summary, sales transaction count, sales ranking, daily revenue trend, abnormal movement hints.

3. 库存风控专员
   - Duties: low-stock detection, stock risk warning, replenishment suggestion, stock movement monitoring.

4. 商品档案管理员
   - Duties: product CRUD, SKU/barcode/unit completeness, item status, item audit entry.

5. 经营策略顾问
   - Duties: rule-based first-stage suggestions, evidence/risk explanation, suggested next action.

Future roles after backend domains exist:
- 客户服务专员: requires customer-service conversation backend.
- 营销活动策划师: requires marketing campaign backend.
- 财务对账专员: requires finance/reconciliation backend.
- 售后处理专员: requires order/after-sales backend.

## MVP Navigation

Enabled:
- 工作台
- 商品管理
- 库存管理
- AI助手
- 任务中心

Coming soon:
- 客户管理
- 营销中心
- 财务对账
- 应用市场

## MVP Dashboard Metrics

Top KPI cards:

1. 今日销售额
   - Source: stock_out ledger revenue for current tenant/shop and current day.
   - Backend fallback if daily exact value is unavailable: dashboard summary period value with label adjusted by frontend.

2. 今日销售笔数
   - Source: stock_out ledger transaction count.
   - Must not be labeled 今日订单量 until real order domain exists.

3. 低库存商品
   - Source: low stock alerts from stock snapshots and item thresholds.

4. 待确认任务
   - Source: pending V2Confirmation rows in current execution context.

Unsupported labels for MVP:
- 今日订单量
- 新增客户数
- 客户咨询数
- 售后申请数
- 待发货订单

These require future order/customer/customer-service domains.

## AI-Native Requirements

The PC/H5 dashboard must not be a traditional SaaS dashboard with AI decorations. It must include:

1. Global command entry
   - Label: “问AI运营协调官” or “交给AI运营协调官处理”.
   - Example hints: 查库存、看销售额、生成补货建议、确认入库任务.

2. Today top priorities
   - Show up to 3 priority cards.
   - Each card includes title, reason, severity, evidence, next action.

3. AI employee cards
   - Show official role name, status, key metrics, and recent activity.
   - Status values: working, attention_needed, idle, degraded.

4. AI suggestions
   - Each suggestion must include:
     - title
     - summary
     - evidence
     - risk
     - confidence or priority
     - action label
     - action type
     - whether confirmation is required

5. Confirmation-first action rule
   - AI suggestions and AI assistant messages must not directly mutate inventory/business truth for high-risk actions.
   - They must create or route to confirmation drafts; ledger/snapshot changes happen only after approval.

6. Work activity transparency
   - Show what AI roles and users did today: pending confirmations, approved confirmations, stock-in/out ledger events, item changes, and generated suggestions.

## Backend Contract: GET /api/v2/pc-dashboard/overview

Response envelope:

```json
{
  "data": {
    "store": {
      "tenant_id": "tenant_1",
      "shop_id": "shop_1",
      "shop_name": "开心小店",
      "plan_label": "本地演示版"
    },
    "user": {
      "account_id": "acct_1",
      "display_name": "老板",
      "role_label": "店主"
    },
    "kpis": [
      {
        "key": "today_sales_amount",
        "label": "今日销售额",
        "value": 3685.9,
        "unit": "元",
        "trend_label": "基于库存出库流水",
        "status": "ready"
      }
    ],
    "ai_employees": [
      {
        "key": "operations_coordinator",
        "name": "AI运营协调官",
        "description": "统筹待确认任务、今日重点和AI指令分发",
        "status": "working",
        "metrics": [
          {"label": "待确认任务", "value": 3, "unit": "个"}
        ],
        "primary_action": {"label": "查看任务", "route": "/tasks"}
      }
    ],
    "top_priorities": [
      {
        "id": "priority_low_stock",
        "title": "优先处理低库存商品",
        "reason": "当前有3个商品低于安全库存",
        "severity": "high",
        "evidence": ["库存风控专员检测到低库存商品"],
        "action": {"label": "查看库存预警", "route": "/inventory?filter=low-stock"}
      }
    ],
    "suggestions": [
      {
        "id": "suggestion_low_stock",
        "type": "inventory_replenishment",
        "title": "建议生成补货清单",
        "summary": "有商品低于安全库存，建议优先补货",
        "evidence": ["低库存商品数: 3"],
        "risk": "补货建议基于当前库存阈值，未包含供应商交期",
        "confidence": "medium",
        "requires_confirmation": true,
        "action": {"label": "查看详情", "route": "/inventory?filter=low-stock"}
      }
    ],
    "activities": [
      {
        "id": "activity_1",
        "time_label": "09:30",
        "actor_name": "库存风控专员",
        "summary": "检测到低库存商品",
        "impact": "需要补货",
        "route": "/inventory?filter=low-stock"
      }
    ],
    "todos": [
      {
        "key": "pending_confirmations",
        "title": "待确认AI任务",
        "count": 3,
        "severity": "high",
        "route": "/tasks"
      }
    ],
    "notifications": {
      "unread_count": 0
    }
  }
}
```

## Empty States

If no sales:
- Show “今天还没有销售流水，完成一次出库后这里会自动更新。”

If no low stock:
- Show “库存状态良好，暂无低库存商品。”

If no pending confirmations:
- Show “暂无待确认AI任务。”

If unsupported nav is clicked:
- Show “该模块即将上线，当前版本先聚焦商品、库存和AI经营助手。”

## Commercial Guardrails

- No fake customer/order/consultation/after-sale metrics in MVP.
- No direct mutation from AI suggestion cards.
- All protected requests must use both Authorization and X-Context-Token.
- All dashboard queries must be tenant/shop scoped.
- Soft-deleted items are excluded from current dashboard views but remain visible in audit history.
