# Business 架构与设计图片索引

生成位置：`docs/architecture-images/`

说明：这些图基于当前仓库真实模块扫描和最近提交 `24bf8d4 feat: improve h5 mobile experience` 生成。所有图为 SVG，可直接在浏览器打开，适合核对细节与后续继续维护。

> image2.0 生成封面曾尝试调用，但当前环境缺少 FAL_KEY，因此本次以可精确核对的 SVG 架构图为主。

| 文件 | 主题 | 覆盖内容 |
|---|---|---|
| [`00-system-overview.svg`](00-system-overview.svg) | 系统总览 | 端到端整体架构：H5、FastAPI、AI、业务服务、数据层、Docker、Provider |
| [`01-backend-modular-monolith.svg`](01-backend-modular-monolith.svg) | 后端模块化单体 | main.py、API Routes、Domain Services、模型、治理服务 |
| [`02-h5-frontend-architecture.svg`](02-h5-frontend-architecture.svg) | 前端信息结构 | React H5 页面、设计系统、AI 工作台、移动端响应式 |
| [`03-ai-native-confirmation-flow.svg`](03-ai-native-confirmation-flow.svg) | AI-native confirmation-first 流程 | 查询快路径、写操作草稿、老板确认、落账和复盘 |
| [`04-data-model-multitenancy.svg`](04-data-model-multitenancy.svg) | 数据模型与多租户 | tenant/shop 隔离、核心模型、治理与媒体模型 |
| [`05-inventory-ledger-projection.svg`](05-inventory-ledger-projection.svg) | 库存账本与投影 | 不可变 LedgerEvent 与 StockSnapshot 投影 |
| [`06-deployment-runtime.svg`](06-deployment-runtime.svg) | Docker 部署运行态 | Dockerfile、多阶段构建、8001、静态目录、外部访问 |
| [`07-security-observability-exports.svg`](07-security-observability-exports.svg) | 安全、审计、导出 | 认证、RBAC、request_id、AuditLog、ExportJob、生产预检 |
| [`08-commercial-business-loop.svg`](08-commercial-business-loop.svg) | 商业闭环 | 老板问 AI 到销售/采购/库存/财务/复盘的真实闭环 |
| [`09-provider-integration-map.svg`](09-provider-integration-map.svg) | Provider 集成图 | LLM、多模态、短信、对象存储与未来替换方向 |

## 建议核对顺序

1. `00-system-overview.svg`：先确认整体认知是否正确。
2. `03-ai-native-confirmation-flow.svg`：确认 AI 原生体验是否符合“AI 不直接落账”的原则。
3. `04-data-model-multitenancy.svg` 与 `05-inventory-ledger-projection.svg`：确认数据边界和库存账本设计。
4. `01-backend-modular-monolith.svg` 与 `02-h5-frontend-architecture.svg`：确认前后端实现边界。
5. `06-deployment-runtime.svg`、`07-security-observability-exports.svg`、`09-provider-integration-map.svg`：确认上线部署、治理与外部 Provider 现状。

## 维护规则

- 后续新增 API、模型、Provider 或前端页面时，应同步更新对应 SVG。
- 图中不得写入 API Key、token、cookie、数据库连接串等敏感信息。
- `dashboard.jpg` 是参考图，未纳入本目录。
