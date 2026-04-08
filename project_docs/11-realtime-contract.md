# 11. 实时事件与 WebSocket 合同

本文件补齐当前蓝图里最容易卡实现的一块：

**聊天页、确认卡、OCR 结果和库存回写，到底通过什么 WebSocket 合同实时同步。**

---

## 1. 设计目标

当前实时层只解决四件事：

- 聊天页尽快收到新消息和结果卡
- 任务状态变化可实时回写
- 待确认生成和解决可实时回写
- 库存事件写入后，工作台和账本能及时失效刷新

当前阶段不通过 WebSocket 做：

- 发送业务消息
- 流式 token 输出
- 多会话复用的复杂订阅总线

---

## 2. 连接入口

当前阶段统一定义为：

- `WS /api/v1/ws/sessions/:session_id?token=<mock_token>`

说明：

- 采用 `session_id` 粒度订阅
- 因为当前阶段仍是 `Mock Auth`，允许通过 query token 连接
- 进入试点前，再升级为更正式的鉴权方式

---

## 3. 基本原则

### 3.1 REST 负责“真相拉取”

REST 负责：

- bootstrap session
- 拉历史消息
- 拉待确认
- 拉库存列表
- 拉审计时间线

### 3.2 WebSocket 负责“增量回写”

WebSocket 只负责：

- 新增事件通知
- 状态变化通知
- 触发前端 query invalidation

### 3.3 事件只追加，不原地修改历史消息

当前 MVP 默认：

- 结果卡是新消息
- 确认卡是新消息
- OCR 结果卡是新消息

而不是：

- 在旧消息上做复杂 patch

---

## 4. 统一事件包结构

```json
{
  "event_id": "evt_01HY9X...",
  "seq": 12,
  "event_type": "task.updated",
  "session_id": "sess_01HY9X...",
  "task_run_id": "task_01HY9X...",
  "message_id": null,
  "occurred_at": "2026-04-03T14:22:31.123Z",
  "data": {}
}
```

字段说明：

- `event_id`
  - 全局唯一事件 id
- `seq`
  - session 内单调递增序号
- `event_type`
  - 事件类型
- `session_id`
  - 当前工作群会话
- `task_run_id`
  - 若事件属于任务流程则必带
- `message_id`
  - 若事件对应新消息则带上
- `occurred_at`
  - UTC 时间
- `data`
  - 结构化 payload

### 4.1 `event_id / seq` 的来源

当前 MVP 不使用通用事件总线，也不依赖进程内内存计数。

统一方案：

- `event_id`
  - 来自 `session_stream_events.event_id`
- `seq`
  - 来自 `session_stream_events.seq`
- 每个 session 的最新序号维护在：
  - `sessions.last_event_seq`

### 4.2 事务生成规则

对所有**业务事件**统一执行：

1. 先在同一事务中写业务真相
   - 例如 `messages` / `task_runs` / `confirmations` / `inventory_events`
2. 锁定对应 `sessions` 行
3. 将 `sessions.last_event_seq + 1`
4. 插入一条 `session_stream_events`
5. 事务提交后再推送 WebSocket

这样做的目的：

- 保证 `seq` 在单 session 内严格递增
- 保证事件顺序与数据库真相顺序一致

### 4.3 传输级事件的特殊规则

下面两类事件是**传输级事件**，不新占用 sequence：

- `session.ready`
- `stream.keepalive`

它们的规则是：

- 可以携带当前最新 `seq`
- 但不会创建新的 `session_stream_events` 记录

客户端判断断档时，应只对**业务事件**做严格断档检查。

---

## 5. MVP 必须实现的事件类型

| event_type | 用途 |
|---|---|
| `session.ready` | 客户端连接成功后的初始化确认 |
| `message.created` | 有新消息、新结果卡、新确认卡 |
| `task.updated` | `TaskRun` 状态变化 |
| `confirmation.created` | 新待确认生成 |
| `confirmation.resolved` | 确认已通过或已拒绝 |
| `ocr.updated` | OCR 状态完成或失败 |
| `inventory.updated` | 库存事件或纠错事件已写入 |
| `alert.updated` | 低库存提醒状态变化 |
| `stream.keepalive` | 保活事件 |
| `error` | 流程级错误通知 |

