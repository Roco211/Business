# Phase 4A Runtime Dry-Run Worker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the minimum worker-backed read-only runtime loop so fresh messages dispatch a `TaskRun`, supported text/voice inputs execute to `completed`, unsupported inputs fail explicitly, and the outcome is visible through both session messages and a read-only task-run route.

**Architecture:** Keep `POST /messages` as the persistent intake entry point, then add a small runtime stack split into deterministic router, allow/block policy guard, mock transcription tool, summarizer, runtime message writer, and a Celery task wrapper. This phase writes only system text messages and `task_runs.result_summary`; it does not create confirmations, inventory events, audit records, or WebSocket updates.

**Tech Stack:** Python, FastAPI, SQLAlchemy, Celery, pytest, SQLite test databases, MySQL-oriented schema design, Docker Compose

---

### Task 1: Add runtime router and mock transcription foundation

**Files:**
- Create: `backend/app/runtime/types.py`
- Create: `backend/app/runtime/router.py`
- Create: `backend/app/runtime/tools.py`
- Test: `backend/tests/test_runtime_router.py`

- [ ] **Step 1: Write the failing runtime routing tests**

```python
def test_route_text_query_to_voice_stock_query():
    context = RuntimeTurnContext(
        shop_id="shop_default",
        session_id="sess_default",
        source_message_id="msg_1",
        task_run_id="task_1",
        input_kind="text",
        source_text="check stock left for cola",
        media_ids=[],
        locale="zh-CN",
        timezone="Asia/Shanghai",
        shop_rules={},
        recent_messages=[],
        pending_confirmation_id=None,
    )

    decision = route_runtime_input(context)

    assert decision.task_type == "voice-stock-query"
    assert decision.assigned_employee_id == "xiaoya"


def test_transcribe_audio_reads_fixture_media_id():
    assert transcribe_audio(media_ids=["voice_stock_in_demo"], text_hint=None) == "restock apples today"


def test_route_runtime_input_blocks_receipt_image():
    context = RuntimeTurnContext(
        shop_id="shop_default",
        session_id="sess_default",
        source_message_id="msg_2",
        task_run_id="task_2",
        input_kind="receipt-image",
        source_text=None,
        media_ids=["receipt_demo"],
        locale="zh-CN",
        timezone="Asia/Shanghai",
        shop_rules={},
        recent_messages=[],
        pending_confirmation_id=None,
    )

    with pytest.raises(RuntimeRouteBlocked) as exc:
        route_runtime_input(context)

    assert exc.value.error_code == "runtime_input_not_supported"
```

- [ ] **Step 2: Run the router tests to verify they fail**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_runtime_router.py -q
```

Expected:

- import failures for `app.runtime.router` or `app.runtime.tools`

- [ ] **Step 3: Add the minimal runtime types, router, and tool**

`backend/app/runtime/types.py`

```python
@dataclass(frozen=True)
class RuntimeTurnContext:
    shop_id: str
    session_id: str
    source_message_id: str
    task_run_id: str
    input_kind: str
    source_text: str | None
    media_ids: list[str]
    locale: str
    timezone: str
    shop_rules: dict[str, object]
    recent_messages: list[dict[str, object]]
    pending_confirmation_id: str | None


@dataclass(frozen=True)
class RuntimeRouteDecision:
    task_type: str
    assigned_employee_id: str
    transcript: str | None
```

`backend/app/runtime/tools.py`

```python
VOICE_TRANSCRIPT_FIXTURES = {
    "voice_query_demo": "check stock left for cola",
    "voice_stock_in_demo": "restock apples today",
}


class MockTranscriptionUnavailable(Exception):
    pass


def transcribe_audio(*, media_ids: list[str], text_hint: str | None) -> str:
    if text_hint and text_hint.strip():
        return text_hint.strip()
    if media_ids and media_ids[0] in VOICE_TRANSCRIPT_FIXTURES:
        return VOICE_TRANSCRIPT_FIXTURES[media_ids[0]]
    raise MockTranscriptionUnavailable("Transcript unavailable for this voice input")
