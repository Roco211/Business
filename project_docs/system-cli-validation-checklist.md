# 系统 CLI 可用性验证清单

## 说明

当前优先目标是把现有 backend scripts 串成一条统一的系统可用性验证链。

理想状态是先有 `backend/scripts/run_system_check.py` 作为统一入口。

如果 wrapper 还未落地，先按下面的 leaf commands 手工执行。

当前不再把 Android/Expo 当作主验收路径。

## 1. 本地 demo smoke

运行：

```powershell
python backend/scripts/run_local_demo_smoke.py --api-base-url http://127.0.0.1:8001
```

期望：

- 能返回 JSON
- `health_status=ok`
- 演示摘要字段与 demo 预期一致
- 退出码为 `0`

## 2. trial readiness

运行：

```powershell
python backend/scripts/run_trial_readiness_check.py --api-base-url http://127.0.0.1:8001
```

期望：

- JSON 中包含 `health_status`、`runtime_mode`、`readiness_status`、`overall_status`
- `overall_status` 在 trial 环境应为 `ready`
- 退出码为 `0`

## 3. live pilot preflight

运行：

```powershell
python backend/scripts/run_live_pilot_preflight.py --api-base-url http://127.0.0.1:8001 --artifact-path C:\secure\pilot\artifacts\pilot-v1_report_20260407T090000000000Z.json
```

期望：

- JSON 中包含 `overall_status`、`runtime_mode`、`trial_provider_profile`、`cutover_mode`
- `reasons` 为空时才可视为 ready
- 退出码为 `0`

## 4. pilot summary check

运行：

```powershell
python backend/scripts/run_pilot_summary_check.py --api-base-url http://127.0.0.1:8001 --hours 24
```

期望：

- JSON 中包含 `overall_status`
- `pilot_summary.time_window`、`pilot_summary.task_totals`、`pilot_summary.confirmations`、`pilot_summary.provider_failures` 可读
- 退出码为 `0`

## 5. shift bundle export

运行：

```powershell
python backend/scripts/export_pilot_shift_bundle.py --hours 24 --output-dir C:\secure\pilot\shift-bundles
```

期望：

- 能导出完整 bundle
- bundle 可用于交接或事故复盘
- 输出应标明 readiness、preflight、pilot summary 与 manifest

## 6. 最终结论

只要下面四项全部稳定，当前阶段就可以认为“系统可用性验证”成立：

- 本地 demo smoke 稳定
- trial readiness 稳定
- live preflight 稳定
- pilot summary / shift bundle 稳定

如果其中任意一项不稳定，优先修后端或 CLI 输出契约，而不是回到 Android/Expo 主线。
