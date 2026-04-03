# 00. 最终技术选型

## 1. 结论

当前 MVP 的最终技术栈已经确定，不再作为开放问题继续讨论。

前端：

- `React Native + TypeScript`
- `Expo Managed + EAS`
- `React Navigation`
- `TanStack Query`
- `Zustand`
- `React Hook Form + Zod`
- `expo-audio`
- `expo-camera + expo-image-picker + expo-file-system`

后端：

- `FastAPI`
- `MySQL`
- `SQLAlchemy 2.0 async + asyncmy`
- `Alembic`
- `Celery + Redis`
- `WebSocket`

基础设施：

- `MinIO`
- `Docker Compose`
- `Mock Auth + 单店单老板`
- `Jest + React Native Testing Library`
- `pytest`
- `结构化日志 + Sentry`

## 2. 选型总表

| 层 | 已选技术 | 用途 | 为什么现在选它 |
|---|---|---|---|
| 移动端运行时 | React Native + TypeScript | App 开发 | 跨平台、成熟、适合当前 MVP |
| RN 工作流 | Expo Managed + EAS | 构建、调试、发版 | 首版媒体能力接入快，工程阻力最小 |
| 导航 | React Navigation | 三主页面 + 弹层 | 对当前信息架构足够稳定直接 |
| 服务端数据缓存 | TanStack Query | 接口缓存、失效、重试 | 适合移动端服务端状态管理 |
| 本地状态 | Zustand | 录音态、面板态、会话 UI 态 | 比 Redux 更轻，适合首版 |
| 表单 | React Hook Form + Zod | 确认卡、纠错表单 | 性能稳定，校验边界清晰 |
| 录音 | expo-audio | 语音采集 | 与 Expo 集成顺手，符合 MVP 节奏 |
| 相机与文件 | expo-camera / expo-image-picker / expo-file-system | 商品拍照、单据拍照、文件处理 | 覆盖多模态采集最关键场景 |
| 后端框架 | FastAPI | REST API / WebSocket | 与异步编排和 Python AI 生态匹配 |
| 数据库 | MySQL | 主业务数据存储 | 团队已选定，满足首版结构化数据需求 |
| ORM | SQLAlchemy 2.0 async + asyncmy | MySQL 访问层 | 边界清晰，异步能力足够 |
| 迁移 | Alembic | 数据库 schema 迁移 | 首版必须有可追踪迁移机制 |
| 队列 | Celery + Redis | ASR / OCR / 识图异步任务 | 比 FastAPI 内置后台任务更适合重任务 |
| 实时通信 | WebSocket | 聊天状态和任务回执 | 更接近聊天产品体验 |
| 对象存储 | MinIO | 语音、图片、单据文件 | 本地和试点环境更可控 |
| 认证 | Mock Auth + 单店单老板 | MVP 登录简化 | 先验证产品，不先做完整账号系统 |
| 部署 | Docker Compose | API / Worker / MySQL / Redis / MinIO 编排 | 首版部署简单可控 |
| 测试 | Jest + RNTL / pytest | 前后端测试 | 能覆盖 MVP 最核心链路 |
| 监控 | 结构化日志 + Sentry | 错误追踪与排障 | 低成本获得可观测性 |

## 3. 为什么这套栈适合当前 MVP

### 3.1 因为你的 MVP 不是普通 CRUD

当前 MVP 的真实复杂度来自这几件事：

- 语音是主入口
- 图片识别必须进 MVP
- 进货单 OCR 必须进 MVP
- 聊天页需要接近微信体验
- 写操作需要确认和审计
- 识别和 OCR 不是纯同步短请求

因此这套技术必须同时满足：

- 移动端能稳定采集语音和图像
- 后端能做异步任务编排
- 数据库结构适合库存与审计
- 聊天回执能尽量实时

### 3.2 为什么不是更轻的方案

例如以下方案都没有被选：

- `FastAPI BackgroundTasks`
  - 不适合后续越来越重的 OCR、识图、语音处理任务
- `本地磁盘存文件`
  - 对媒体文件管理和后续部署都不友好
- `只做 HTTP 轮询`
  - 可以演示，但不像聊天产品
- `Redux Toolkit`
  - 对当前 MVP 过重
- `Bare React Native`
  - 现在会拖慢首版交付

