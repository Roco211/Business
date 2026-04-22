# 试运行就绪运行手册

## 当前主线

整套系统的主验收已经切到 CLI 路线。优先阅读 [系统 CLI 可用性验证清单](./system-cli-validation-checklist.md)，把它当作总入口；本页只展开 `run_trial_readiness_check.py` 这一 leaf command 及其运行约束。

`backend/scripts/run_system_check.py` 已落地。当前推荐先运行 `python backend/scripts/run_system_check.py --mode trial`；只有在需要单独复核 readiness 或定位失败原因时，才直接执行本页 leaf command。当前不再把 Android/Expo 当作主验收路径。

## 范围

试运行就绪 CLI 验证以下内容：

- `GET /health`
- `GET /api/v1/system/readiness`（需要认证）

它不会修改 demo 状态，也不会调用 `/api/v1/system/demo/bootstrap`。

## 配置档位

### 本地 Demo 档位

用于开发和本地 smoke 重置。

- `APP_RUNTIME_MODE=local-demo`
- `OBJECT_STORAGE_PROVIDER=mock`
- `ASR_PROVIDER=mock`
- `OCR_PROVIDER=mock`
- `VISION_PROVIDER=mock`
- `ASR_ALLOW_MOCK_FALLBACK=1`
- `OCR_ALLOW_MOCK_FALLBACK=1`
- `VISION_ALLOW_MOCK_FALLBACK=1`

### 试运行档位

用于试运行就绪和操作员预检。

- `APP_RUNTIME_MODE=trial`
- `OBJECT_STORAGE_PROVIDER=s3-compatible`
- `ASR_PROVIDER=real-provider`
- `OCR_PROVIDER=real-provider`
- `VISION_PROVIDER=real-provider`
- `ASR_ALLOW_MOCK_FALLBACK=0`
- `OCR_ALLOW_MOCK_FALLBACK=0`
- `VISION_ALLOW_MOCK_FALLBACK=0`

`*_ALLOW_MOCK_FALLBACK=0` 在试运行模式下是必须的。

## 命令

这是 readiness 的 leaf command。若你正在执行系统级验收，先看系统 CLI 清单；只有需要单独复核 readiness 时才直接运行这里的命令。

```powershell
python backend/scripts/run_trial_readiness_check.py
```

可选参数：

```powershell
python backend/scripts/run_trial_readiness_check.py --api-base-url http://10.0.2.2:8001
python backend/scripts/run_trial_readiness_check.py --auth-token <access_token>
python backend/scripts/run_trial_readiness_check.py --login-email owner@example.com --login-password dev-password
```

如果未传入 `--auth-token`，CLI 会通过 `POST /api/v1/auth/login` 登录，并使用返回的 bearer token。

## 输出契约

CLI 会输出紧凑 JSON，字段包括：

- `api_base_url`
- `health_status`
- `runtime_mode`
- `readiness_status` (from `/api/v1/system/readiness` `overall_status`)
- `overall_status` (operator verdict; `ready` only when `runtime_mode=trial` and `readiness_status=ready`, otherwise `degraded`)
- `object_storage` (`status`, `mode`)
- `providers.asr|ocr|vision` (`status`, `mode`)

示例：

```json
{"api_base_url":"http://127.0.0.1:8001","health_status":"ok","runtime_mode":"trial","readiness_status":"ready","overall_status":"ready","object_storage":{"status":"ready","mode":"s3-compatible"},"providers":{"asr":{"status":"ready","mode":"real-provider"},"ocr":{"status":"ready","mode":"real-provider"},"vision":{"status":"ready","mode":"real-provider"}}}
```

## 退出码

- 退出 `0`：`runtime_mode == "trial"` 且 `readiness_status == "ready"`（`overall_status == "ready"`）
- 退出 `1`：就绪降级或未就绪、认证失败、health 失败、非 200 响应，或返回封装格式异常

## 试运行元数据检查清单

在第一次 pilot 执行前，确认 readiness payload 中的 `trial_profile` 检查项已填充：

- `trial_provider_profile`
- `asr_provider_label`
- `ocr_provider_label`
- `vision_provider_label`
- `trial_calibration_dataset_dir`
- `trial_calibration_artifacts_dir`

如果试运行模式下缺少这些值，先把环境视为降级并修正配置，再跑 live traffic。

## 私有校准数据准备

把 pilot 校准数据放在仓库外，并将 `TRIAL_CALIBRATION_DATASET_DIR` 指向那个私有目录。

