# AI 原生 SaaS V2 Outbox Due Sweep 调度实现计划

> **给智能执行代理（agentic workers）：** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务逐项实现本计划。步骤使用 checkbox（`- [ ]`）语法跟踪。

**Goal:** 把已经存在的 V2 outbox due-scope 兜底消费任务接入 Celery beat，使 pending outbox 即使没有业务请求触发也能被周期性 sweep。

**Architecture:** 保持现有“业务提交后 best-effort 唤醒 scoped worker + 系统级 due-scope fallback”双通道。新增调度层只注册 Celery beat 周期任务，并通过配置控制间隔和每次 sweep 的安全上限；本地 compose 增加独立 `beat` 进程，避免把调度职责塞进 API 或普通 worker。调度任务仍复用 `drain_due_v2_outbox_scopes(...)`，不新增 public/internal HTTP API。

**Tech Stack:** Python、Celery、Docker Compose、pytest

---

## 文件结构

- 修改 `backend/tests/test_worker_bootstrap.py`：先固定 Celery beat schedule 默认值和环境变量覆盖行为。
- 创建 `backend/tests/test_infra_docker_compose.py`：先固定本地 compose 必须包含独立 Celery beat 服务。
- 修改 `backend/app/core/config.py`：增加 V2 outbox due sweep 调度配置。
- 修改 `backend/app/workers/celery_app.py`：把 due-scope task 注册到 `beat_schedule`。
- 修改 `.env.example`：暴露本地默认调度参数。
- 修改 `infra/docker/docker-compose.yml`：增加 `beat` 服务。
- 修改 `infra/docker/README.md`：更新本地启动命令和 outbox due sweep 说明。

### Task 1: 固定 Celery beat 调度配置

**Files:**
- Modify: `backend/tests/test_worker_bootstrap.py`
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/workers/celery_app.py`
- Modify: `.env.example`

- [x] **Step 1: 先写失败测试，确认默认 Celery app 注册 due-scope beat schedule**

测试要点：

```python
def test_celery_app_registers_due_scope_beat_schedule_defaults() -> None:
    celery_app = create_celery_app()

    schedule = celery_app.conf.beat_schedule["v2-outbox-due-scope-sweep"]
    assert schedule == {
        "task": "app.workers.v2_outbox_due_tasks.drain_due_v2_outbox_scopes",
        "schedule": 30,
        "kwargs": {
            "scope_limit": 20,
            "batch_limit_per_scope": 50,
            "max_batches_per_scope": 10,
            "retry_after_seconds": 60,
        },
    }
```

- [x] **Step 2: 再写失败测试，确认环境变量可以覆盖调度间隔和 sweep 上限**

测试要点：

```python
def test_celery_app_uses_due_scope_beat_schedule_env_overrides(monkeypatch) -> None:
    monkeypatch.setenv("V2_OUTBOX_DUE_SWEEP_INTERVAL_SECONDS", "45")
    monkeypatch.setenv("V2_OUTBOX_DUE_SWEEP_SCOPE_LIMIT", "7")
    monkeypatch.setenv("V2_OUTBOX_DUE_SWEEP_BATCH_LIMIT_PER_SCOPE", "8")
    monkeypatch.setenv("V2_OUTBOX_DUE_SWEEP_MAX_BATCHES_PER_SCOPE", "2")
    monkeypatch.setenv("V2_OUTBOX_DUE_SWEEP_RETRY_AFTER_SECONDS", "120")

    celery_app = create_celery_app()

    schedule = celery_app.conf.beat_schedule["v2-outbox-due-scope-sweep"]
    assert schedule["schedule"] == 45
    assert schedule["kwargs"] == {
        "scope_limit": 7,
        "batch_limit_per_scope": 8,
        "max_batches_per_scope": 2,
        "retry_after_seconds": 120,
    }
```

- [x] **Step 3: 运行 worker bootstrap 测试，确认新断言红灯**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_worker_bootstrap.py -q
```

Expected:

- 新增 beat schedule 断言失败，因为当前 `celery_app.py` 尚未设置 `beat_schedule`。

- [x] **Step 4: 实现最小配置与 Celery beat schedule**

实现边界：

- `Settings` 新增默认值：
  - `v2_outbox_due_sweep_interval_seconds=30`
  - `v2_outbox_due_sweep_scope_limit=20`
  - `v2_outbox_due_sweep_batch_limit_per_scope=50`
  - `v2_outbox_due_sweep_max_batches_per_scope=10`
  - `v2_outbox_due_sweep_retry_after_seconds=60`
- `get_settings()` 从同名环境变量读取整数。
- `create_celery_app()` 在创建 Celery 后设置：

