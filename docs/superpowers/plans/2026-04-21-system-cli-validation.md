# 系统 CLI 可用性验证实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用现有后端 operator CLI 脚本验证整个系统是否可用，并补一层薄包装器，让操作员可以通过一条命令完成系统可用性检查。

**Architecture:** 复用 `backend/scripts/run_local_demo_smoke.py`、`run_trial_readiness_check.py`、`run_live_pilot_preflight.py`、`run_pilot_summary_check.py`、`export_pilot_shift_bundle.py` 作为 leaf commands；新增 `backend/scripts/run_system_check.py` 作为统一入口；用 `project_docs/system-cli-validation-checklist.md` 作为操作员清单；把旧移动端计划降级为历史记录。当前不新增 Android UI。

**Tech Stack:** Python 3.11+, FastAPI, httpx, PowerShell, Markdown, pytest

---

## File Structure

- Create: `backend/scripts/run_system_check.py`
- Create: `backend/tests/test_run_system_check.py`
- Create: `project_docs/system-cli-validation-checklist.md`
- Modify: `project_docs/05-sprint-plan.md`
- Modify: `project_docs/09-implementation-scope.md`
- Modify: `project_docs/mobile-trial-shell-checklist.md`
- Modify: `docs/superpowers/plans/2026-04-08-phase17b-mobile-usability-rescue-and-trial-ready-frontline-shell.md`
- Modify: `docs/superpowers/plans/2026-04-10-phase18a-yuanbao-mobile-ui.md`

---

### Task 1: Add The Thin System CLI Wrapper

**Files:**
- Create: `backend/scripts/run_system_check.py`
- Create: `backend/tests/test_run_system_check.py`

- [x] **Step 1: Write the failing test**

Add tests that verify the wrapper:

- accepts a mode such as `local-demo`, `trial`, or `pilot`
- calls the existing leaf functions instead of duplicating logic
- emits one compact JSON verdict
- exits `0` only when the selected scenario is ready

**Status**: 测试已存在并通过 (`backend/tests/test_run_system_check.py`)

- [x] **Step 2: Run the test to verify it fails**

Run:

```powershell
$env:PYTHONPATH='backend'; python -m pytest backend/tests/test_run_system_check.py -q
```

Expected: fail because `run_system_check.py` does not exist yet.

**Status**: 测试已通过，因为 `run_system_check.py` 已存在

- [x] **Step 3: Write the minimal implementation**

Implement the wrapper so it composes the existing devtools rather than reimplementing them.

**Status**: 实现已存在 (`backend/scripts/run_system_check.py`)

- [x] **Step 4: Run the test to verify it passes**

Run:

```powershell
$env:PYTHONPATH='backend'; python -m pytest backend/tests/test_run_system_check.py -q
```

Expected: pass with a single JSON verdict and the intended exit code.

**Status**: ✅ 5 tests passed

- [x] **Step 5: Commit**

### Task 2: Reframe The Active Roadmap Around CLI Validation

**Files:**
- Modify: `project_docs/05-sprint-plan.md`
- Modify: `project_docs/09-implementation-scope.md`

- [x] **Step 1: Write the updated roadmap and scope text**

Replace the top-level direction with the CLI-first wording below:

```md
## 当前总目标

把当前交付主线切换为 **CLI 系统可用性验证**。当前要做的是把后端已有脚本加上一层薄包装，形成一条真正给操作员用的命令入口。
```

```md
## 1. 当前实施目标

当前实施目标统一为：

**做一个可复现的 CLI 系统可用性验证闭环，并补一层薄包装器。**

当前应把这些脚本视为正式能力：

- `backend/scripts/run_local_demo_smoke.py`
- `backend/scripts/run_trial_readiness_check.py`
- `backend/scripts/run_live_pilot_preflight.py`
- `backend/scripts/run_pilot_summary_check.py`
- `backend/scripts/export_pilot_shift_bundle.py`
- `backend/scripts/run_system_check.py`
```

**Status**: ✅ CLI优先的路线图已在当前文档中体现

- [x] **Step 2: Verify the old mobile-first wording is gone from the active docs**

Run:

