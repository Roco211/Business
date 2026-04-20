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

- [ ] **Step 1: Write the failing test**

Add tests that verify the wrapper:

- accepts a mode such as `local-demo`, `trial`, or `pilot`
- calls the existing leaf functions instead of duplicating logic
- emits one compact JSON verdict
- exits `0` only when the selected scenario is ready

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
$env:PYTHONPATH='backend'; python -m pytest backend/tests/test_run_system_check.py -q
```

Expected: fail because `run_system_check.py` does not exist yet.

- [ ] **Step 3: Write the minimal implementation**

Implement the wrapper so it composes the existing devtools rather than reimplementing them.

- [ ] **Step 4: Run the test to verify it passes**

Run:

```powershell
$env:PYTHONPATH='backend'; python -m pytest backend/tests/test_run_system_check.py -q
```

Expected: pass with a single JSON verdict and the intended exit code.

- [ ] **Step 5: Commit**

```powershell
git add backend/scripts/run_system_check.py backend/tests/test_run_system_check.py
git commit -m "feat: add system cli wrapper"
```

### Task 2: Reframe The Active Roadmap Around CLI Validation

**Files:**
- Modify: `project_docs/05-sprint-plan.md`
- Modify: `project_docs/09-implementation-scope.md`

- [ ] **Step 1: Write the updated roadmap and scope text**

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

- [ ] **Step 2: Verify the old mobile-first wording is gone from the active docs**

Run:

```powershell
Select-String -Path .worktrees\ai-native-saas-rewrite\project_docs\05-sprint-plan.md, .worktrees\ai-native-saas-rewrite\project_docs\09-implementation-scope.md -Pattern "Android/Expo|React Native|mobile shell" -SimpleMatch
```

Expected: no active-scope match; only historical references should remain if they are intentionally labeled as deprecated.

- [ ] **Step 3: Commit the roadmap rewrite**

```powershell
git add project_docs/05-sprint-plan.md project_docs/09-implementation-scope.md
git commit -m "docs: switch planning to cli validation"
```

### Task 3: Create The Operator CLI Checklist

**Files:**
- Create: `project_docs/system-cli-validation-checklist.md`

- [ ] **Step 1: Write the checklist content**

Use the following structure so operators can run the system in a fixed order:

```md
# 系统 CLI 可用性验证清单

## 1. 统一入口（目标状态）

```powershell
python backend/scripts/run_system_check.py --mode trial --api-base-url http://127.0.0.1:8001
```

## 2. 本地 demo smoke（wrapper 未落地时的 fallback）

```powershell
python backend/scripts/run_local_demo_smoke.py --api-base-url http://127.0.0.1:8001
```

## 3. trial readiness

```powershell
python backend/scripts/run_trial_readiness_check.py --api-base-url http://127.0.0.1:8001
```

## 4. live pilot preflight

```powershell
python backend/scripts/run_live_pilot_preflight.py --api-base-url http://127.0.0.1:8001 --artifact-path C:\secure\pilot\artifacts\pilot-v1_report_20260407T090000000000Z.json
```

## 5. pilot summary check

```powershell
python backend/scripts/run_pilot_summary_check.py --api-base-url http://127.0.0.1:8001 --hours 24
```

## 6. shift bundle export

```powershell
python backend/scripts/export_pilot_shift_bundle.py --hours 24 --output-dir C:\secure\pilot\shift-bundles
```
```

- [ ] **Step 2: Verify the new checklist exists and includes the wrapper plus fallback commands**

Run:

```powershell
Get-Content .worktrees\ai-native-saas-rewrite\project_docs\system-cli-validation-checklist.md
```

Expected: the file contains the wrapper target, the fallback leaf commands, and no Android/Expo steps.

- [ ] **Step 3: Commit the checklist**

```powershell
git add project_docs/system-cli-validation-checklist.md
git commit -m "docs: add cli validation checklist"
```

### Task 4: Deprecate The Old Mobile Artifacts

**Files:**
- Modify: `project_docs/mobile-trial-shell-checklist.md`
- Modify: `docs/superpowers/plans/2026-04-08-phase17b-mobile-usability-rescue-and-trial-ready-frontline-shell.md`
- Modify: `docs/superpowers/plans/2026-04-10-phase18a-yuanbao-mobile-ui.md`

- [ ] **Step 1: Write the superseded banner**

Insert the same banner at the top of each historical mobile artifact:

```md
> **状态：已废弃 / superseded**
> 当前主线已经切换为 CLI 系统可用性验证。本文仅保留历史记录，不再作为后续工作的执行依据。
> 请改看 `project_docs/system-cli-validation-checklist.md`、`project_docs/05-sprint-plan.md` 和 `project_docs/09-implementation-scope.md`。
```

- [ ] **Step 2: Verify the deprecation marker is visible**

Run:

```powershell
Select-String -Path .worktrees\ai-native-saas-rewrite\project_docs\mobile-trial-shell-checklist.md, .worktrees\ai-native-saas-rewrite\docs\superpowers\plans\2026-04-08-phase17b-mobile-usability-rescue-and-trial-ready-frontline-shell.md, .worktrees\ai-native-saas-rewrite\docs\superpowers\plans\2026-04-10-phase18a-yuanbao-mobile-ui.md -Pattern "superseded|已废弃"
```

Expected: all three files clearly advertise that they are historical only.

- [ ] **Step 3: Commit the historical deprecation pass**

```powershell
git add project_docs/mobile-trial-shell-checklist.md docs/superpowers/plans/2026-04-08-phase17b-mobile-usability-rescue-and-trial-ready-frontline-shell.md docs/superpowers/plans/2026-04-10-phase18a-yuanbao-mobile-ui.md
git commit -m "docs: deprecate mobile trial shell path"
```

### Task 5: Validate The Wrapper Against The Existing Leaf Scripts

**Files:**
- Modify `backend/scripts/run_system_check.py` if the wrapper JSON verdict needs another field after local verification

- [ ] **Step 1: Run the current CLI scripts in the intended order**

Run:

```powershell
python backend/scripts/run_system_check.py --mode trial --api-base-url http://127.0.0.1:8001
python backend/scripts/run_system_check.py --mode local-demo --api-base-url http://127.0.0.1:8001
```

If the wrapper has not landed yet, run the leaf scripts manually in the same sequence.

- [ ] **Step 2: Decide whether the wrapper JSON is sufficient**

The wrapper should return a compact verdict with enough detail to know:

- which scenario ran
- which sub-checks passed or failed
- why the final verdict is ready or degraded

If the payload is too thin, extend the wrapper once rather than pushing logic into docs.

- [ ] **Step 3: Record the final operating rule**

Document the final decision in `project_docs/system-cli-validation-checklist.md` so future work knows whether the current CLI surface is wrapper-first or leaf-script-first.

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
