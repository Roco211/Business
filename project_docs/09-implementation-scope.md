# 09. 当前实施范围与落地边界

本文只回答一个问题：

**在当前 `project_docs` 与后端脚本已经存在的前提下，下一阶段到底应该把什么当作“可落地”，什么不该再推进。**

---

## 1. 当前实施目标

当前实施目标统一为：

**做一个可复现的 CLI 系统可用性验证闭环，并补一层薄包装器，让 `app_cli.py` 同时覆盖 `up`、`demo`、`ask`、`check` 和 `cutover`。**

换句话说：

- 后端真实存在
- 数据库、对象存储、任务编排、WebSocket、summary / preflight 逻辑都继续按真实系统方式运行
- 但当前验收入口是 CLI，不是 Android/Expo
- 当前顶层入口已经是 `backend/scripts/app_cli.py`
- `backend/scripts/run_system_check.py` 作为底层统一检查入口，其余脚本作为 leaf commands

当前应把这些脚本视为正式能力：

- `backend/scripts/app_cli.py`
- `backend/scripts/run_local_demo_smoke.py`
- `backend/scripts/run_trial_readiness_check.py`
- `backend/scripts/run_live_pilot_preflight.py`
- `backend/scripts/run_pilot_summary_check.py`
- `backend/scripts/export_pilot_shift_bundle.py`

---

## 2. 当前阶段的默认实施决策

### 2.1 实施层级

当前默认实施层级定义为：

- `B. 可复现的端到端 CLI 验证闭环 + 薄包装器`

不是：

- 只写文档
- 重新做 Android/Expo 试点壳
- 再开一个新的移动端 UI 重构线

### 2.2 交付姿势

当前阶段优先交付：

- 稳定的 CLI 命令
- 稳定的 JSON 输出
- 稳定的退出码
- 可直接执行的操作员清单
- 一个顶层体验 CLI，能够直接打印本地 demo 快照并向默认会话发消息
- 一个底层统一检查命令

### 2.3 验证姿势

当前阶段继续使用：

- SQLite / 本地 demo
- trial readiness
- live preflight
- pilot summary
- shift bundle

但不再把 Android 设备、Expo Go、模拟器当作当前验收前提。

---

## 3. 当前范围内必须完成的内容

### P0 - CLI 验证闭环

必须先做成：

- 本地 demo smoke
- 顶层 `app_cli.py demo`
- trial readiness
- live pilot preflight
- pilot summary check
- shift bundle export

### P1 - 薄包装器

必须补齐：

- 一个顶层入口 `app_cli.py`
- 一个统一入口 `run_system_check.py`
- 统一的 JSON verdict
- 统一的 exit code
- 对 local-demo / trial / pilot 场景的固定编排

### P2 - 操作员清单

必须补齐：

- 每个 CLI 命令的用途
- 每个命令的运行前置条件
- 每个命令的预期输出
- 每个命令的失败判读方式

### P3 - 历史路线退场

必须明确：

- Android/Expo trial shell 已不是当前主线
- 旧 mobile checklist 只保留历史记录
- 旧 mobile plan 只保留历史记录

---

## 4. 当前范围明确不纳入

以下内容统一视为后续阶段，不阻塞当前工作：

- Android 端新页面
- Expo shell 继续扩展
- 新的移动端交互重构
- 多店铺 / 多角色 / 复杂权限体系
- 真正实时的复杂前端协作
- 流式模型输出在客户端的高级可视化
- 新的第三方插件市场
- 跨账号复杂同步

---

## 5. 当前推荐落地顺序

### 第 1 步：先把 CLI 当成正式验收面

先确认：

- `run_local_demo_smoke.py` 能证明本地 demo 可用，`app_cli.py demo` 能把它包装成可直接体验的顶层入口
- `run_trial_readiness_check.py` 能证明 trial readiness 可用

### 第 2 步：再补试运行 gate

然后确认：

- `run_live_pilot_preflight.py` 能卡住 cutover 不一致
- `run_pilot_summary_check.py` 能给出日常复核结果

### 第 3 步：最后把交接打通

补齐：

- `export_pilot_shift_bundle.py`
- 操作员清单
- 归档说明

---

## 6. 这轮不再等待的决定

下面这些问题在当前阶段不再阻塞推进：

- 是否先做 Android app
- 是否继续加 Expo UI
- 是否先做更复杂的移动端视觉
- 是否先把所有终端体验都做完整

原因很简单：

**当前阶段的价值判断不是“界面做得多像产品”，而是“整个系统能不能被 CLI 验证成可用”。**