```

`backend/app/runtime/router.py`

```python
QUERY_KEYWORDS = ("query", "stock", "left", "remaining", "how many", "check")


class RuntimeRouteBlocked(Exception):
    def __init__(self, error_code: str, error_message: str) -> None:
        super().__init__(error_message)
        self.error_code = error_code
        self.error_message = error_message


def classify_text_intent(text: str) -> str:
    lowered = text.lower()
    return "voice-stock-query" if any(k in lowered for k in QUERY_KEYWORDS) else "voice-stock-in"


def route_runtime_input(context: RuntimeTurnContext) -> RuntimeRouteDecision:
    if context.input_kind == "text":
        transcript = (context.source_text or "").strip()
        if not transcript:
            raise RuntimeRouteBlocked("runtime_processing_error", "Text message is empty")
        return RuntimeRouteDecision(classify_text_intent(transcript), "xiaoya", transcript)

    if context.input_kind == "voice":
        transcript = transcribe_audio(media_ids=context.media_ids, text_hint=context.source_text)
        return RuntimeRouteDecision(classify_text_intent(transcript), "xiaoya", transcript)

    raise RuntimeRouteBlocked("runtime_input_not_supported", f"Runtime input kind '{context.input_kind}' is not supported in Phase 4A.")
```

- [ ] **Step 4: Re-run the router tests to verify they pass**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_runtime_router.py -q
```

Expected:

- all router tests pass

- [ ] **Step 5: Commit**

```bash
git add backend/app/runtime/types.py backend/app/runtime/router.py backend/app/runtime/tools.py backend/tests/test_runtime_router.py
git commit -m "feat: add runtime routing foundation"
```

### Task 2: Add task lifecycle, runtime processor, and runtime message writeback

**Files:**
- Modify: `backend/app/services/task_runs.py`
- Create: `backend/app/services/runtime_messages.py`
- Create: `backend/app/runtime/context.py`
- Create: `backend/app/runtime/summarizer.py`
- Create: `backend/app/runtime/processor.py`
- Test: `backend/tests/test_runtime_processor.py`

- [ ] **Step 1: Write the failing runtime processor tests**

```python
def test_process_task_run_completes_text_task_and_writes_runtime_message(db_session):
    task_run_id = create_owner_message(
        db_session,
        message_type="text",
        text="check stock left for cola",
        media_ids=[],
        client_request_id="runtime_text_001",
    )

    result = process_task_run(db_session, task_run_id)
    task_run = db_session.get(TaskRun, task_run_id)
    runtime_messages = db_session.scalars(
        select(Message).where(Message.actor_type == "system", Message.task_run_id == task_run_id)
    ).all()

    assert result.status == "completed"
    assert task_run.status == "completed"
    assert task_run.task_type == "voice-stock-query"
    assert task_run.result_summary is not None
    assert len(runtime_messages) == 1


def test_process_task_run_fails_unsupported_image(db_session):
    task_run_id = create_owner_message(
        db_session,
        message_type="image",
        text=None,
        media_ids=["image_demo"],
        client_request_id="runtime_image_001",
    )

    result = process_task_run(db_session, task_run_id)
    task_run = db_session.get(TaskRun, task_run_id)

    assert result.status == "failed"
    assert task_run.error_code == "runtime_input_not_supported"
```

- [ ] **Step 2: Run the processor tests to verify they fail**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_runtime_processor.py -q
```

Expected:

- import failures for `app.runtime.processor`

- [ ] **Step 3: Add lifecycle helpers and runtime processor**

`backend/app/services/task_runs.py`

```python
PROCESSING_STATUS = "processing"
COMPLETED_STATUS = "completed"
FAILED_STATUS = "failed"