```python
celery.conf.beat_schedule = {
    "v2-outbox-due-scope-sweep": {
        "task": "app.workers.v2_outbox_due_tasks.drain_due_v2_outbox_scopes",
        "schedule": settings.v2_outbox_due_sweep_interval_seconds,
        "kwargs": {
            "scope_limit": settings.v2_outbox_due_sweep_scope_limit,
            "batch_limit_per_scope": settings.v2_outbox_due_sweep_batch_limit_per_scope,
            "max_batches_per_scope": settings.v2_outbox_due_sweep_max_batches_per_scope,
            "retry_after_seconds": settings.v2_outbox_due_sweep_retry_after_seconds,
        },
    }
}
```

- `.env.example` 增加同名配置，保持本地默认值可见。

- [x] **Step 5: 重跑 worker bootstrap 测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_worker_bootstrap.py -q
```

Expected:

- `3 passed`

### Task 2: 固定本地 compose 运行约定

**Files:**
- Create: `backend/tests/test_infra_docker_compose.py`
- Modify: `infra/docker/docker-compose.yml`
- Modify: `infra/docker/README.md`

- [x] **Step 1: 先写失败测试，确认 compose 包含独立 beat 服务**

测试要点：

```python
def test_local_compose_includes_celery_beat_service() -> None:
    compose_text = Path("infra/docker/docker-compose.yml").read_text(encoding="utf-8")

    assert "\n  beat:\n" in compose_text
    assert "celery -A app.workers.celery_app.celery_app beat --loglevel=info" in compose_text
    assert "migrator:" in compose_text
    assert "redis:" in compose_text
```

- [x] **Step 2: 运行 compose 测试，确认红灯**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_infra_docker_compose.py -q
```

Expected:

- 失败，因为当前 compose 只有 `worker` 服务，没有 `beat` 服务。

- [x] **Step 3: 实现最小 compose 和 README 更新**

`infra/docker/docker-compose.yml` 增加：

```yaml
  beat:
    build:
      context: ../..
      dockerfile: backend/Dockerfile
    env_file:
      - ../../.env.example
    command: celery -A app.workers.celery_app.celery_app beat --loglevel=info
    depends_on:
      migrator:
        condition: service_completed_successfully
      mysql:
        condition: service_started
      redis:
        condition: service_started
```

`infra/docker/README.md` 更新本地启动命令：

```powershell
docker compose -f infra/docker/docker-compose.yml --env-file .env.example up -d mysql redis minio api worker beat
```

并说明 `beat` 负责周期性触发 V2 outbox due-scope sweep。

- [x] **Step 4: 重跑 compose 测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_infra_docker_compose.py -q
```

Expected:

- `1 passed`

### Task 3: 阶段验收

**Files:**
- Verify: `backend/tests/test_worker_bootstrap.py`
- Verify: `backend/tests/test_infra_docker_compose.py`
- Verify: `backend/tests/test_v2_outbox_due_tasks.py`
- Verify: `backend/tests/test_v2_outbox_due_scopes.py`

- [x] **Step 1: 运行调度层目标回归**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_worker_bootstrap.py backend/tests/test_infra_docker_compose.py backend/tests/test_v2_outbox_due_tasks.py backend/tests/test_v2_outbox_due_scopes.py -q
```

- [x] **Step 2: 运行 V2 outbox / worker 回归**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_outbox_due_scopes.py backend/tests/test_v2_outbox_due_tasks.py backend/tests/test_v2_outbox_runtime_dispatch.py backend/tests/test_v2_outbox_tasks.py backend/tests/test_v2_outbox_worker.py backend/tests/test_v2_outbox_dispatch.py backend/tests/test_worker_bootstrap.py backend/tests/test_infra_docker_compose.py -q
```

- [x] **Step 3: 如目标回归通过，再运行关键 V2 / worker 回归**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_alembic_bootstrap.py backend/tests/test_v2_identity_context.py backend/tests/test_v2_conversation_runtime.py backend/tests/test_v2_clarification_confirmation.py backend/tests/test_v2_inventory_ledger.py backend/tests/test_v2_inventory_read_api.py backend/tests/test_v2_inventory_corrections_api.py backend/tests/test_v2_inventory_stock_out_api.py backend/tests/test_v2_outbox.py backend/tests/test_v2_outbox_dispatch.py backend/tests/test_v2_outbox_worker.py backend/tests/test_v2_outbox_tasks.py backend/tests/test_v2_outbox_runtime_dispatch.py backend/tests/test_v2_outbox_due_scopes.py backend/tests/test_v2_outbox_due_tasks.py backend/tests/test_v2_inventory_projection_replay.py backend/tests/test_v2_internal_api.py backend/tests/test_runtime_tasks.py backend/tests/test_worker_bootstrap.py backend/tests/test_infra_docker_compose.py backend/tests/test_openapi_contract_snapshot.py -q
```
