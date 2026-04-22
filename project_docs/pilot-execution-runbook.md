# Pilot 执行运行手册

## 当前主线

整套系统的主验收先看 [系统 CLI 可用性验证清单](./system-cli-validation-checklist.md)。`backend/scripts/run_system_check.py` 已经是当前推荐入口；需要 drill-down 时，再按下面的 leaf commands 串起来执行。

本页继续保留 pilot summary、shift bundle 和回滚姿态，属于 CLI 路线里的 leaf 运行手册，不再以 Android/Expo 为主线。

## 每日 Pilot 复核流程

1. 优先运行系统 CLI wrapper；若 wrapper 返回 degraded，再按下面的 leaf commands 逐项定位。
2. 确认 API 已启动，trial profile 仍然配置正确。
3. 运行 readiness CLI。
4. 运行当前复核窗口的 pilot summary CLI。
5. 导出一份 shift bundle JSON 包，用于交接或事故复盘。
6. 只有在 readiness、summary 和 shift bundle export 都成功后，才继续 pilot traffic。

常用命令：

```powershell
python backend/scripts/run_system_check.py --mode pilot --api-base-url http://127.0.0.1:8001 --hours 24 --output-dir C:\secure\pilot\shift-bundles
python backend/scripts/run_trial_readiness_check.py
python backend/scripts/run_pilot_summary_check.py
python backend/scripts/export_pilot_shift_bundle.py --hours 24 --output-dir C:\secure\pilot\shift-bundles
```

常用覆盖参数：

```powershell
python backend/scripts/run_pilot_summary_check.py --hours 24
python backend/scripts/run_pilot_summary_check.py --max-fallback-rate 0.05 --max-low-confidence-rate 0.20
python backend/scripts/export_pilot_shift_bundle.py --hours 8 --api-base-url http://127.0.0.1:8001
```

## 切换模式含义

- `closed`：guardrails 会阻断 live cutover 行为，操作员应把 pilot traffic 视为已暂停
- `shadow`：在 guardrails 之下观察 providers，任何状态变更都必须通过确认
- `open`：在已批准的档位、artifact 和预检对齐后，cutover 进入 live 状态

如果不确定，先从 `open` 回退到 `shadow`。若事故严重或未解决，就回退到 `closed`。

## Pilot Summary CLI 契约

CLI 会先跑 readiness，再跑受保护的 pilot summary route。它会输出一个紧凑 JSON 对象，字段包括：

- `overall_status`
- `readiness`
- `pilot_summary.time_window`
- `pilot_summary.task_totals`
- `pilot_summary.total_task_count`
- `pilot_summary.telemetry_task_count`
- `pilot_summary.confirmations`
- `pilot_summary.confirmation_rate`
- `pilot_summary.rejection_rate`
- `pilot_summary.fallback_count`
- `pilot_summary.fallback_rate`
- `pilot_summary.low_confidence_count`
- `pilot_summary.low_confidence_rate`
- `pilot_summary.provider_failures`
- `pilot_summary.trial_provider_profile`
- `pilot_summary.reasons`
- `thresholds`

退出行为：

- 退出 `0`：readiness 为绿且 pilot summary verdict 为绿
- 退出 `1`：readiness 降级、pilot summary 降级、缺少 trial profile 元数据、出现 provider failures、阈值被突破、认证失败、非 200 响应，或返回封装异常

## 如何解读降级结果

当 `pilot_summary.reasons` 中出现以下任一项时，把 pilot summary 视为 degraded：

- `trial_provider_profile_missing`
- `provider_failures_present`
- `fallback_rate_exceeded`
- `low_confidence_rate_exceeded`

即使 pilot summary 的指标都在阈值内，只要 readiness 不是绿，CLI 也会判定为 degraded。

分母说明：

- `confirmation_rate` 继续使用 `total_task_count`
- `fallback_rate` 和 `low_confidence_rate` 使用 `telemetry_task_count`，也就是当前 `trial_provider_profile` 在窗口内带 telemetry 的独立 task run 数

## 建议的每日复核节奏

- 日初：在打开 pilot traffic 前先跑 readiness 和 24 小时 pilot summary。
- 班中：任何 provider 事故或阈值告警之后，重新跑 pilot summary。
- 日终：导出并归档最终 shift bundle，保留当班生效的 calibration artifact id。

## 必需的 Shift Bundle 导出流程

每次交接和每条事故时间线都要运行一次：

```powershell
python backend/scripts/export_pilot_shift_bundle.py --hours 24 --output-dir C:\secure\pilot\shift-bundles
```

Bundle 内容：

- readiness JSON（等同于 `run_trial_readiness_check` 的 payload）
- preflight JSON（等同于 `run_live_pilot_preflight` 的 payload）
- 当前 `GET /api/v1/system/pilot-control` JSON
- pilot summary JSON（等同于 `run_pilot_summary_check` 的 payload）
- 紧凑 manifest，包含文件名、时间戳、shop id、mode、profile 和 artifact id

目标位置要求：

- 使用仓库外的私有位置（推荐），或者
- 使用已明确加入 gitignore 的仓库路径

如果上游 artifact 有任何降级，导出仍然会成功，但 bundle 会标记 `overall_status=degraded` 并附带 `degraded_reasons`。

## 回滚姿态

如果任一操作员 CLI 退出码非 0：

1. 在原因查清前，停止开启新的 pilot traffic。
2. 调查期间先把 cutover 回退到 `shadow`：

```powershell
python backend/scripts/set_pilot_cutover.py --mode shadow --note "rollback: investigating incident"
```

3. 如果事故仍未解决，就把 cutover 完全关闭：

```powershell
python backend/scripts/set_pilot_cutover.py --mode closed --note "rollback: cutover closed pending fix"
```

4. 保留并把最新的 shift bundle 导出附到事故工单。
5. 如果问题和 calibration rule 有关，重新应用上一份已批准的 calibration report：

```powershell
python backend/scripts/apply_trial_calibration.py --report C:\secure\pilot\artifacts\last-known-good.json
```

6. 恢复前重新运行 `run_trial_readiness_check.py`、`run_live_pilot_preflight.py` 和 `run_pilot_summary_check.py`。
7. 只通过受控路径重新打开 cutover：

```powershell
python backend/scripts/set_pilot_cutover.py --mode open --artifact-path C:\secure\pilot\artifacts\last-known-good.json --note "resume after rollback"
```

备注：

- 不要把 `/api/v1/system/demo/bootstrap` 当成 trial 模式的恢复步骤。
- 任何非空的 `provider_failures` map 在说明根因之前，都应视为 pilot 事故。
- 如果 `trial_provider_profile` 缺失或为空，就不能把这次运行当作已校准的 pilot traffic。
- 如果 summary 降级或收到回滚信号，完整的事故响应流程请继续看 [pilot 事故恢复运行手册](./pilot-incident-recovery-runbook.md)。
