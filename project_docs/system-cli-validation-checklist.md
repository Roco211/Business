# 系统 CLI 可用性验证清单

## 说明

当前优先目标是把现有 backend scripts 串成一条统一的系统可用性验证链。

`backend/scripts/app_cli.py` 已经落地，当前应优先使用它作为顶层 CLI 入口。

`backend/scripts/run_system_check.py` 继续保留为底层统一检查入口；当你需要直接看单次检查 JSON 或单独集成某个 mode 时，可以继续直接调用它。

`backend/scripts/app_cli.py demo` 则负责把本地 demo smoke 的真实状态直接打印出来，方便先看见应用，再看检查结果。

当前不再把 Android/Expo 当作主验收路径。

## 1. 统一入口

优先运行：

```powershell
python backend/scripts/app_cli.py up --profile local-demo
python backend/scripts/app_cli.py demo
python backend/scripts/app_cli.py check --mode local-demo
```

期望：

- `up` 会准备本地 runtime、迁移 SQLite，并启动 API 服务
- `demo` 会调用本地 demo smoke 并输出紧凑 JSON 快照，里面包含健康状态、shop/session 标识和核心计数
- `check` 会调用底层统一检查入口并输出紧凑 JSON
- 只有所选场景 ready 时退出码才为 `0`

trial / pilot 推荐顺序：

```powershell
python backend/scripts/app_cli.py up --profile trial
python backend/scripts/app_cli.py cutover --mode shadow
python backend/scripts/app_cli.py check --mode trial
python backend/scripts/app_cli.py check --mode pilot
```

如果顶层 CLI 返回 degraded，再按下面的统一检查命令和 leaf commands 向下钻取。

## 2. 底层统一检查入口

直接运行：

```powershell
python backend/scripts/run_system_check.py --mode local-demo --api-base-url http://127.0.0.1:8001
python backend/scripts/run_system_check.py --mode trial --api-base-url http://127.0.0.1:8001
python backend/scripts/run_system_check.py --mode pilot --api-base-url http://127.0.0.1:8001 --hours 24 --output-dir C:\secure\pilot\shift-bundles
```

期望：

- `local-demo` / `trial` 输出 `mode`、`overall_status`、`checks`
- `pilot` 额外输出 `reasons`，并在 `checks` 中展开 `trial_readiness`、`live_pilot_preflight`、`pilot_summary` 与 `shift_bundle`
- 只有所选场景 ready 时退出码才为 `0`

## 3. 本地 demo smoke

运行：

```powershell
python backend/scripts/run_local_demo_smoke.py --api-base-url http://127.0.0.1:8001
```

期望：

- 能返回 JSON
- `health_status=ok`
- 演示摘要字段与 demo 预期一致
- 退出码为 `0`

## 4. trial readiness

运行：

```powershell
python backend/scripts/run_trial_readiness_check.py --api-base-url http://127.0.0.1:8001
```

期望：

- JSON 中包含 `health_status`、`runtime_mode`、`readiness_status`、`overall_status`
- `overall_status` 在 trial 环境应为 `ready`
- 退出码为 `0`

## 5. live pilot preflight

运行：

```powershell
python backend/scripts/run_live_pilot_preflight.py --api-base-url http://127.0.0.1:8001 --artifact-path C:\secure\pilot\artifacts\pilot-v1_report_20260407T090000000000Z.json
```

期望：

- JSON 中包含 `overall_status`、`runtime_mode`、`trial_provider_profile`、`cutover_mode`
- `reasons` 为空时才可视为 ready
- 退出码为 `0`

## 6. pilot summary check

运行：

```powershell
python backend/scripts/run_pilot_summary_check.py --api-base-url http://127.0.0.1:8001 --hours 24
```

期望：

- JSON 中包含 `overall_status`
- `pilot_summary.time_window`、`pilot_summary.task_totals`、`pilot_summary.confirmations`、`pilot_summary.provider_failures` 可读
- 退出码为 `0`

## 7. shift bundle export

运行：

```powershell
python backend/scripts/export_pilot_shift_bundle.py --hours 24 --output-dir C:\secure\pilot\shift-bundles
```

期望：

- 能导出完整 bundle
- bundle 可用于交接或事故复盘
- 输出应标明 readiness、preflight、pilot summary 与 manifest

## 8. 最终结论

只要下面四项全部稳定，当前阶段就可以认为“系统可用性验证”成立：

- 本地 demo smoke 稳定
- trial readiness 稳定
- live preflight 稳定
- pilot summary / shift bundle 稳定

如果其中任意一项不稳定，优先修后端或 CLI 输出契约，而不是回到 Android/Expo 主线。
