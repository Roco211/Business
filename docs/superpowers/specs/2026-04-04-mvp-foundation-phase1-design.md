# MVP Foundation Phase 1 Design

## 背景

当前仓库已经具备较完整的产品与工程蓝图：

- `AI_Store_Manager_PRD.md` 负责产品目标、范围与成功标准
- `project_docs/00-13` 已经覆盖技术选型、客户端架构、API、数据模型、runtime、实时合同、数据库 schema 与 provider 策略
- `showcase_app/` 和 `AI_Store_Manager_UI.html` 提供了原型展示与说明

但仓库仍停留在“文档 + 展示站”阶段，还没有真正的：

- `apps/mobile` React Native 工程
- `backend` FastAPI / runtime / worker 工程
- `infra/docker` 本地基础设施编排
- 机器可校验的初始合同与最小验证路径

因此，第一子项目不应直接追求完整业务功能，而应先把仓库从“蓝图”推进到“可施工的工程起点”。

## 本阶段目标

Phase 1 的目标是：

**建立一个可运行、可扩展、可版本化的 MVP 工程骨架，并把最关键的蓝图约束固化到代码和配置结构中。**

本阶段完成后，仓库应该满足下面几点：

1. 有明确的移动端、后端、基础设施目录与职责边界
2. 有最小可运行的后端入口与健康检查
3. 有最小可运行的移动端壳层入口
4. 有本地基础设施编排文件，能表达 MySQL / Redis / MinIO / API / Worker 的存在方式
5. 有第一批可执行或可生成的合同落点，避免继续只靠 Markdown 约定
6. 有最小测试与 fixture 骨架，为后续 TDD 打底

## 不在本阶段范围内

本阶段明确不追求：

- 六条业务主链路全部打通
- 真实 ASR / OCR / Vision provider 接入
- 完整账号体系、多店铺、多角色权限
- 完整 runtime orchestration 逻辑实现
- 完整 WebSocket 事件流与数据库迁移落地
- 完整 UI 还原或高保真交互打磨

换句话说，本阶段的产出是“真实工程底座”，不是“可试点的业务成品”。

## 方案选择

本次设计采用之前已选的 `A` 路径：

### 方案 A：工程骨架 + 合同固化 + 最小验证

优点：

- 最适合作为所有后续开发的公共起点
- 能最快把文档转成真实工程结构
- 能同时减少“文档很多但项目还不能开工”的落差
- 更利于 git 分阶段提交与后续多人并行

代价：

- 短期内业务体验提升有限
- 需要克制，不把骨架阶段膨胀成完整产品开发

### 为什么不先选 B / C

- 不先只做后端 runtime：否则移动端与基础设施仍然悬空
- 不先只做文档治理：否则 repo 依然没有真实可施工入口

## 核心设计

### 1. 仓库结构

Phase 1 结束后，仓库应至少形成下面结构：

```text
apps/
  mobile/
backend/
  app/
    api/
    core/
    contracts/
    models/
    runtime/
    workers/
  tests/
    fixtures/
infra/
  docker/
docs/
  superpowers/
    specs/
    plans/
project_docs/
showcase_app/
```

职责划分：

- `apps/mobile`
  - React Native / Expo 工程壳层
  - 仅承接导航、基础页面壳、配置和后续 feature 目录
- `backend/app/api`
  - FastAPI 路由入口与 DTO
- `backend/app/contracts`
  - 首批结构化合同定义
  - 先承接与 Phase 1 相关的健康检查、认证、session bootstrap 等基础合同
- `backend/app/core`
  - 配置、依赖注入、应用工厂等通用设施
- `backend/app/runtime`
  - 先创建目录和边界，不在本阶段实现完整 orchestrator
- `backend/app/workers`
  - Celery worker 入口与任务注册占位
- `backend/tests/fixtures`
  - provider fixture、接口样例、后续 TDD 的最小测试数据
- `infra/docker`
  - `docker-compose`、服务定义、环境模板

### 2. 单一事实源策略

当前仓库存在三种事实来源：

- 产品/工程蓝图：`project_docs/`
- 展示层：`showcase_app/`
- 未来实现层：尚未建立

Phase 1 的规则应明确为：

1. `project_docs/` 仍然是产品与工程意图的源头
2. 实现级合同从本阶段开始进入 `backend/` 代码与配置
3. `showcase_app/` 不再承担新的规则定义职责，只展示已经存在的结论

也就是说，**本阶段不全面重写 showcase，但要停止继续扩大其硬编码事实面的范围。**

### 3. 后端骨架

后端在本阶段要实现的是“可启动的业务服务骨架”，不是完整业务域。