def claim_task_run_for_runtime(db_session: Session, *, task_run_id: str) -> TaskRunTransitionResult:
    task_run = db_session.get(TaskRun, task_run_id)
    if task_run is None:
        raise LookupError(task_run_id)
    if task_run.status != CREATED_STATUS or task_run.task_type != PENDING_CLASSIFICATION_TASK_TYPE:
        return TaskRunTransitionResult(changed=False, task_run=task_run)
    task_run.status = PROCESSING_STATUS
    task_run.updated_at = datetime.now(UTC).replace(tzinfo=None)
    db_session.flush()
    return TaskRunTransitionResult(changed=True, task_run=task_run)
```

`backend/app/services/runtime_messages.py`

```python
def write_runtime_message(db_session: Session, *, session_id: str, task_run_id: str, text: str) -> Message:
    now = datetime.now(UTC).replace(tzinfo=None)
    message = Message(
        message_id=new_prefixed_id("msg"),
        session_id=session_id,
        actor_type="system",
        actor_id="runtime_system",
        message_type="text",
        text=text,
        media_ids=[],
        client_request_id=None,
        task_run_id=task_run_id,
        created_at=now,
    )
    db_session.add(message)
    session_record = db_session.get(SessionRecord, session_id)
    if session_record is not None:
        session_record.last_message_at = now
    db_session.flush()
    return message
```

`backend/app/runtime/context.py`

```python
def build_runtime_turn_context(db_session: Session, *, task_run_id: str) -> RuntimeTurnContext:
    task_run = db_session.get(TaskRun, task_run_id)
    source_message = db_session.get(Message, task_run.source_message_id)
    session_record = db_session.get(SessionRecord, task_run.session_id)
    shop = db_session.get(Shop, session_record.shop_id)
    recent_records = list(
        db_session.scalars(
            select(Message)
            .where(Message.session_id == session_record.session_id)
            .order_by(Message.created_at.desc(), Message.message_id.desc())
            .limit(10)
        )
    )
    return RuntimeTurnContext(
        shop_id=shop.shop_id,
        session_id=session_record.session_id,
        source_message_id=source_message.message_id,
        task_run_id=task_run.task_run_id,
        input_kind=source_message.message_type,
        source_text=source_message.text,
        media_ids=source_message.media_ids,
        locale=shop.locale,
        timezone=shop.timezone,
        shop_rules={"low_confidence_threshold": float(shop.low_confidence_threshold)},
        recent_messages=[{"message_id": r.message_id, "actor_type": r.actor_type, "text": r.text} for r in recent_records],
        pending_confirmation_id=None,
    )
```

`backend/app/runtime/summarizer.py`

```python
def summarize_completed_task(*, task_type: str, transcript: str | None) -> tuple[str, str]:
    if task_type == "voice-stock-query":
        return (
            f"Mock runtime query processed: {(transcript or '').strip() or 'query'}",
            "Mock runtime: stock query accepted. Fixture inventory shows low stock for the requested item.",
        )
    return (
        f"Mock runtime stock-in intent captured: {(transcript or '').strip() or 'stock-in'}",
        "Mock runtime: stock-in intent accepted. Inventory writes are deferred to later confirmation and inventory phases.",
    )


def summarize_failed_task(*, error_code: str, error_message: str) -> tuple[str, str]:
    return (f"Runtime failed with {error_code}", f"Mock runtime could not process this task: {error_message}")
```

`backend/app/runtime/processor.py`

```python
@dataclass(frozen=True)
class RuntimeProcessResult:
    status: str
    task_run_id: str
    task_type: str | None
    error_code: str | None


