# Phase B2 Chat 确认优先完成记录

日期：2026-04-25
分支：`hermes/ai-native-saas-rewrite`
状态：已完成

## 背景

V2 后端已经具备 `V2TaskRun`、`V2Confirmation`、确认列表、审批、拒绝等基础能力，但 Chat 写库存路径仍存在安全边界缺口：

- `stock_in` 会直接调用库存入库提交
- `stock_out` 会直接调用库存出库提交
- 这违反“AI 不能直接修改业务真相”的架构原则

本阶段目标是把 Chat 驱动的库存写操作改为 confirmation-first：先创建任务运行（task_run）和待确认单（confirmation），用户确认后再通过已有确认审批 API 落账。

## 本次改动

### 1. Chat stock_in 改为确认优先

文件：`backend/app/api/v2/routes/chat.py`

行为变化：

- 识别到入库意图后，不再直接写库存账本
- 创建 `V2Message` + `V2TaskRun`
- 创建 `V2Confirmation(status=pending, confirmation_type=inventory.stock_in)`
- 返回“待确认单”提示
- 库存快照保持不变

### 2. Chat stock_out 改为确认优先

文件：`backend/app/api/v2/routes/chat.py`

行为变化：

- 库存不足时仍直接返回库存不足错误，不创建确认单
- 库存充足时，不再直接出库
- 创建 `V2Message` + `V2TaskRun`
- 创建 `V2Confirmation(status=pending, confirmation_type=inventory.stock_out)`
- 返回“待确认单”提示
- 库存快照保持不变

### 3. 多租户查询边界收紧

Chat 查找匹配商品时新增 `tenant_id` 限定：

- `V2InventoryItem.tenant_id == context.tenant_id`
- `V2InventoryStockSnapshot.tenant_id == context.tenant_id`
- `V2InventoryStockSnapshot.shop_id == context.shop_id`

## 新增测试

文件：`backend/tests/test_v2_chat_confirmation_first.py`

覆盖：

1. `test_chat_stock_in_creates_pending_confirmation_without_committing_inventory`
   - Chat 入库创建 pending confirmation
   - 不返回“入库成功”
   - 库存快照不变
   - task_run 状态为 `awaiting_confirmation`

2. `test_chat_stock_out_creates_pending_confirmation_without_committing_inventory`
   - Chat 出库创建 pending confirmation
   - 不返回“出库成功”
   - 库存快照不变
   - task_run 状态为 `awaiting_confirmation`

## 验证结果

已通过：

```bash
cd /root/business-clone
PYTHONPATH=backend pytest -q backend/tests/test_v2_chat_confirmation_first.py
# 2 passed

PYTHONPATH=backend python3 -m py_compile backend/app/api/v2/routes/chat.py backend/tests/test_v2_chat_confirmation_first.py

PYTHONPATH=backend pytest -q \
  backend/tests/test_v2_chat_confirmation_first.py \
  backend/tests/test_mvp_acceptance_flows.py::test_acceptance_chat_stock_in_confirmation_flow \
  backend/tests/test_mvp_acceptance_flows.py::test_acceptance_upload_backed_photo_stock_in_remains_confirmation_first
# 4 passed

python3 backend/scripts/test_phase9_scenarios.py
# 5/5 passed

python3 backend/scripts/test_phase8_acceptance.py
# 8/8 passed
```

## 当前剩余后端重点

1. 补一条完整 API 级验收：Chat stock_in/stock_out -> pending confirmation -> approve -> 库存变化
2. 真实 LLM / ASR / OCR / Vision provider 接入
3. Voice / Photo 场景复用 confirmation-first 流程做端到端闭环
4. WebSocket 实时推送 inventory.updated / confirmation.created / alert.updated
