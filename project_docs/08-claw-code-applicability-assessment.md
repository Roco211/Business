# 08. Claw Code 框架适配评估

## 1. 结论先说

`claw-code` 的**框架思想非常值得借**，尤其适合拿来补强你当前文档里已经提出但还没工程化落地的“AI 原生控制平面”。

但它**不适合直接作为这个项目的主框架照搬**。

最合适的做法是：

- 保持当前 `React Native + FastAPI + MySQL + Celery + WebSocket` 主栈不变
- 借鉴 `claw-code` 的运行时思想，在服务端实现一个**面向店铺业务的 agent runtime / orchestration layer**
- 复用的是“控制平面设计”，不是“编码代理工具箱”

一句话总结：

**可借架构，不宜整套迁移；应做领域化改造，而不是直接嵌入。**

## 2. Claw Code 本质上是什么

从当前仓库内容看，`claw-code` 本质上是一个**本地编码代理运行时**，核心能力集中在：

- 会话运行时
- 工具注册与工具调用
- 权限与升级批准
- 指令与上下文加载
- 子代理调度
- Hook / Plugin 扩展
- 会话压缩与恢复

它解决的问题是：

- 模型如何在一个可控循环里调用工具
- 高风险工具如何被守门
- 长上下文如何被压缩继续运行
- 运行时如何加载本地规则、技能和插件

它不是一个库存业务系统，也不是一个现成的移动端后端框架。

## 3. 为什么它和你的项目有高度“思想匹配”

你的 `project_docs` 已经明确了一个方向：

- 用户前台看到的是少量 AI 员工
- 系统后台真正运行的是会话、任务、守门、工具链和审计

这和 `claw-code` 最强的部分是对齐的。

### 3.1 会话循环可以借

`claw-code` 的核心运行方式不是“LLM 回一句就结束”，而是：

- 用户输入进入会话
- 模型输出文本或工具调用
- 运行时执行工具
- 工具结果再回到会话
- 持续直到本轮完成

这和你的业务非常贴近，因为你不是纯聊天，而是：

- 语音进入任务
- 任务触发 ASR / OCR / 识图 / 库存查询
- 中间可能要确认
- 最终才落账或回执

### 3.2 守门机制可以借

你的项目文档已经明确：

- 高风险动作不能直接写库
- 低置信动作必须确认
- 所有关键写操作必须可追踪

`claw-code` 的权限模式、工具级权限要求、执行前审批，和你的 `Policy Guard` 思路天然同构。

### 3.3 角色合同可以借

你在 `07` 里已经把“员工不是人格，而是角色合同”说得很清楚了。

`claw-code` 的子代理、技能、工具白名单，给了一个很好的工程映射：

- 角色 = 员工合同
- Skill = 能力包
- Tool = 原子动作
- Allowed Tools = 角色边界

### 3.4 长任务压缩与恢复可以借

你的产品里会出现很多长链路：

- 语音入库
- OCR 抽字段
- 待确认
- 老板修改
- 写入库存事件
- 回写聊天和账本

这类链路天然需要：

- 任务摘要
- 会话压缩
- 中断恢复

`claw-code` 的 compaction 思路对这里很有参考价值。

### 3.5 插件 / 能力包思路可以借，但不该过早上线

你的 PRD 明确说首版不做第三方插件市场，但长期又希望能力可以扩展。

`claw-code` 的插件、Hook、技能体系，适合拿来做你后续的：

- 能力包
- 官方扩展员工
- 供应商适配器
- OCR / ASR / 视觉策略切换层

## 4. 为什么它不适合直接搬过来

### 4.1 目标领域不一样

`claw-code` 的工具面向：

- shell
- 文件读写
- 代码搜索
- notebook
- prompt/runtime 辅助

而你的项目真正的领域工具应该是：

- `transcribe_audio`
- `recognize_product`
- `extract_receipt_fields`
- `query_inventory`
- `create_confirmation`
- `append_inventory_event`
- `append_audit_log`
- `push_session_update`

也就是说，核心运行时形态相似，但**工具域完全不同**。

### 4.2 当前主实现是 Rust 本地 CLI，不是你要的业务后端

你的项目已定栈是：

- `FastAPI`
- `MySQL`
- `Celery + Redis`
- `WebSocket`

而 `claw-code` 当前主产品面是：

- Rust 本地 CLI
- 编码代理运行时
- 轻量会话 HTTP/SSE 辅助服务

它没有为你的业务准备好：

- MySQL 业务模型
- TaskRun / Confirmation / AuditLog 持久化
- Celery 任务编排
- 店铺规则引擎
- 库存事件事务边界

### 4.3 它的开放式代理能力不应该直接碰业务真相