## 4. 客户端最终选型

### 4.1 客户端主栈

```text
React Native
  + TypeScript
  + Expo Managed
  + EAS
  + React Navigation
  + TanStack Query
  + Zustand
  + React Hook Form
  + Zod
```

### 4.2 客户端媒体栈

```text
expo-audio
expo-camera
expo-image-picker
expo-file-system
```

### 4.3 客户端职责

- 采集语音、商品照片、进货单照片
- 上传媒体
- 展示微信式聊天页
- 展示结果卡、确认卡、OCR 卡
- 提交确认和人工纠错

### 4.4 客户端不负责

- 语音理解结果真相
- OCR 最终抽取真相
- 库存最终落账
- 审计真相存储

## 5. 后端最终选型

### 5.1 后端主栈

```text
FastAPI
  + SQLAlchemy 2.0 async
  + asyncmy
  + Alembic
  + Celery
  + Redis
  + WebSocket
```

### 5.2 后端职责

- 暴露 REST API
- 提供 WebSocket 推送
- 统一会话编排
- 管理 TaskRun / Confirmation / InventoryEvent / AuditLog
- 负责编排 ASR / OCR / 识图
- 统一写库存和审计

### 5.3 为什么 MySQL 仍然成立

因为首版主要是结构化业务数据：

- 商品
- 库存
- 事件
- 确认
- 审计
- 会话消息索引

这些都更适合关系型数据库。

## 6. 对象存储与媒体策略

### 已选

- `MinIO`

### 用法

- 语音录音上传到 MinIO
- 商品图上传到 MinIO
- 进货单图片上传到 MinIO
- 数据库只存 `media_id`、URL、元数据

### 后续升级路径

如果后面上云并扩大试点，可以平滑迁移到：

- `AWS S3`
- 或其他兼容 S3 的对象存储

## 7. 异步任务与实时策略

### 7.1 异步任务

所有较重任务统一走：

```text
FastAPI API -> Celery -> Redis -> Worker
```

适用任务：

- 语音转写
- 商品识别
- 进货单 OCR
- 低置信字段复核
- 结果卡生成

### 7.2 实时回执

聊天页状态更新走：

- `WebSocket`

用法：

- 任务处理中
- OCR 完成
- 识图完成
- 待确认生成
- 确认通过后写回聊天

## 8. 认证与权限策略

### 8.1 MVP 已选方案

- `Mock Auth + 单店单老板`

目标：

- 避免首版被登录系统拖慢
- 先验证语音、多模态、库存链路

### 8.2 当前不做

- 多角色账号系统
- 店员体系
- 多租户权限矩阵
- 手机号 OTP

### 8.3 后续升级路径

若进入真实试点，再升级为：

- 手机号 OTP
- 店铺上下文绑定
- 设备登录与基础权限控制

## 9. 部署与环境

### 9.1 本地开发

推荐：

```text
Expo Dev Server
FastAPI API
Celery Worker
MySQL
Redis
MinIO
```

其中后 5 项统一由 `Docker Compose` 管理。

### 9.2 MVP 试点环境

推荐仍然保持：

- App：`EAS Build`
- 服务端：`Docker Compose + 单台云服务器`

原因：

- 成本低
- 调试简单
- 不会过早引入集群和运维复杂度

## 10. 测试与监控

### 10.1 测试

客户端：

- `Jest`
- `React Native Testing Library`

服务端：

- `pytest`

必须优先覆盖的链路：

- 语音入库
- 语音查询
- 拍照建档
- 拍照查询
- 进货单 OCR
- 人工纠错

### 10.2 监控

已选：

- 结构化日志
- `Sentry`

至少覆盖：

- 前端崩溃
- 接口异常
- Worker 异常
- OCR / 识图失败

## 11. 当前不选的技术

以下技术明确不进首版默认栈：

- Bare React Native
- Expo Router
- Redux Toolkit
- Formik
- Yup
- aiomysql
- FastAPI BackgroundTasks 作为主异步框架
- 本地磁盘存媒体
- 轮询作为主实时策略
- 完整手机号登录系统
- Kubernetes

## 12. 对后续文档的约束

从现在开始，`project_docs` 里的其他文档都应以本文件为最终技术选型依据。

如果后续需要改栈，应该优先更新本文件，再同步其他文档。

