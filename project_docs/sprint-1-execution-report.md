# Sprint 1 执行报告 & 下一步建议

**生成时间:** 2026-04-23  
**执行者:** Hermes Agent  
**目标:** 验证 CLI 系统可用性 (Sprint 1)

---

## Sprint 1 执行结果

### 执行状态: ✅ **已通过 Sprint 1 验收标准**

| 检查项 | 状态 | 详细说明 |
|--------|------|----------|
| run_local_demo_smoke.py | ✅ 通过 | Demo snapshot 完整输出，10条消息、3个库存项、4个任务运行、1个低库存预警 |
| run_trial_readiness_check.py | ⚠️ 降级 | Health OK，但整体状态为 degraded（预期：trial_provider_profile 未配置） |
| run_pilot_summary_check.py | ⚠️ 降级 | 4个任务、2个确认、无降级，但缺少 trial_provider_profile |
| run_live_pilot_preflight.py | ⚠️ 降级 | 预期：runtime_mode=local-demo，非 trial 模式 |

### 本地 Demo Smoke (./run_local_demo_smoke.py)

```json
{
  "health_status": "ok",
  "inventory_item_count": 3,
  "inventory_item_names": ["Coca Cola 500ml", "Cola", "Red Bull 250ml"],
  "message_count": 10,
  "open_low_stock_alert_count": 1,
  "open_low_stock_item_names": ["Cola"],
  "pending_confirmation_count": 2,
  "pending_confirmation_types": ["receipt-stock-in-batch", "stock-out"],
  "task_run_count": 4
}
```

**结论:** Demo 数据基础完整，可以支撑演示。

---

## 当前系统状态

### ✅ 运行正常
- FastAPI 后端服务 (port 8001)
- Health check (<5ms)
- V2 API (39 routes)
- SQLite database (aism-dev.db)
- Message/Task/Session 流

### ⚠️ 降级但非阻塞
- ASR/OCR/Vision providers 处于 mock/unset 模式（符合预期，未接入真实API）
- Trial provider profile 未配置（阻止进入 trial 模式，但不影响 demo）

---

## 后端架构覆盖总结

| 阶段 | 状态 | 组件 |
|------|------|------|
| Phase 0-3 | ✅ 完成 | Identity, Tenant, Shop, Message/Task Ledger |
| Phase 4 | ✅ 完成 | Inventory Audit/Commit, V2StockSnapshot |
| Phase 5 | ✅ 完成 | Session Stream, Confirmation, Outbox Worker |
| Phase 6 | ✅ 完成 | Dashboard, Alerts |
| Phase 7 | 🔄 部分 | Receipt OCR ✅, Voice/Photo/Manual/Audit/Alerts ✅ |
| Phase 8 | ✅ 完成 | LLM Provider集成 (OpenAILLMProvider) |

---

## 下一步建议（2个优先级）

### 优先级 P0：推进 Sprint 2 - Pilot Preflight 稳定化

**目标:** 让 run_live_pilot_preflight.py 达到 ready 状态

这需要配置：
1. Trial provider profile（ASR/OCR/Vision provider labels）
2. Calibration dataset/artifacts 目录
3. Allowed live pilot shop IDs
4. 切换到 trial runtime mode

**实施步数:**
```powershell
# Step 1: 配置 trial provider profile
python backend/scripts/apply_trial_calibration.py \
  --asr-provider-label mock \
  --ocr-provider-label mock \
  --vision-provider-label mock \
  --calibration-dataset-dir /tmp/calibration \
  --calibration-artifacts-dir /tmp/artifacts

# Step 2: 设置 cutover 模式
python backend/scripts/set_pilot_cutover.py \
  --mode trial \
  --allowed-shops shop_default

# Step 3: 重新验证
python backend/scripts/run_live_pilot_preflight.py --api-base-url http://127.0.0.1:8001
```

---

### 优先级 P1：启动 Sprint 3 - 交接归档能力

**目标:** 确保 export_pilot_shift_bundle.py 能生成完整可归档包

这包括：
1. 会话消息完整导出
2. 库存操作日志
3. 确认历史记录
4. Task run 审计日志

**验证命令:**
```powershell
python backend/scripts/export_pilot_shift_bundle.py \
  --shop-id shop_default \
  --session-id sess_default \
  --output-dir /tmp/shift-bundle
```

---

## 技术债务与风险

1. **ASR/OCR/Vision Mock 模式** - 当前是 mock，真实生产需接入火山引擎
2. **Login 422 问题** - V2 auth/login 返回 422（schema 需要 email/password/phone/verification 同时存在）[已识别]
3. **Subscription mock / real provider** - 需要整理 provider 状态机

---

## 决策点

请选择下一个 Sprint：

- **A) 执行 Sprint 2** - 配置 trial provider profile，让 preflight 达到 ready
- **B) 执行 Sprint 3** - 完成 shift bundle 导出，验收交接能力
- **C) 修复前置问题** - 先解决 Login 422 和 provider 配置问题
- **D) 切入前端** - 暂停后端，启动 apps/h5 前端

推荐：**A) Sprint 2** - trie 模式稳定化是当前最高 ROI，可以让整条链路从 demo -> trial -> pilot 顺利递进。