---

## 6. 关键 payload 约定

### 6.1 `message.created`

```json
{
  "event_type": "message.created",
  "data": {
    "message_type": "result-card",
    "actor_type": "agent",
    "actor_id": "xiaoya",
    "preview_text": "红牛目前还剩 2 罐，已经是低库存。"
  }
}
```

### 6.2 `task.updated`

```json
{
  "event_type": "task.updated",
  "data": {
    "status": "awaiting-confirmation",
    "task_type": "voice-stock-in",
    "error_code": null
  }
}
```

### 6.3 `confirmation.created`

```json
{
  "event_type": "confirmation.created",
  "data": {
    "confirmation_id": "conf_01HY9X...",
    "confirmation_type": "new-item",
    "summary": "这个商品我需要您确认一下名称、数量和价格。"
  }
}
```

### 6.4 `inventory.updated`

```json
{
  "event_type": "inventory.updated",
  "data": {
    "item_id": "item_01HY9X...",
    "inventory_event_id": "inv_evt_01HY9X...",
    "current_stock": 3,
    "unit": "箱"
  }
}
```

---

## 7. 客户端订阅与处理规则

### 7.1 ChatScreen

在下面时机建立连接：

1. 调用 `POST /api/v1/sessions/bootstrap`
2. 拿到 `session_id`
3. 建立对应的 session stream

收到事件后处理建议：

- `message.created`
  - 追加或失效 `useSessionMessagesQuery`
- `task.updated`
  - 刷新当前任务状态
- `confirmation.created`
  - 刷新 `usePendingConfirmationsQuery`
- `confirmation.resolved`
  - 关闭当前确认 UI 并刷新消息流

### 7.2 DashboardScreen

推荐不单独开第二条连接，优先复用同一条 session stream。

收到下面事件后失效：

- `inventory.updated`
- `alert.updated`
- `confirmation.created`
- `confirmation.resolved`

对应刷新：

- summary
- low stock
- pending confirmations

### 7.3 LedgerScreen

同样优先复用同一条 session stream。

收到下面事件后失效：

- `inventory.updated`
- `confirmation.resolved`

对应刷新：

- inventory items
- audit logs

---

## 8. 重连策略

当前 MVP 默认策略：

- 首次失败：`1s`
- 第二次失败：`2s`
- 第三次失败：`5s`
- 后续最大回退：`10s`

如果连续 3 次失败：

- 前端展示轻提示：
  - `实时连接已断开，正在重试`

一旦重连成功：

- 强制失效并重新拉取：
  - 消息列表
  - 待确认列表
  - 库存列表
  - 审计时间线

---

## 9. 序号与补偿规则

客户端必须记录最近一次收到的 `seq`。

若出现：

- `seq` 断档
- 长时间未收到 `stream.keepalive`
- 重连后任务状态不一致

则客户端直接进入补偿逻辑：

- 不尝试自己修补缺失事件
- 统一走 REST 全量同步当前页面关键数据

---

## 10. 服务端实现约束

当前实时层必须满足：

- 只有服务端能发布事件
- 事件先持久化业务真相，再发 WebSocket
- 业务事件的 `event_id / seq` 必须来自数据库，不允许由 WebSocket 进程自己生成
- 事件发布失败不允许回滚已成功提交的数据库事务
- WebSocket 推送失败要记日志，但不影响主业务完成

---

## 11. 当前阶段明确不做的实时复杂度

- 业务消息通过 WebSocket 上行
- SSE 与 WebSocket 双栈并存
- token 级流式模型回显
- 多 session 复用一个复杂订阅协议
- 离线事件回放服务

本文件的目标很明确：

**先把“session 级事件流 + query invalidation”做稳，就足够支撑聊天产品体验。**
