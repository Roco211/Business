# Phase J5：AI执行复盘列表化

## 背景

J1 已在任务审批后即时展示“刚刚完成的AI执行复盘”；J4 已把最近执行复盘聚合进 AI 经营日报。当前还缺少一个独立页面，让老板能像查看员工工作记录一样，系统性查看 AI 今天/最近已完成的业务动作。

## 目标

- 新增后端 AI 执行复盘列表接口，基于真实已审批且已落账的 confirmation.resolution_payload.execution_result 聚合。
- 新增 H5「AI执行复盘」页面，从导航、日报、通知/任务相关入口可进入。
- 页面展示 AI 已完成的任务、影响、下一步入口、证据链、状态分布。
- 继续坚持 confirmation-first：只展示已发生事实，不自动执行任何写操作。

## 安全边界

- 不伪造执行复盘；没有 execution_result 的 confirmation 不纳入已完成列表。
- 只读取当前 tenant_id + shop_id 数据。
- 只展示已 approved / committed 且 execution_result.status == committed 的结果。
- 不允许页面触发自动审批、自动扣库存、自动记账。

## 后端契约

GET /api/v2/pc-dashboard/execution-recaps?limit=20

返回：

```json
{
  "summary": {
    "total_count": 1,
    "sales_order_count": 1,
    "purchase_order_count": 0,
    "inventory_count": 0
  },
  "items": [
    {
      "confirmation_id": "...",
      "task_run_id": "...",
      "kind": "sales_order",
      "status": "committed",
      "summary": "...",
      "effects": ["已创建销售单", "已扣减库存"],
      "next_route": "/sales",
      "created_at": "...",
      "resolved_at": "...",
      "source_employee": "经营数据分析员",
      "intent_type": "sales.order_create",
      "risk_level": "medium",
      "evidence": ["来自已审批AI任务", "已写入业务事实"]
    }
  ]
}
```

## H5 验收

- [x] 左侧导航新增「执行复盘 AI」。
- [x] 页面显示总数、销售/采购/库存分类数。
- [x] 页面列表显示 summary、effects、source_employee、resolved_at、下一步按钮。
- [x] 日报详情里的 AI执行复盘可进入完整列表。
- [x] 浏览器 console error 为 0，无横向溢出。
- [x] 后端测试、H5 build、Docker 8001 热更新通过。
- [x] 提交并推送。