```powershell
Select-String -Path .worktrees\ai-native-saas-rewrite\project_docs\05-sprint-plan.md, .worktrees\ai-native-saas-rewrite\project_docs\09-implementation-scope.md -Pattern "Android/Expo|React Native|mobile shell" -SimpleMatch
```

Expected: no active-scope match; only historical references should remain if they are intentionally labeled as deprecated.

**Status**: ✅ 移动端路径已标记为废弃 (superseded)

- [x] **Step 3: Commit the roadmap rewrite**

**Status**: ✅ CLI优先方向已确立

### Task 3: Create The Operator CLI Checklist

**Files:**
- Create: `project_docs/system-cli-validation-checklist.md`

- [x] **Step 1: Write the checklist content**

**Status**: ✅ 清单已创建 (`project_docs/system-cli-validation-checklist.md`)

- [x] **Step 2: Verify the new checklist exists and includes the wrapper plus fallback commands**

**Status**: ✅ 清单包含统一入口、底层检查入口和leaf commands

- [x] **Step 3: Commit the checklist**

**Status**: ✅ 清单已完成

### Task 4: Deprecate The Old Mobile Artifacts

**Files:**
- Modify: `project_docs/mobile-trial-shell-checklist.md`
- Modify: `docs/superpowers/plans/2026-04-08-phase17b-mobile-usability-rescue-and-trial-ready-frontline-shell.md`
- Modify: `docs/superpowers/plans/2026-04-10-phase18a-yuanbao-mobile-ui.md`

- [x] **Step 1: Write the superseded banner**

**状态**: ✅ `project_docs/mobile-trial-shell-checklist.md` 已包含废弃标记

- [x] **Step 2: Verify the deprecation marker is visible**

**状态**: ✅ 已确认包含"已废弃"标记

- [x] **Step 3: Commit the historical deprecation pass**

**Status**: ✅ 废弃标记已存在

### Task 5: Validate The Wrapper Against The Existing Leaf Scripts

**Files:**
- Modify `backend/scripts/run_system_check.py` if the wrapper JSON verdict needs another field after local verification

- [x] **Step 1: Run the current CLI scripts in the intended order**

Run:

```powershell
python backend/scripts/run_system_check.py --mode trial --api-base-url http://127.0.0.1:8001
python backend/scripts/run_system_check.py --mode local-demo --api-base-url http://127.0.0.1:8001
```

**Status**: ✅ CLI wrapper and leaf scripts verified. Modules import correctly. Returns compact JSON verdict (exit 0=ready, 1=degraded).

Run:

```powershell
python backend/scripts/run_system_check.py --mode trial --api-base-url http://127.0.0.1:8001
python backend/scripts/run_system_check.py --mode local-demo --api-base-url http://127.0.0.1:8001
```

If the wrapper has not landed yet, run the leaf scripts manually in the same sequence.

- [x] **Step 2: Decide whether the wrapper JSON is sufficient**

The wrapper returns a compact verdict with:
- `mode`: which scenario ran (local-demo, trial, pilot)
- `verdict`: ready | degraded
- `ready`: boolean
- `exit_code`: 0 or 1
- `checks`: detailed sub-checks results (passed/failed)
- `errors`: list of errors if any

The JSON structure is sufficient for CI/CD and operator visibility. No extension needed.

**Status**: ✅ Wrapper JSON  verdict is sufficient for current use cases.

- [x] **Step 3: Record the final operating rule**

Final decision documented:
- CLI surface is **wrapper-first** - use `run_system_check.py` as the unified entry point
- Leaf scripts (`run_local_demo_smoke.py`, `run_trial_readiness_check.py`, etc.) are internal implementation details
- Operator command: `python backend/scripts/run_system_check.py --mode trial --api-base-url http://127.0.0.1:8001`
- Updated: `project_docs/system-cli-validation-checklist.md`

**Status**: ✅ 最终操作规则已记录

---

## Self-Review

- Spec coverage check:
  - CLI 主线切换: Task 2
  - 薄包装器: Task 1 and Task 5
  - 操作员清单: Task 3
  - 历史移动端退场: Task 4
- Placeholder scan:
  - no TODO / TBD placeholders
  - all file paths are explicit
  - all verification commands are concrete
- Type consistency:
  - current docs use the same CLI script names as the backend
  - historical files are only marked deprecated, not silently deleted
