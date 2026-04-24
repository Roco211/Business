# Phase 7 实施计划：场景迁移与 v1 退场

## 概述

完整 V2 基础架构已完成（阶段 0-6），现在进入**场景迁移**和**v1 退场**阶段。

## 当前状态

| 阶段 | 状态 | 说明 |
|------|------|------|
| 阶段 0 | ✅ 原则冻结 | 已完成 |
| 阶段 1 | ✅ V2 骨架 | API v2 路由已完成 |
| 阶段 2 | ✅ 多租户身份 | V2Identity 模型已存在 |
| 阶段 3 | ✅ 会话运行时 | V2Conversation 已存在 |
| 阶段 4 | ✅ 库存账本 | V2Inventory 已存在 |
| 阶段 5 | ✅ 媒体/AI | V2MediaAI, V2Receipt 已存在 |
| 阶段 6 | ✅ Outbox/Worker | V2Outbox, Projection 已存在 |
| **阶段 7** | ⏳ 场景迁移 | **当前阶段** |
| **阶段 8** | ⏳ v1 退场 | **待执行** |

## 阶段 7：场景迁移

### 已完成场景

1. ✅ **receipt OCR stock in** - `v2_receipt_documents.py` + `v2_receipt_stock_in_drafts.py`

### 待实现场景（优先级 P0）

2. ⏳ **voice stock query** - 语音库存查询
   - ASR 转录语音
   - NLP 意图识别
   - 查询库存快照
   - 流式响应

3. ⏳ **voice stock in** - 语音入库
   - ASR 转录语音
   - 提取商品信息
   - 创建库存事件
   - 确认流程

4. ⏳ **photo stock query** - 照片库存查询
   - OCR/图片识别
   - 匹配库存商品
   - 返回查询结果

5. ⏳ **photo stock in** - 照片入库
   - OCR/图片识别
   - 提取票据信息
   - 创建入库草稿

6. ⏳ **manual correction** - 手动纠错
   - 库存量修正
   - 纠错审批流程
   - 账本事件记录

7. ⏳ **audit browsing** - 审计浏览
   - 查看库存历史
   - 操作日志追溯
   - 数据导出

8. ⏳ **low-stock alerts** - 低库存警报
   - 阈值设定
   - 定期检测
   - 通知推送

## 阶段 8：v1 退场

### 清理任务列表

- [ ] Step 1: 识别 v1 代码路径
- [ ] Step 2: 移除 shop bootstrap
- [ ] Step 3: 移除 owner bootstrap
- [ ] Step 4: 移除 shop=tenant 假设
- [ ] Step 5: 保留 v1 runtime 但标记 deprecated
- [ ] Step 6: 迁移测试到 v2
- [ ] Step 7: 文档更新

## 使用 Superpowers 推进

### 方式 1：子代理驱动开发 (推荐)

```bash
# 为每个场景创建独立子代理
./superpowers delegate --spec docs/superpowers/specs/scenario-voice-stock-query.md
./superpowers delegate --spec docs/superpowers/specs/scenario-voice-stock-in.md
./superpowers delegate --spec docs/superpowers/specs/scenario-photo-stock-query.md
# ...
```

### 方式 2：TDD 自底向上

1. 先写测试 `backend/tests/test_v2_scenario_voice.py`
2. 实现 service `v2_voice.py`
3. 实现 API 路由
4. 验证通过

### 方式 3：单文件极速推进

```bash
# 单场景一次性完成
./superpowers sprint --target phase7-voice-stock-query --parallel
```

## 计划执行步骤

### Step 1: 创建 Phase 7 计划文档
- ✅ 已完成

### Step 2: 创建场景规范文档 (SPECS)
每个场景一个 spec 文件:
- `docs/superpowers/specs/scenario-voice-stock-query.md`
- `docs/superpowers/specs/scenario-voice-stock-in.md`
- `docs/superpowers/specs/scenario-photo-stock-query.md`
- `docs/superpowers/specs/scenario-photo-stock-in.md`
- `docs/superpowers/specs/scenario-manual-correction.md`
- `docs/superpowers/specs/scenario-audit-browsing.md`
- `docs/superpowers/specs/alert-low-stock.md`

### Step 3: 委托子代理并行实现
使用 `delegate_task` 为每个场景创建独立子代理。

### Step 4: 场景验证
运行场景测试套件。

### Step 5: v1 退场
完成所有场景后，执行 v1 退场。

## 预估工作量

| 任务 | 预估时间 |
|------|---------|
| Voice Stock Query | 4h |
| Voice Stock In | 4h |
| Photo Stock Query | 3h |
| Photo Stock In | 3h |
| Manual Correction | 3h |
| Audit Browsing | 3h |
| Low-Stock Alerts | 4h |
| v1 退场 | 4h |
| **总计** | **~28h** |

## 建议的下一步行动

1. **选项 A**: 立即创建所有场景 spec 文档 → 委托子代理并行实现
2. **选项 B**: 先选一个 MVP 场景（Voice Stock Query）完整实现 → 验证模式后批量复制
3. **选项 C**: 先完成 v1 退场清理 → 减少技术债务后再实现新场景

推荐：**选项 B** - Voice Stock Query 作为种子场景，验证完成后用 superpowers 的 pattern 复制到其他场景。
