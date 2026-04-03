# 09. 当前施工范围与落地边界

本文件解决的问题不是“产品最终会变成什么”，而是：

**基于当前 `project_docs`，下一轮工程落地到底先做什么、不做什么，以及什么叫“已经可以开工”。**

---

## 1. 当前施工目标

当前这轮实现目标统一定义为：

**做一个“可演示的端到端 mock 闭环 MVP 骨架”，而不是一步到位接入全部真实 AI 能力。**

换句话说：

- 基础工程和业务骨架要真实存在
- 数据库、对象存储、任务编排、WebSocket 都按真实系统方式搭
- ASR / OCR / 识图 / 自由推理能力，当前阶段先通过可替换的 mock provider 承接

这样做的目的有两个：

1. 先验证整个系统链路和边界是否成立
2. 避免在状态机、确认链、账本和审计还没稳住前，就被供应商接入细节拖慢

---

## 2. 当前阶段的默认实施决策

### 2.1 实施层级

当前实施层级默认定为：

- `B. 可演示的端到端 mock 闭环`

不是：

- 只做文档或空骨架
- 也不是直接接真实 ASR / OCR / 识图供应商

### 2.2 AI 能力策略

当前阶段统一采用：

- `mock-first provider strategy`

即：

- 路由、ASR、OCR、识图、总结都先有稳定接口
- 默认实现先走 mock / fixture
- 后续可以无痛替换成真实 provider

### 2.3 认证策略

当前阶段继续使用：

- `Mock Auth + 单店单老板`

默认上下文：

- 只有一个默认店铺
- 只有一个老板账号
- 所有会话默认落在一个工作群里

### 2.4 落地顺序

当前阶段推荐：

- **后端骨架优先**
- React Native 最小壳层随后接入

原因：

- 这个产品的核心复杂度在会话、任务、确认、账本和审计
- 如果后端合同不先钉死，前端很容易做成“看起来像聊天，实际上没有真相层”的假壳

---

## 3. 当前阶段明确纳入范围的内容

### P0 业务闭环

必须先做成：

- 默认工作群 session bootstrap
- 媒体上传申请
- 发送消息
- `voice-stock-in`
- `voice-stock-query`
- 确认链路
- `InventoryEvent` 写入
- `AuditLog` 写入
- WebSocket 回写聊天状态

### P1 多模态闭环

在 P0 稳定后纳入：

- `photo-stock-in`
- `photo-stock-query`
- `receipt-ocr`
- OCR 低置信字段高亮
- 新商品 / 低置信识别进入确认态

### P2 账本闭环

在 P0/P1 后补齐：

- 库存列表
- 审计时间线
- 人工纠错
- 低库存提醒

### 工程骨架

当前阶段必须一起落地：

- FastAPI API 工程
- SQLAlchemy + Alembic
- Celery + Redis Worker 骨架
- MinIO 上传链路
- WebSocket session stream
- React Native 工程骨架

---

## 4. 当前阶段明确不纳入范围的内容

以下内容统一视为后续阶段，不阻塞当前开工：

- 多店铺
- 多角色账号体系
- 手机号 OTP
- 多供应商并行路由
- 流式模型输出
- 第三方插件市场
- 平台化员工包 / 能力包市场
- 复杂离线同步
- 真正的实时通话
- 任意自由子代理

---

## 5. 建议的仓库落地结构

当前工作区还没有真正的移动端和业务后端工程，因此建议按下面结构开始施工：

```text
apps/
  mobile/
backend/
  app/
    api/
    agent_runtime/
    db/
    models/
    repositories/
    services/
    workers/
    websocket/
  tests/
infra/
  docker/
project_docs/
showcase_app/
```

说明：

- `apps/mobile` 负责 React Native 客户端
- `backend` 负责 FastAPI、数据库、runtime 和 worker
- `infra` 负责 Docker Compose、环境模板和本地依赖编排
- `showcase_app` 保持为蓝图展示入口，不作为业务后端本体

---

## 6. 推荐施工顺序

### 第 1 步：先立服务端骨架

先完成：

- FastAPI app 结构
- MySQL 模型与 Alembic
- Mock Auth
- `/health`
- `/api/v1/sessions/bootstrap`

### 第 2 步：把消息与任务账本立起来

完成：

- `sessions`
- `messages`
- `task_runs`
- `confirmations`

### 第 3 步：把 runtime loop 跑通

完成：

- Router
- Policy Guard
- Tool Runner
- Summarizer
- Mock ASR / OCR / 识图 provider

### 第 4 步：打通 P0 闭环

完成：

- 语音入库
- 语音查询
- 待确认生成
- 确认后写库存事件
- 审计写入
- WebSocket 回写

### 第 5 步：接 React Native 最小壳层

先做：

- 3 个主页面
- session bootstrap
- 消息流拉取
- WebSocket 订阅
- 结果卡 / 确认卡渲染

### 第 6 步：再补多模态与账本

最后补：

- 拍照建档
- 拍照查询
- OCR
- 账本
- 人工纠错

---

## 7. 当前阶段的完成定义

只有同时满足下面这些条件，才算“当前蓝图已经被落成第一版工程骨架”：

- 能启动 FastAPI、Worker、MySQL、Redis、MinIO
- 能 bootstrap 出默认工作群 session
- 能通过消息接口创建 `TaskRun`
- `voice-stock-in` 能走到确认态
- 确认通过后能写入 `InventoryEvent` 和 `AuditLog`
- `voice-stock-query` 能返回只读结果卡
- 聊天页能通过 WebSocket 收到状态更新
- 所有 AI 能力都经过 provider interface，而不是散落在业务代码里

---

## 8. 当前阶段不需要再等待的决策

以下问题在当前施工阶段不再阻塞开工：

- 真实 ASR 最终选哪家
- 真实 OCR 最终选哪家
- 真实识图最终选哪家
- 是否做正式登录系统

因为本阶段默认答案已经确定：

- 先 mock
- 先单店单老板
- 先把系统骨架和闭环做稳

---

## 9. 真正会阻塞下一阶段的事项

进入真实试点前，仍然需要补充：

- 真实 provider 选型与评测
- 正式账号与店铺上下文
- 生产环境对象存储与密钥管理
- 更严格的风控规则与运营策略

本文件的结论可以总结成一句话：

**当前阶段先落一个“真实骨架 + mock AI 能力”的闭环系统，用它验证蓝图，而不是一开始就追求供应商接入完成度。**