最小要求：

- `FastAPI app factory`
- `/health`
- `/api/v1/auth/mock-login`
- `/api/v1/sessions/bootstrap`
- 配置加载与环境变量边界
- 基础 OpenAPI 暴露

其中：

- `/health` 证明服务可启动
- `mock-login` 与 `sessions/bootstrap` 证明系统已经开始承接文档中的真实业务上下文，而不是纯空壳

### 4. 移动端骨架

移动端在本阶段只做“可运行的 Expo 壳层 + 结构正确的三主页面”。

最小要求：

- Expo + TypeScript 工程初始化
- 基础导航
- `DashboardScreen`
- `ChatScreen`
- `LedgerScreen`
- 用于后续接入的 feature 目录和共享目录

本阶段不要求：

- 录音、相机、上传能力真正接通
- 真实 API 联调
- 微信感细节完整打磨

### 5. 基础设施骨架

`infra/docker` 在本阶段的目的，是把蓝图中的基础依赖显式化。

最小要求：

- `docker-compose.yml`
- MySQL
- Redis
- MinIO
- API 服务
- Worker 服务
- `.env.example`

即使某些服务最初只是最小占位，也必须让目录、命名、环境变量和服务边界先固定下来。

### 6. 合同固化策略

本阶段不追求把 `project_docs/02/03/10/11/12` 全部一次性代码化。

但必须先落第一批“最小可实现合同”：

- `MockLoginResponse`
- `SessionBootstrapResponse`
- 基础错误响应结构
- 健康检查响应结构

这些合同应优先以 **后端代码中的 Pydantic 模型** 作为实现来源，并由 FastAPI 自动生成 OpenAPI。

这样做的原因：

- 比单独手写一份新的 OpenAPI 文档更不容易漂移
- 后续可以逐步从代码生成更完整的合同
- 更适合当前 repo 从“无工程”向“有工程”过渡

### 7. 测试与 fixture 策略

Phase 1 必须建立最小测试基线，而不是等功能多了再补。

最小测试集合：

- 后端健康检查测试
- `mock-login` 路由测试
- `sessions/bootstrap` 路由测试
- 至少一组 fixture 目录骨架：
  - `backend/tests/fixtures/providers/asr/`
  - `backend/tests/fixtures/providers/ocr/`
  - `backend/tests/fixtures/providers/vision/`

这些 fixture 在 Phase 1 可以先只放占位样例或 README 说明，但目录与命名必须先立起来。

### 8. Git 管控策略

本阶段工作应按“可回退的里程碑”提交，而不是一次性堆大改动。

推荐提交节奏：

1. `docs:` 写入设计 spec
2. `chore:` 建立仓库基础目录和配置模板
3. `feat:` 加入最小后端骨架
4. `feat:` 加入最小移动端骨架
5. `test:` 加入最小验证与 fixture 骨架

每个提交都应对应一个清晰结果，而不是混合文档、骨架、测试与杂项修复。

## 数据流与边界

本阶段只需验证最短数据流：

```text
Client shell -> API app -> mock context -> response DTO
```

不进入：

- provider 调用
- runtime 多步编排
- DB 真实写入
- WebSocket 实时事件

这个最短路径的价值在于：

- 验证工程结构成立
- 验证 API 命名与 DTO 形态开始落到代码
- 为下一阶段接入数据库、worker、runtime 留出稳定入口

## 错误处理原则

本阶段只实现最基础的错误边界：

- 配置缺失时快速失败
- API 路由返回统一错误结构
- 目录和环境变量命名保持显式

本阶段不实现：

- 供应商错误码映射
- 复杂库存冲突处理
- runtime 级多步回滚

## 完成定义

Phase 1 只有在满足下面条件时，才算完成：

1. 仓库存在 `apps/mobile`、`backend`、`infra/docker` 基础结构
2. 后端可启动并通过 `/health`
3. 后端存在 `mock-login` 与 `sessions/bootstrap` 的最小实现与测试
4. 移动端存在可启动的三主页面壳层
5. 存在 `docker-compose` 与 `.env.example`
6. 存在初始 fixture 目录骨架
7. 所有新增代码都通过对应最小验证命令

## 后续衔接

Phase 1 完成后，下一阶段的实现计划应继续推进：

1. 数据库模型与 Alembic 初始化
2. `messages / task_runs / confirmations` 落地
3. runtime 最小 loop 落地
4. WebSocket session stream 落地
5. 语音入库与语音查询 P0 闭环

也就是说，Phase 1 是“把工地围起来、通水通电、立施工图”，而不是“把主体结构一次建完”。
