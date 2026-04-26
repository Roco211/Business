# Phase L5：AI-native 端到端真实体验验收

## 目标

验证 Business 对普通老板的核心体验不是“能看页面”，而是能完成真实 AI-native 经营闭环：

1. 手机号 mock 验证码登录。
2. 选择租户和门店上下文。
3. 在 Dashboard/AI 入口直接问“今天生意怎么样？”。
4. AI 基于真实工具数据返回经营解释，不回复“不理解/请按格式”。
5. 输入“我卖了 2 个扳手，帮我记一下”。
6. AI 不直接落账，而是生成待确认销售草稿。
7. 老板审批后真实创建销售单、扣库存、写财务流水、写审计。
8. confirmation 中保留 execution_result，H5 执行复盘页可展示。

## 验收标准

- 后端 HTTP 契约测试覆盖完整链路。
- Docker 8001 smoke 覆盖真实运行服务。
- 浏览器验收覆盖 Dashboard/AI/任务中心/执行复盘路径。
- 写操作仍保持 confirmation-first。
- 不输出 token、API Key、.env、数据库连接串。
- H5 build、后端关键回归、console error 检查均通过。

## 不做

- 不接真实短信，继续 mock 验证码 888888。
- 不让 AI 自动审批或直接落账。
- 不伪造销售、库存、财务数据。
