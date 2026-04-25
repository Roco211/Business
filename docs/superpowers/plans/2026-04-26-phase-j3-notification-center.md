# Phase J3：真实通知中心

## 背景

J1 已让任务审批后有执行复盘，J2 已让新用户通过一分钟流程体验完整 AI-native 闭环。当前缺口是：待确认任务、库存风险、经营日报重点散落在首页、任务中心和库存页，老板需要自己找。

J3 目标是增加一个真实通知中心，把“需要老板注意的事情”统一收拢起来。

## 目标

- 后端 `GET /api/v2/pc-dashboard/overview` 返回 `notifications` 真实聚合，而不是 `{ unread_count: 0 }`。
- 通知来源只使用当前已有事实：pending confirmation、低库存、经营日报风险/下一步建议、近期任务状态。
- 前端顶部通知入口可打开通知中心抽屉。
- 通知可引导跳转到任务中心、库存管理、工作台等页面。
- 不引入假客服、假订单、假外部推送数据。

## 安全边界

- 通知中心只展示和导航，不直接执行库存、销售、采购、财务写操作。
- 高风险操作仍必须进入任务中心 confirmation-first 审批。
- 所有后端聚合必须限定 `tenant_id` + `shop_id`。
- 不引入真实外部推送、Web Push、飞书推送；J3 只做站内通知中心。

## 实施步骤

- [x] 发现现有通知/待办/日报/低库存能力。
- [x] 写 J3 计划文档。
- [x] 扩展 PC dashboard HTTP 测试，先断言通知中心契约失败。
- [x] 后端实现 `notifications.items`、`unread_count`、`attention_count`、`generated_at`。
- [x] 前端类型扩展。
- [x] H5 顶部通知按钮打开通知中心抽屉。
- [x] 通知动作支持跳转页面，展示来源员工、优先级、证据和操作按钮。
- [x] 后端测试、H5 build、Docker 8001 热更新、浏览器验收。
- [x] 精确提交并推送。

## 通知契约草案

```json
{
  "notifications": {
    "unread_count": 2,
    "attention_count": 2,
    "generated_at": "2026-04-26T00:00:00",
    "items": [
      {
        "id": "notification_pending_confirmations",
        "type": "confirmation",
        "title": "有AI任务等待确认",
        "summary": "当前有1个AI草稿等待老板确认",
        "severity": "high",
        "source_employee": "AI运营协调官",
        "route": "/tasks",
        "action_label": "去确认",
        "evidence": ["待确认任务数: 1"],
        "created_at": "2026-04-26T00:00:00"
      }
    ]
  }
}
```

## 验收标准

- PC dashboard 测试断言通知中心包含 pending confirmation 与低库存通知。
- H5 顶部通知入口显示未读数量，点击打开“通知中心”。
- 通知项包含来源员工、严重程度、证据、行动按钮。
- 点击“去确认”能进入任务中心。
- 浏览器 console 0 error，无横向溢出。
- 不提交 `dashboard.jpg`、`.env`、本地数据库、dist、tsbuildinfo。
