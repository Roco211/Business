# Phase L1 + L2 AI-native 体验重构计划

## 背景

用户反馈当前 Business 虽然完成了大量后端和商用硬化能力，但普通用户体验仍然不像 AI 原生产品：Dashboard 缺少明显对话入口，Chat 没有真正接入 LLM，UI 有拼装感，普通界面暴露了开发期文本和接口。

本阶段先聚焦 L1 + L2，不继续推进 HTTPS、短信或更多运维能力。

## 目标

1. 修复 L0：LLM 配置链路，应用必须读取现有 `LLM_PROVIDER_API_URL`、`LLM_PROVIDER_API_KEY`、`LLM_PROVIDER_MODEL`。
2. L2：Chat 后端优先走真实 LLM，LLM 负责自然语言理解和基于真实工具结果生成回答。
3. L2：未知/模糊输入不能再粗暴回复“不理解，请按指定格式”，应由 AI 自然追问或给经营建议。
4. L1：Dashboard 顶部变成 AI-first 输入入口，普通用户一进入就知道可以直接问 AI。
5. 保持 confirmation-first：涉及库存写操作仍只生成待确认任务，不直接落账。
6. 本阶段不输出任何 API Key、token、secret 或连接串。

## 范围

### 本阶段包含

- LLM provider 配置兼容修复。
- LLM smoke/初始化契约测试。
- Chat 路由回答链路调整：真实数据查询结果交给 LLM 做自然语言解释。
- General Chat 兜底改为 LLM 经营助手回答。
- Dashboard AI 输入入口和 AI Page 对话体验优化。

### 本阶段不包含

- 真实短信接入。
- HTTPS/域名部署。
- 全量 UI 设计系统重构。
- 复杂工具调用框架或多 agent runtime 重写。

## 验收标准

1. 本地配置存在有效 LLM 时，`get_llm_service()` 初始化为真实 provider，`_use_mock=False`。
2. `/api/v2/chat` 对“今天生意怎么样？”这类自然语言能返回经营助手式回复，不再返回“不理解您的意思”。
3. 查询营业额、热销、库存预警等真实数据后，回复由 LLM 基于真实数据解释。
4. 库存写入类自然语言仍生成 pending confirmation，审批前不改库存。
5. Dashboard 顶部有明显 AI 对话入口，快捷问题直接进入 AI 处理。
6. 后端测试通过，H5 build 通过，Docker 8001 热更新后浏览器无 console error。
