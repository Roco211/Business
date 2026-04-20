# 05. Sprint 计划与执行顺序

## 1. 当前总目标

把当前交付主线切换为 **CLI 系统可用性验证**。当前要做的不是 Android/Expo trial shell，而是把后端已有脚本加上一层薄包装，形成一条真正给操作员用的命令入口。

## 2. 当前默认执行顺序

1. `backend/scripts/run_system_check.py`（目标入口）
2. 如果 wrapper 还未落地，则按下面的 leaf scripts 顺序手工执行：
   - `backend/scripts/run_local_demo_smoke.py`
   - `backend/scripts/run_trial_readiness_check.py`
   - `backend/scripts/run_live_pilot_preflight.py`
   - `backend/scripts/run_pilot_summary_check.py`
   - `backend/scripts/export_pilot_shift_bundle.py`

## 3. 当前 Sprint 切分

### Sprint 0 - CLI 主线切换与薄包装器

目标：

- 把现有后端脚本定义为正式验证能力
- 补一层 `run_system_check.py` 薄包装器
- 把移动端 trial shell 明确降级为历史路线

交付：

- `backend/scripts/run_system_check.py`
- `project_docs/system-cli-validation-checklist.md`
- `project_docs/05-sprint-plan.md`
- `project_docs/09-implementation-scope.md`
- 历史移动端计划的 superseded 标记

验收：

- 操作员能用一条命令启动系统可用性验证
- 如果 wrapper 尚未落地，至少能按固定顺序手工执行 leaf scripts
- 文档中不再把 Android/Expo 写成当前主线

### Sprint 1 - 本地演示与 readiness

目标：

- 确认本地 demo smoke 可重复执行
- 确认 trial readiness 的 JSON 输出、退出码和登录路径稳定

验收：

- `run_local_demo_smoke.py` 返回稳定的演示摘要
- `run_trial_readiness_check.py` 返回清晰的 ready / degraded 结果

### Sprint 2 - 试运行 preflight 与日常复核

目标：

- 把 live preflight 和 pilot summary 变成上线前与日常复核的标准检查

验收：

- `run_live_pilot_preflight.py` 能验证 trial profile、cutover mode 和 approved artifact 的一致性
- `run_pilot_summary_check.py` 能输出单行 JSON 并给出明确 verdict

### Sprint 3 - 交接与归档

目标：

- 把 shift bundle 导出固定为交接与事故复盘入口
- 保证操作员不需要回到移动端流程才能完成验证

验收：

- `export_pilot_shift_bundle.py` 可生成完整可归档包
- `project_docs/system-cli-validation-checklist.md` 可以直接作为操作手册

## 4. 已废弃路线

以下内容只保留历史参考，不再作为当前主线：

- Android/Expo trial shell
- `project_docs/mobile-trial-shell-checklist.md`
- `docs/superpowers/plans/2026-04-08-phase17b-mobile-usability-rescue-and-trial-ready-frontline-shell.md`
- `docs/superpowers/plans/2026-04-10-phase18a-yuanbao-mobile-ui.md`

## 5. 现在的判断标准

只要当前迭代能稳定满足下面四点，就算 CLI 主线成立：

- 本地 demo smoke 稳定
- trial readiness 稳定
- live preflight 稳定
- pilot summary / shift bundle 稳定