def process_task_run(db_session: Session, task_run_id: str) -> RuntimeProcessResult:
    claim = claim_task_run_for_runtime(db_session, task_run_id=task_run_id)
    if not claim.changed:
        return RuntimeProcessResult("skipped", claim.task_run.task_run_id, claim.task_run.task_type, claim.task_run.error_code)
    try:
        context = build_runtime_turn_context(db_session, task_run_id=task_run_id)
        decision = route_runtime_input(context)
        result_summary, runtime_text = summarize_completed_task(task_type=decision.task_type, transcript=decision.transcript)
        complete_task_run(
            db_session,
            task_run_id=task_run_id,
            task_type=decision.task_type,
            assigned_employee_id=decision.assigned_employee_id,
            result_summary=result_summary,
        )
        write_runtime_message(db_session, session_id=context.session_id, task_run_id=task_run_id, text=runtime_text)
        db_session.commit()
        return RuntimeProcessResult("completed", task_run_id, decision.task_type, None)
    except RuntimeRouteBlocked as exc:
        context = build_runtime_turn_context(db_session, task_run_id=task_run_id)
        result_summary, runtime_text = summarize_failed_task(error_code=exc.error_code, error_message=exc.error_message)
        fail_task_run(db_session, task_run_id=task_run_id, error_code=exc.error_code, error_message=exc.error_message, result_summary=result_summary)
        write_runtime_message(db_session, session_id=context.session_id, task_run_id=task_run_id, text=runtime_text)
        db_session.commit()
        return RuntimeProcessResult("failed", task_run_id, None, exc.error_code)
```

- [ ] **Step 4: Re-run the processor tests to verify they pass**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_runtime_processor.py -q
```

Expected:

- all runtime processor tests pass

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/task_runs.py backend/app/services/runtime_messages.py backend/app/runtime/context.py backend/app/runtime/summarizer.py backend/app/runtime/processor.py backend/tests/test_runtime_processor.py
git commit -m "feat: add runtime dry-run processor"
```

### Task 3: Add worker dispatch, task-run polling API, and integration tests

**Files:**
- Create: `backend/app/services/runtime_dispatch.py`
- Create: `backend/app/workers/runtime_tasks.py`
- Modify: `backend/app/workers/celery_app.py`
- Create: `backend/app/contracts/task_run.py`
- Create: `backend/app/api/routes/task_runs.py`
- Modify: `backend/app/api/routes/messages.py`
- Modify: `backend/app/api/router.py`
- Modify: `backend/tests/test_messages.py`
- Create: `backend/tests/test_runtime_tasks.py`
- Create: `backend/tests/test_task_runs.py`
- Modify: `backend/tests/test_worker_bootstrap.py`

- [ ] **Step 1: Write the failing integration tests**

```python
def test_create_message_dispatches_runtime_once_for_fresh_create(client, monkeypatch):
    delay_mock = Mock()
    monkeypatch.setattr("app.api.routes.messages.enqueue_runtime_task", delay_mock)

    response = client.post(
        "/api/v1/sessions/sess_default/messages",
        headers={"Authorization": "Bearer mock_owner_token"},
        json={"message_type": "text", "text": "restock cola", "media_ids": [], "client_request_id": "route_dispatch_001"},
    )

    assert response.status_code == 201
    delay_mock.assert_called_once_with(response.json()["data"]["task_run_id"])


def test_get_task_run_returns_runtime_state(client):
    create_response = client.post(
        "/api/v1/sessions/sess_default/messages",
        headers={"Authorization": "Bearer mock_owner_token"},
        json={"message_type": "text", "text": "check stock left", "media_ids": [], "client_request_id": "task_route_001"},
    )
    task_run_id = create_response.json()["data"]["task_run_id"]

    response = client.get(f"/api/v1/task-runs/{task_run_id}", headers={"Authorization": "Bearer mock_owner_token"})

    assert response.status_code == 200
    assert response.json()["data"]["task_run_id"] == task_run_id
```

- [ ] **Step 2: Run the integration tests to verify they fail**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_runtime_tasks.py backend/tests/test_task_runs.py backend/tests/test_messages.py backend/tests/test_worker_bootstrap.py -q
```

Expected:

- import failures for `app.workers.runtime_tasks` or 404 for `/api/v1/task-runs/{task_run_id}`

- [ ] **Step 3: Add dispatch helper, Celery task, task-run contract/route, and route wiring**

