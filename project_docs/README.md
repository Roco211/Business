# AI数字店铺大管家 - 蓝图与 CLI 验证索引

这套文档同时保留历史的 React Native 首版蓝图和当前的系统 CLI 可用性验证主线。若你的目标是判断整套系统是否可用，请先看下面的“当前主线”；如果你只是回看原始蓝图，再看后面的历史阅读顺序。

## 当前主线

1. [系统 CLI 可用性验证清单](./system-cli-validation-checklist.md)
2. [试运行就绪运行手册](./trial-readiness-runbook.md)
3. [Pilot 执行运行手册](./pilot-execution-runbook.md)

当前推荐从顶层 CLI 开始，而不是直接拼 leaf scripts：

```powershell
python backend/scripts/app_cli.py up --profile local-demo
python backend/scripts/app_cli.py demo
python backend/scripts/app_cli.py check --mode local-demo
```

`demo` 会直接打印当前运行中的本地 demo 快照，方便先看见应用状态，再进入检查。

如果你要体验 trial / pilot 路线，再继续：

```powershell
python backend/scripts/app_cli.py up --profile trial
python backend/scripts/app_cli.py cutover --mode shadow
python backend/scripts/app_cli.py check --mode trial
python backend/scripts/app_cli.py check --mode pilot
```

## 历史蓝图假设

以下内容保留原 React Native 首版方案的前提，只作为历史背景：

- 首版客户端使用 `React Native + TypeScript`
- 使用 `Expo Managed + EAS`
- 后端使用 `FastAPI + MySQL`
- 语音、多模态、OCR 都通过服务端编排
- 客户端负责采集、上传、展示、确认和回执

## 历史蓝图阅读顺序

以下顺序对应原始蓝图脉络，它不代表当前系统验收的执行顺序。

1. [00-final-tech-stack.md](./00-final-tech-stack.md)
2. [01-react-native-architecture.md](./01-react-native-architecture.md)
3. [02-api-contract.md](./02-api-contract.md)
4. [03-data-models.md](./03-data-models.md)
5. [04-client-state-and-flows.md](./04-client-state-and-flows.md)
6. [05-sprint-plan.md](./05-sprint-plan.md)
7. [06-risks-and-decisions.md](./06-risks-and-decisions.md)
8. [07-ai-employee-and-ai-native-system.md](./07-ai-employee-and-ai-native-system.md)
9. [08-claw-code-applicability-assessment.md](./08-claw-code-applicability-assessment.md)
10. [09-implementation-scope.md](./09-implementation-scope.md)
11. [10-runtime-contracts.md](./10-runtime-contracts.md)
12. [11-realtime-contract.md](./11-realtime-contract.md)
13. [12-db-schema.md](./12-db-schema.md)
14. [13-provider-decisions.md](./13-provider-decisions.md)

文档用途：

- `00` 解决“最终栈到底定了什么”
- `01` 解决“项目怎么搭”
- `02` 解决“接口怎么定”
- `03` 解决“数据怎么存”
- `04` 解决“页面和状态怎么跑”
- `05` 解决“开发怎么排期”
- `06` 解决“首版有哪些关键取舍”
- `07` 解决“AI 员工怎么设计、AI 原生系统怎么搭”
- `08` 解决“Claw Code 的哪些思想该借，哪些不该直接搬”
- `09` 解决“当前这轮正式施工到底做什么、不做什么”
- `10` 解决“runtime 合同、tool 合同和状态机怎么落”
- `11` 解决“WebSocket 实时事件到底怎么定义”
- `12` 解决“MySQL 和 Alembic 应该按什么 schema 开工”
- `13` 解决“provider 当前怎么定，何时再切真实供应商”

本目录不替代 PRD。

- `AI_Store_Manager_PRD.md` 继续负责产品目标和范围
- `project_docs/*` 负责工程落地与系统 CLI 验证
