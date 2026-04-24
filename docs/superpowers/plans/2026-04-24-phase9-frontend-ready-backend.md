# Phase 9 推进计划：前端就绪后端完善

> **目标**: 在不依赖外部火山引擎 API Key 的前提下，将后端打磨到可对接前端的成熟度。

---

## 当前状态

- Phase 8 基础设施: ✅ 完成 (Catalog/Ledger/Chat SSE/验收测试)
- 真实 AI 能力: ⏳ 等待 API Key
- 前端对接: ⏳ 需要 API 文档 + 契约稳定

---

## 任务清单

### Task 1: Chat SSE 体验优化
**文件**: `backend/app/api/v2/routes/chat.py`
**目标**:
- [ ] 修复 UTF-8 字符截断问题（当前 chunk_size=2 可能截断中文）
- [ ] 添加多轮会话上下文管理（session-based history）
- [ ] AI 员工角色标签（营业数据员/库存守护员/销售分析员）

### Task 2: 端到端场景测试脚本
**文件**: `backend/scripts/test_phase8_scenarios.py`
**目标**:
- [ ] Voice Stock Query 完整链路测试
- [ ] Photo Stock Query 完整链路测试
- [ ] Receipt OCR 完整链路测试
- [ ] Chat 多轮对话测试

### Task 3: API 契约文档
**文件**: `backend/docs/api-contract-v2.md`
**目标**:
- [ ] 整理所有 43 个 V2 路由的输入/输出契约
- [ ] 标注认证方式（Bearer + X-Context-Token）
- [ ] 提供前端 SDK 调用示例

### Task 4: 性能基线建立
**文件**: `backend/scripts/benchmark_v2_apis.py`
**目标**:
- [ ] 各 API 延迟基线测试
- [ ] SSE 首包延迟测量
- [ ] 生成性能报告

---

## 执行方式

使用 superpowers:subagent-driven-development 或并行执行。

**预估**: 3-4 小时
**优先级**: Task 1 > Task 2 > Task 3 > Task 4