- 只保留经过操作员批准的 pilot 样本，不要把原始试运行媒体提交到源代码管理。
- 能做去标识化或最小权限导出时，优先这么做。
- 保持稳定的文件路径，避免每次运行都要手工改名，方便 manifest 直接引用。
- 限制目录访问到 pilot 操作员组，因为 manifest 里可能包含敏感收据、照片或录音。

推荐的 manifest 形状：

```json
{
  "trial_id": "pilot-v1",
  "cases": [
    {
      "case_id": "asr-001",
      "capability": "asr",
      "media_path": "asr/order-001.wav",
      "text_hint": "owner asking for current cola stock",
      "expected": {
        "transcript_contains": ["cola"],
        "min_confidence": 0.9
      }
    },
    {
      "case_id": "ocr-001",
      "capability": "ocr",
      "media_path": "ocr/receipt-001.jpg",
      "expected": {
        "total_amount": 123.0,
        "amount_tolerance": 1.0
      }
    },
    {
      "case_id": "vision-001",
      "capability": "vision",
      "media_path": "vision/item-001.jpg",
      "expected": {
        "top_candidate_in": ["Red Bull 250ml"],
        "min_confidence": 0.9
      }
    }
  ]
}
```

## 校准运行与应用流程

1. 加载试运行环境档位，确认 readiness CLI 使用的是预期的 `trial_provider_profile`。
2. 使用私有 manifest 运行 live calibration。
3. 检查 `TRIAL_CALIBRATION_ARTIFACTS_DIR` 下生成的 JSON 和 Markdown 产物。
4. 将批准过的 JSON 报告应用到 shop rules。
5. 在打开 pilot 日之前重新运行 readiness。

命令：

```powershell
python backend/scripts/run_live_trial_calibration.py --manifest C:\secure\pilot\manifest.json
python backend/scripts/apply_trial_calibration.py --report C:\secure\pilot\artifacts\pilot-v1_report_20260407T090000000000Z.json
python backend/scripts/run_trial_readiness_check.py
```

备注：

- `run_live_trial_calibration.py` 会写出一份机器可读的 JSON 报告和一份 Markdown 操作员摘要。
- `apply_trial_calibration.py` 会更新目标 shop 的 `low_confidence_threshold`、`require_price_confirmation` 和 `require_new_item_confirmation`。
- 校准应用会写入一条审计日志，关联报告 `artifact_id` 和 `trial_provider_profile`。
- 如果应用后的规则不可接受，就在下一次 readiness 检查前重新应用最后一份已知可用的报告。

## 线上 Pilot 预检 CLI 契约

在任何 `shadow -> open` 切换前，立即运行预检：

```powershell
python backend/scripts/run_live_pilot_preflight.py --artifact-path C:\secure\pilot\artifacts\pilot-v1_report_20260407T090000000000Z.json
```

可选参数：

```powershell
python backend/scripts/run_live_pilot_preflight.py --api-base-url http://10.0.2.2:8001
python backend/scripts/run_live_pilot_preflight.py --auth-token <access_token>
```

输出契约（紧凑 JSON）：

- `overall_status`：`ready` 或 `degraded`
- `runtime_mode`
- `trial_provider_profile`
- `cutover_mode`
- `approved_calibration_artifact_id`
- `reasons`：降级原因数组，ready 时为空

退出行为：

- 退出 `0`：所有预检门禁都通过
- 退出 `1`：readiness 不一致、档位/标签漂移、artifact 不一致、allowlist 不一致、路径安全问题、认证失败，或 payload 异常

预检契约说明：

- CLI 使用受保护路由，并校验以下内容是否对齐：
  - `GET /api/v1/system/readiness`
  - `GET /api/v1/system/pilot-control`
  - 已批准 artifact 的 JSON 内容
- 如果 `reasons` 非空，就不要把环境视为可安全切到 `open`
- 预检状态不是粘性的；每个新的切换窗口都要重新运行

## 切换模式含义

- `closed`：live pilot traffic 由切换策略阻断
- `shadow`：live providers 运行，但 guardrails 会强制在状态变更前确认
- `open`：live providers 和 guardrails 已对齐，可以进行受控的 live cutover

只有在拿到新的 `ready` 预检结果后，才可以进入 `open`。

## 交接到每日 Pilot 复核

在 readiness 变绿并且已应用批准过的校准报告后，就切到 [Pilot 执行运行手册](./pilot-execution-runbook.md) 继续做日常操作员检查。那份手册覆盖 pilot summary CLI、阈值覆盖和回滚姿态。