`backend/app/services/runtime_dispatch.py`

```python
import logging

from app.workers.runtime_tasks import process_task_run

logger = logging.getLogger(__name__)


def enqueue_runtime_task(task_run_id: str) -> bool:
    try:
        process_task_run.delay(task_run_id)
    except Exception:
        logger.warning("Failed to dispatch runtime task", extra={"task_run_id": task_run_id})
        return False
    return True
```

`backend/app/workers/runtime_tasks.py`

```python
@celery_app.task(name="app.workers.runtime_tasks.process_task_run")
def process_task_run(task_run_id: str) -> dict[str, str | None]:
    session = get_session_factory()()
    try:
        result = run_runtime_task(session, task_run_id)
        return {
            "status": result.status,
            "task_run_id": result.task_run_id,
            "task_type": result.task_type,
            "error_code": result.error_code,
        }
    finally:
        session.close()
```

`backend/app/contracts/task_run.py`

```python
class TaskRunData(BaseModel):
    task_run_id: str
    session_id: str
    source_message_id: str
    task_type: str
    status: str
    assigned_employee_id: str | None
    result_summary: str | None
    error_code: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
```

Route wiring requirements:

- `backend/app/api/routes/task_runs.py` adds read-only `GET /api/v1/task-runs/{task_run_id}`
- `backend/app/api/routes/messages.py` imports `enqueue_runtime_task` and calls it only when `result.replayed` is `False`
- `backend/app/api/router.py` includes `task_runs_router`
- `backend/app/workers/celery_app.py` includes `app.workers.runtime_tasks`

- [ ] **Step 4: Re-run the integration tests to verify they pass**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_runtime_tasks.py backend/tests/test_task_runs.py backend/tests/test_messages.py backend/tests/test_worker_bootstrap.py -q
```

Expected:

- all integration tests pass

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/runtime_dispatch.py backend/app/workers/runtime_tasks.py backend/app/workers/celery_app.py backend/app/contracts/task_run.py backend/app/api/routes/task_runs.py backend/app/api/routes/messages.py backend/app/api/router.py backend/tests/test_runtime_tasks.py backend/tests/test_task_runs.py backend/tests/test_messages.py backend/tests/test_worker_bootstrap.py
git commit -m "feat: add runtime worker dispatch and task polling"
```

### Task 4: Verify and document the full Phase 4A slice

**Files:**
- Modify: `backend/app/runtime/README.md`
- Modify: `infra/docker/README.md`

- [ ] **Step 1: Update runtime and infra docs**

`backend/app/runtime/README.md`

```md
# Runtime Skeleton

Phase 4A turns this package into a real read-only dry-run runtime. It now contains deterministic routing, a minimal allow/block policy guard, a mock transcription tool, summarization, and a task processor used by the Celery worker.

It still does not implement confirmations, inventory writes, audit writes, or WebSocket fanout.
```

`infra/docker/README.md`

```md
Phase 4A adds a dry-run runtime worker on top of the message/task ledger. The worker consumes freshly created task runs asynchronously and writes read-only runtime outcomes back into the message stream, while still avoiding confirmation, inventory, audit, and WebSocket dependencies.
```

- [ ] **Step 2: Run the runtime-focused tests**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_runtime_router.py backend/tests/test_runtime_processor.py backend/tests/test_runtime_tasks.py backend/tests/test_task_runs.py -q
```

Expected:

- all runtime-focused tests pass

- [ ] **Step 3: Run the full verification suite**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests -q
npm --prefix apps/mobile test -- --runInBand
docker compose -f infra/docker/docker-compose.yml --env-file .env.example config
git status --short
```

Expected:

- backend tests all pass
- mobile tests pass
- compose config exits `0`
- git status only shows the Phase 4A files before the final docs commit

- [ ] **Step 4: Commit the verification/docs finish**

```bash
git add backend/app/runtime/README.md infra/docker/README.md
git commit -m "test: verify phase 4a runtime dry-run worker"
```