编码代理允许比较开放的探索和工具使用，这是它的优势。

但在你的场景里：

- 库存是业务真相
- 审计是责任边界
- OCR / 识图是低置信来源

所以你不能让一个通用子代理像在代码仓库里一样自由探索后直接改真相数据。

你需要的是：

- 受限工具集
- 显式确认规则
- 任务状态机
- 可审计写入器

### 4.4 插件生命周期和 shell 型扩展要谨慎

`claw-code` 的插件体系非常适合开发工具，但如果直接照搬到业务系统，会带来额外风险：

- 扩展执行边界过大
- Hook 太容易演变成黑盒副作用
- 业务链路排障会变难

对于店铺业务系统，插件能力应该后置，而且优先做：

- 受控 provider adapter
- 受控 capability package

不应该一开始就是任意命令型插件。

## 5. 最推荐的借法：只借“控制平面”

最值得借的不是“多智能体热闹感”，而是下面这套控制平面：

### 5.1 Runtime Loop

把一轮任务统一抽象成：

`Input -> Route -> Build Context -> Run Tools -> Guard -> Confirm or Commit -> Reply`

### 5.2 Tool Contract

每个工具必须有：

- 输入 schema
- 输出 schema
- 风险等级
- 是否允许直接执行
- 是否要求确认
- 是否写审计

### 5.3 Role Contract

每个员工必须有：

- 可见身份
- 域边界
- 可用 skill
- 可用 tool
- 禁止动作
- 必须确认的动作
- 可移交对象

### 5.4 Session + Task 双层状态

不要只存聊天消息。

要把：

- `ConversationSession`
- `SessionMessage`
- `TaskRun`
- `Confirmation`
- `InventoryEvent`
- `AuditLog`

串成一个统一执行账本。

### 5.5 Summary / Recovery

会话太长时，不是简单截断，而是压成：

- 当前任务摘要
- 最近确认状态
- 未完成动作
- 当前店铺规则
- 当前上下文对象

## 6. 对你这个项目的具体落地建议

建议在 FastAPI 服务端新增一个独立的编排层，例如：

```text
backend/app/agent_runtime/
  contracts/
    employee_profiles.py
    tool_specs.py
    policy_rules.py
  core/
    router.py
    context_builder.py
    orchestrator.py
    reviewer.py
    summarizer.py
  tools/
    asr.py
    vision.py
    ocr.py
    inventory_query.py
    inventory_write.py
    confirmations.py
    audit.py
  transports/
    websocket_push.py
  persistence/
    task_runs.py
    confirmations.py
    audit_logs.py
```

### 6.1 MVP 先实现四个内部角色就够了

- `Router`
- `PolicyGuard`
- `ToolRunner`
- `Summarizer`

`Reviewer` 可以先只在高风险写库前启用。

### 6.2 前台只保留两个员工

- 小雅
- 老李

这一点不需要因为 `claw-code` 的多代理能力而改动。

### 6.3 Tool 不要直接复用 claw 的工具集

你应该重建业务工具层，而不是把 `bash/read_file/edit_file` 一类工具平移到产品后端。

### 6.4 权限模型要转译成“业务风险等级”

可以把 `claw-code` 的权限思路翻译成：

- `read_only`
  - 只查库存、只读解释
- `needs_confirmation`
  - 新商品、低置信识别、缺价格
- `committable`
  - 已通过确认，可以落账
- `forbidden`
  - 越界角色禁止动作

### 6.5 会话压缩要面向任务，不要只面向对话

`claw-code` 的 compaction 偏“对话摘要”。

你的版本应该优先保留：

- 当前任务类型
- 当前识别候选
- 当前待确认字段
- 当前是否允许写入
- 最近一条库存事件

## 7. 我给你的最终判断

### 适配度

- 架构思想适配度：高
- 直接代码复用价值：低
- 作为主框架整体替换：不建议
- 作为服务端 AI 编排层的设计参考：强烈建议

### 推荐决策

建议你把 `claw-code` 定位成：

- **参考框架**
- **运行时设计样本**
- **控制平面启发来源**

而不是：

- 直接嵌入的现成后端
- 直接替代 `FastAPI + Celery` 的主框架

## 8. 下一步最值得做什么

如果继续推进，最有价值的下一步不是继续抽象概念，而是把它落成一版**面向店铺业务的 runtime 设计稿**，至少补齐这三份内容：

1. `EmployeeProfile / ToolSpec / PolicyRule` 数据结构
2. `TaskRun -> Confirmation -> InventoryEvent -> AuditLog` 的执行状态机
3. `Router / Guard / Runner / Summarizer` 的 FastAPI 服务端模块边界

这样你就真正把 `claw-code` 学到的东西，转成了这个项目能落地的工程框架。
