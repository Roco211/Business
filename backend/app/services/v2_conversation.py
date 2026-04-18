from dataclasses import dataclass
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    V2Clarification,
    V2Confirmation,
    V2ConversationSession,
    V2Message,
    V2TaskDraft,
    V2TaskRun,
)
from app.services.v2_confirmation_provenance import build_v2_confirmation_source_payload
from app.services.v2_commit_records import append_v2_inventory_commit_records
from app.services.v2_inventory import (
    commit_v2_inventory_stock_in,
    commit_v2_inventory_stock_out,
    validate_v2_stock_in_draft_payload,
    validate_v2_stock_out_draft_payload,
)
from app.services.v2_outbox_runtime_dispatch import enqueue_v2_outbox_drain
from app.services.v2_session_stream import append_v2_session_event
from app.services.v2_time import utc_now_naive

CAPTURED_STATUS = "captured"
INTERPRETING_STATUS = "interpreting"
DRAFTED_STATUS = "drafted"
NEEDS_CLARIFICATION_STATUS = "needs_clarification"
AWAITING_CONFIRMATION_STATUS = "awaiting_confirmation"
EXECUTING_STATUS = "executing"
COMMITTED_STATUS = "committed"
REJECTED_STATUS = "rejected"
PENDING_STATUS = "pending"
APPROVED_STATUS = "approved"
ANSWERED_STATUS = "answered"
SYSTEM_ACTOR_TYPE = "system"
RUNTIME_SYSTEM_ACTOR_ID = "runtime_system"
SYSTEM_RESULT_MESSAGE_KIND = "system_result"
GENERIC_DRAFT_TYPES = {"conversation.capture", "document.receipt.extract"}
ALLOWED_V2_MESSAGE_INTENTS = {
    "conversation.capture",
    "inventory.stock_in",
    "inventory.stock_out",
}
ALLOWED_V2_TASK_DRAFT_TYPES = {
    "inventory.stock_in",
    "inventory.stock_out",
}


class V2TaskRunTransitionError(ValueError):
    pass


class V2ConfirmationConflictError(ValueError):
    pass


class V2TaskDraftNotReadyError(ValueError):
    pass


class V2ConfirmationTypeMismatchError(ValueError):
    pass


class V2UnsupportedIntentTypeError(ValueError):
    pass


class V2UnsupportedDraftTypeError(ValueError):
    pass


class V2TaskDraftTypeMismatchError(ValueError):
    pass


@dataclass(frozen=True)
class CreatedV2Session:
    session_id: str
    tenant_id: str
    shop_id: str
    session_type: str
    title: str
    status: str
    initiated_by_account_id: str


def create_v2_session(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    initiated_by_account_id: str,
    session_type: str,
    title: str,
) -> CreatedV2Session:
    now = utc_now_naive()
    session = V2ConversationSession(
        session_id=f"vsess_{uuid.uuid4().hex}"[:40],
        tenant_id=tenant_id,
        shop_id=shop_id,
        session_type=session_type,
        title=title,
        status="active",
        initiated_by_account_id=initiated_by_account_id,
        created_at=now,
        updated_at=now,
    )
    db_session.add(session)
    db_session.commit()
    return CreatedV2Session(
        session_id=session.session_id,
        tenant_id=session.tenant_id,
        shop_id=session.shop_id,
        session_type=session.session_type,
        title=session.title,
        status=session.status,
        initiated_by_account_id=session.initiated_by_account_id,
    )


def list_v2_sessions(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
) -> list[V2ConversationSession]:
    return list(
        db_session.scalars(
            select(V2ConversationSession)
            .where(
                V2ConversationSession.tenant_id == tenant_id,
                V2ConversationSession.shop_id == shop_id,
            )
            .order_by(V2ConversationSession.created_at.desc(), V2ConversationSession.session_id.desc())
        )
    )


def get_v2_session(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    session_id: str,
) -> V2ConversationSession | None:
    return db_session.scalar(
        select(V2ConversationSession).where(
            V2ConversationSession.session_id == session_id,
            V2ConversationSession.tenant_id == tenant_id,
            V2ConversationSession.shop_id == shop_id,
        )
    )


def _message_preview_text(payload_json: dict[str, object], message_kind: str) -> str:
    text = payload_json.get("text")
    if isinstance(text, str) and text.strip():
        return text.strip()
    return message_kind


def _resolve_v2_message_event_task_run_id(message: V2Message) -> str | None:
    raw_task_run_id = message.payload_json.get("task_run_id")
    if isinstance(raw_task_run_id, str) and raw_task_run_id.strip():
        return raw_task_run_id.strip()
    return None


def _build_v2_message_created_event_data(message: V2Message) -> dict[str, object]:
    data: dict[str, object] = {
        "message_kind": message.message_kind,
        "actor_type": message.actor_type,
        "actor_id": message.actor_id,
        "preview_text": _message_preview_text(message.payload_json, message.message_kind),
    }
    if message.message_kind == SYSTEM_RESULT_MESSAGE_KIND:
        data["payload_json"] = dict(message.payload_json)
    return data


def _build_v2_system_result_source_payload(confirmation: V2Confirmation) -> dict[str, str]:
    return {
        key: value
        for key, value in build_v2_confirmation_source_payload(confirmation).items()
        if value is not None
    }


def _is_v2_receipt_derived_confirmation(confirmation: V2Confirmation) -> bool:
    return build_v2_confirmation_source_payload(confirmation).get("source_type") == "receipt-document"


def append_v2_message_created_event(
    db_session: Session,
    *,
    message: V2Message,
) -> None:
    append_v2_session_event(
        db_session,
        tenant_id=message.tenant_id,
        shop_id=message.shop_id,
        session_id=message.session_id,
        event_type="message.created",
        task_run_id=_resolve_v2_message_event_task_run_id(message),
        message_id=message.message_id,
        data=_build_v2_message_created_event_data(message),
        occurred_at=message.created_at,
    )


def append_v2_task_updated_event(
    db_session: Session,
    *,
    task_run: V2TaskRun,
) -> None:
    append_v2_session_event(
        db_session,
        tenant_id=task_run.tenant_id,
        shop_id=task_run.shop_id,
        session_id=task_run.session_id,
        event_type="task.updated",
        task_run_id=task_run.task_run_id,
        message_id=task_run.source_message_id,
        data={
            "status": task_run.status,
            "intent_type": task_run.intent_type,
            "error_code": task_run.error_code,
        },
        occurred_at=task_run.updated_at,
    )


def create_v2_message_and_task_run(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    session_id: str,
    actor_id: str,
    message_kind: str,
    payload_json: dict[str, object],
    client_request_id: str | None,
    intent_type: str | None,
) -> tuple[V2Message, V2TaskRun] | None:
    session = get_v2_session(
        db_session,
        tenant_id=tenant_id,
        shop_id=shop_id,
        session_id=session_id,
    )
    if session is None:
        return None

    normalized_intent_type = _normalize_v2_message_intent(intent_type)
    now = utc_now_naive()
    message = V2Message(
        message_id=f"vmsg_{uuid.uuid4().hex}"[:40],
        tenant_id=tenant_id,
        shop_id=shop_id,
        session_id=session_id,
        actor_type="account",
        actor_id=actor_id,
        message_kind=message_kind,
        payload_json=payload_json,
        client_request_id=client_request_id,
        created_at=now,
    )
    task_run = V2TaskRun(
        task_run_id=f"vtask_{uuid.uuid4().hex}"[:40],
        tenant_id=tenant_id,
        shop_id=shop_id,
        session_id=session_id,
        source_message_id=message.message_id,
        intent_type=normalized_intent_type,
        status="captured",
        risk_level="unknown",
        trace_id=f"trace_{uuid.uuid4().hex}",
        result_summary=None,
        error_code=None,
        created_at=now,
        updated_at=now,
        completed_at=None,
    )
    db_session.add(message)
    db_session.add(task_run)
    append_v2_message_created_event(db_session, message=message)
    append_v2_task_updated_event(db_session, task_run=task_run)
    db_session.commit()
    return message, task_run


def _normalize_v2_message_intent(intent_type: str | None) -> str:
    normalized = (intent_type or "conversation.capture").strip()
    if normalized not in ALLOWED_V2_MESSAGE_INTENTS:
        raise V2UnsupportedIntentTypeError(f"Unsupported intent_type '{normalized}'.")
    return normalized


def _normalize_v2_task_draft_type(draft_type: str) -> str:
    normalized = draft_type.strip()
    if normalized not in ALLOWED_V2_TASK_DRAFT_TYPES:
        raise V2UnsupportedDraftTypeError(f"Unsupported draft_type '{normalized}'.")
    return normalized


def list_v2_messages(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    session_id: str,
) -> list[V2Message]:
    return list(
        db_session.scalars(
            select(V2Message)
            .where(
                V2Message.tenant_id == tenant_id,
                V2Message.shop_id == shop_id,
                V2Message.session_id == session_id,
            )
            .order_by(V2Message.created_at.asc(), V2Message.message_id.asc())
        )
    )


def append_v2_system_result_message(
    db_session: Session,
    *,
    task_run: V2TaskRun,
    confirmation: V2Confirmation,
    text: str,
) -> V2Message:
    now = utc_now_naive()
    source_payload = _build_v2_system_result_source_payload(confirmation)
    message = V2Message(
        message_id=f"vmsg_{uuid.uuid4().hex}"[:40],
        tenant_id=task_run.tenant_id,
        shop_id=task_run.shop_id,
        session_id=task_run.session_id,
        actor_type=SYSTEM_ACTOR_TYPE,
        actor_id=RUNTIME_SYSTEM_ACTOR_ID,
        message_kind=SYSTEM_RESULT_MESSAGE_KIND,
        payload_json={
            "text": text,
            "task_run_id": task_run.task_run_id,
            "task_run_status": task_run.status,
            "intent_type": task_run.intent_type,
            "confirmation_id": confirmation.confirmation_id,
            "confirmation_type": confirmation.confirmation_type,
            **source_payload,
        },
        client_request_id=None,
        created_at=now,
    )
    db_session.add(message)
    append_v2_message_created_event(db_session, message=message)
    return message


def get_v2_task_run(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    task_run_id: str,
) -> V2TaskRun | None:
    return db_session.scalar(
        select(V2TaskRun).where(
            V2TaskRun.task_run_id == task_run_id,
            V2TaskRun.tenant_id == tenant_id,
            V2TaskRun.shop_id == shop_id,
        )
    )


def get_v2_task_draft(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    task_run_id: str,
) -> V2TaskDraft | None:
    return db_session.scalar(
        select(V2TaskDraft).where(
            V2TaskDraft.task_run_id == task_run_id,
            V2TaskDraft.tenant_id == tenant_id,
            V2TaskDraft.shop_id == shop_id,
        )
    )


def upsert_v2_task_draft(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    task_run_id: str,
    draft_type: str,
    draft_payload: dict[str, object],
    created_by_account_id: str,
) -> V2TaskRun:
    normalized_draft_type = _normalize_v2_task_draft_type(draft_type)
    task_run = _require_v2_task_run_for_context(
        db_session,
        tenant_id=tenant_id,
        shop_id=shop_id,
        task_run_id=task_run_id,
    )
    if task_run.status not in {CAPTURED_STATUS, DRAFTED_STATUS}:
        raise V2TaskRunTransitionError(
            f"Task run {task_run_id} cannot accept draft updates from status '{task_run.status}'."
        )
    should_specialize_generic_task = task_run.intent_type in GENERIC_DRAFT_TYPES
    if not should_specialize_generic_task and task_run.intent_type != normalized_draft_type:
        raise V2TaskDraftTypeMismatchError(
            f"Task run {task_run_id} intent type '{task_run.intent_type}' does not match draft type '{normalized_draft_type}'."
        )

    if normalized_draft_type == "inventory.stock_in":
        validate_v2_stock_in_draft_payload(draft_payload)
    elif normalized_draft_type == "inventory.stock_out":
        validate_v2_stock_out_draft_payload(draft_payload)

    now = utc_now_naive()
    if should_specialize_generic_task:
        task_run.intent_type = normalized_draft_type
    _upsert_v2_task_draft(
        db_session,
        tenant_id=tenant_id,
        shop_id=shop_id,
        task_run=task_run,
        draft_payload=dict(draft_payload),
        created_by_account_id=created_by_account_id,
        now=now,
    )
    task_run.status = DRAFTED_STATUS
    task_run.result_summary = "Task draft is ready for confirmation."
    task_run.error_code = None
    task_run.updated_at = now
    task_run.completed_at = None
    append_v2_task_updated_event(db_session, task_run=task_run)
    db_session.commit()
    return task_run


def _require_v2_task_run_for_context(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    task_run_id: str,
) -> V2TaskRun:
    task_run = db_session.scalar(
        select(V2TaskRun)
        .where(
            V2TaskRun.task_run_id == task_run_id,
            V2TaskRun.tenant_id == tenant_id,
            V2TaskRun.shop_id == shop_id,
        )
        .execution_options(populate_existing=True)
    )
    if task_run is None:
        raise LookupError(task_run_id)
    return task_run


def _upsert_v2_task_draft(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    task_run: V2TaskRun,
    draft_payload: dict[str, object],
    created_by_account_id: str,
    now,
) -> V2TaskDraft:
    draft = get_v2_task_draft(
        db_session,
        tenant_id=tenant_id,
        shop_id=shop_id,
        task_run_id=task_run.task_run_id,
    )
    if draft is None:
        draft = V2TaskDraft(
            task_draft_id=f"vdraft_{uuid.uuid4().hex}"[:40],
            tenant_id=tenant_id,
            shop_id=shop_id,
            task_run_id=task_run.task_run_id,
            draft_type=task_run.intent_type,
            payload_json=draft_payload,
            created_by_account_id=created_by_account_id,
            created_at=now,
            updated_at=now,
        )
        db_session.add(draft)
        return draft

    draft.draft_type = task_run.intent_type
    draft.payload_json = draft_payload
    draft.updated_at = now
    return draft


def create_v2_clarification(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    task_run_id: str,
    reason_code: str,
    question_text: str,
    requested_fields: list[str],
    draft_payload: dict[str, object] | None,
) -> V2Clarification:
    existing = db_session.scalar(
        select(V2Clarification)
        .where(V2Clarification.task_run_id == task_run_id)
        .execution_options(populate_existing=True)
    )
    if existing is not None:
        if existing.status == PENDING_STATUS:
            return existing
        raise V2ConfirmationConflictError(
            f"Task run {task_run_id} already has a non-pending clarification in status '{existing.status}'."
        )

    task_run = _require_v2_task_run_for_context(
        db_session,
        tenant_id=tenant_id,
        shop_id=shop_id,
        task_run_id=task_run_id,
    )
    if task_run.status not in {CAPTURED_STATUS, INTERPRETING_STATUS}:
        raise V2TaskRunTransitionError(
            f"Task run {task_run_id} cannot request clarification from status '{task_run.status}'."
        )

    now = utc_now_naive()
    clarification = V2Clarification(
        clarification_id=f"vclar_{uuid.uuid4().hex}"[:40],
        tenant_id=tenant_id,
        shop_id=shop_id,
        task_run_id=task_run_id,
        status=PENDING_STATUS,
        reason_code=reason_code,
        question_text=question_text,
        requested_fields=requested_fields,
        draft_payload=draft_payload,
        answer_payload=None,
        answered_by_account_id=None,
        created_at=now,
        answered_at=None,
    )
    task_run.status = NEEDS_CLARIFICATION_STATUS
    task_run.result_summary = question_text
    task_run.updated_at = now
    task_run.completed_at = None
    db_session.add(clarification)
    append_v2_task_updated_event(db_session, task_run=task_run)
    db_session.commit()
    return clarification


def create_v2_confirmation(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    task_run_id: str,
    confirmation_type: str,
    draft_payload: dict[str, object],
) -> V2Confirmation:
    existing = db_session.scalar(
        select(V2Confirmation)
        .where(V2Confirmation.task_run_id == task_run_id)
        .execution_options(populate_existing=True)
    )
    if existing is not None:
        if existing.status == PENDING_STATUS:
            return existing
        raise V2ConfirmationConflictError(
            f"Task run {task_run_id} already has a non-pending confirmation in status '{existing.status}'."
        )

    task_run = _require_v2_task_run_for_context(
        db_session,
        tenant_id=tenant_id,
        shop_id=shop_id,
        task_run_id=task_run_id,
    )
    if task_run.status not in {CAPTURED_STATUS, DRAFTED_STATUS}:
        raise V2TaskRunTransitionError(
            f"Task run {task_run_id} cannot await confirmation from status '{task_run.status}'."
        )

    now = utc_now_naive()
    confirmation = V2Confirmation(
        confirmation_id=f"vconf_{uuid.uuid4().hex}"[:40],
        tenant_id=tenant_id,
        shop_id=shop_id,
        task_run_id=task_run_id,
        confirmation_type=confirmation_type,
        status=PENDING_STATUS,
        draft_payload=draft_payload,
        approved_by_account_id=None,
        resolution_payload=None,
        created_at=now,
        resolved_at=None,
    )
    task_run.status = AWAITING_CONFIRMATION_STATUS
    task_run.result_summary = "Awaiting confirmation."
    task_run.updated_at = now
    task_run.completed_at = None
    db_session.add(confirmation)
    append_v2_task_updated_event(db_session, task_run=task_run)
    db_session.commit()
    return confirmation


def list_v2_clarifications(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    status: str | None,
    limit: int,
) -> list[V2Clarification]:
    safe_limit = max(1, min(limit, 50))
    statement = select(V2Clarification).where(
        V2Clarification.tenant_id == tenant_id,
        V2Clarification.shop_id == shop_id,
    )
    if status is not None:
        statement = statement.where(V2Clarification.status == status)
    statement = statement.order_by(V2Clarification.created_at.desc(), V2Clarification.clarification_id.desc()).limit(
        safe_limit
    )
    return list(db_session.scalars(statement))


def _require_v2_clarification_for_context(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    clarification_id: str,
) -> V2Clarification:
    clarification = db_session.scalar(
        select(V2Clarification)
        .where(
            V2Clarification.clarification_id == clarification_id,
            V2Clarification.tenant_id == tenant_id,
            V2Clarification.shop_id == shop_id,
        )
        .execution_options(populate_existing=True)
    )
    if clarification is None:
        raise LookupError(clarification_id)
    return clarification


def answer_v2_clarification(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    clarification_id: str,
    answer_payload: dict[str, object],
    answered_by_account_id: str,
) -> V2Clarification:
    clarification = _require_v2_clarification_for_context(
        db_session,
        tenant_id=tenant_id,
        shop_id=shop_id,
        clarification_id=clarification_id,
    )
    if clarification.status != PENDING_STATUS:
        raise V2ConfirmationConflictError(
            f"Clarification {clarification_id} must be pending; found '{clarification.status}'."
        )

    task_run = _require_v2_task_run_for_context(
        db_session,
        tenant_id=tenant_id,
        shop_id=shop_id,
        task_run_id=clarification.task_run_id,
    )
    if task_run.status != NEEDS_CLARIFICATION_STATUS:
        raise V2TaskRunTransitionError(
            f"Task run {task_run.task_run_id} must be awaiting clarification; found '{task_run.status}'."
        )

    now = utc_now_naive()
    clarification.status = ANSWERED_STATUS
    clarification.answer_payload = answer_payload
    clarification.answered_by_account_id = answered_by_account_id
    clarification.answered_at = now
    merged_draft_payload = dict(clarification.draft_payload or {})
    merged_draft_payload.update(answer_payload)
    _upsert_v2_task_draft(
        db_session,
        tenant_id=tenant_id,
        shop_id=shop_id,
        task_run=task_run,
        draft_payload=merged_draft_payload,
        created_by_account_id=answered_by_account_id,
        now=now,
    )
    task_run.status = DRAFTED_STATUS
    task_run.result_summary = "Clarification answered; draft is ready for confirmation."
    task_run.error_code = None
    task_run.updated_at = now
    task_run.completed_at = None
    append_v2_task_updated_event(db_session, task_run=task_run)
    db_session.commit()
    return clarification


def request_v2_confirmation_from_task_draft(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    task_run_id: str,
    confirmation_type: str,
) -> V2Confirmation:
    draft = get_v2_task_draft(
        db_session,
        tenant_id=tenant_id,
        shop_id=shop_id,
        task_run_id=task_run_id,
    )
    if draft is None:
        raise V2TaskDraftNotReadyError(f"Task run {task_run_id} does not have a draft yet.")
    should_specialize_generic_draft = draft.draft_type in GENERIC_DRAFT_TYPES
    if draft.draft_type not in GENERIC_DRAFT_TYPES and draft.draft_type != confirmation_type:
        raise V2ConfirmationTypeMismatchError(
            f"Task run {task_run_id} draft type '{draft.draft_type}' does not match confirmation type '{confirmation_type}'."
        )

    task_run = _require_v2_task_run_for_context(
        db_session,
        tenant_id=tenant_id,
        shop_id=shop_id,
        task_run_id=task_run_id,
    )
    if task_run.status != DRAFTED_STATUS:
        raise V2TaskRunTransitionError(
            f"Task run {task_run_id} must be drafted before confirmation; found '{task_run.status}'."
        )
    if should_specialize_generic_draft:
        now = utc_now_naive()
        task_run.intent_type = confirmation_type
        task_run.updated_at = now
        draft.draft_type = confirmation_type
        draft.updated_at = now
        db_session.flush()

    return create_v2_confirmation(
        db_session,
        tenant_id=tenant_id,
        shop_id=shop_id,
        task_run_id=task_run_id,
        confirmation_type=confirmation_type,
        draft_payload=dict(draft.payload_json),
    )


def list_v2_confirmations(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    status: str | None,
    limit: int,
) -> list[V2Confirmation]:
    safe_limit = max(1, min(limit, 50))
    statement = select(V2Confirmation).where(
        V2Confirmation.tenant_id == tenant_id,
        V2Confirmation.shop_id == shop_id,
    )
    if status is not None:
        statement = statement.where(V2Confirmation.status == status)
    statement = statement.order_by(V2Confirmation.created_at.desc(), V2Confirmation.confirmation_id.desc()).limit(
        safe_limit
    )
    return list(db_session.scalars(statement))


def _require_v2_confirmation_for_context(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    confirmation_id: str,
) -> V2Confirmation:
    confirmation = db_session.scalar(
        select(V2Confirmation)
        .where(
            V2Confirmation.confirmation_id == confirmation_id,
            V2Confirmation.tenant_id == tenant_id,
            V2Confirmation.shop_id == shop_id,
        )
        .execution_options(populate_existing=True)
    )
    if confirmation is None:
        raise LookupError(confirmation_id)
    return confirmation


def approve_v2_confirmation(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    confirmation_id: str,
    resolution_payload: dict[str, object],
    approved_by_account_id: str,
) -> V2Confirmation:
    should_enqueue_outbox = False
    try:
        confirmation = _require_v2_confirmation_for_context(
            db_session,
            tenant_id=tenant_id,
            shop_id=shop_id,
            confirmation_id=confirmation_id,
        )
        if confirmation.status != PENDING_STATUS:
            raise V2ConfirmationConflictError(
                f"Confirmation {confirmation_id} must be pending; found '{confirmation.status}'."
            )

        task_run = _require_v2_task_run_for_context(
            db_session,
            tenant_id=tenant_id,
            shop_id=shop_id,
            task_run_id=confirmation.task_run_id,
        )
        if task_run.status != AWAITING_CONFIRMATION_STATUS:
            raise V2TaskRunTransitionError(
                f"Task run {task_run.task_run_id} must be awaiting confirmation; found '{task_run.status}'."
            )

        now = utc_now_naive()
        confirmation.status = APPROVED_STATUS
        confirmation.resolution_payload = resolution_payload
        confirmation.approved_by_account_id = approved_by_account_id
        confirmation.resolved_at = now

        system_result_text: str | None = None
        if confirmation.confirmation_type == "inventory.stock_in":
            resolved_fields = dict(resolution_payload.get("fields") or {})
            commit_result = commit_v2_inventory_stock_in(
                db_session,
                tenant_id=tenant_id,
                shop_id=shop_id,
                task_run_id=task_run.task_run_id,
                created_by_account_id=approved_by_account_id,
                payload=resolved_fields,
            )
            append_v2_inventory_commit_records(
                db_session,
                task_run=task_run,
                confirmation=confirmation,
                actor_type="account",
                actor_id=approved_by_account_id,
                inventory_item=commit_result.item,
                ledger_event=commit_result.event,
            )
            task_run.status = COMMITTED_STATUS
            task_run.result_summary = "Confirmation approved and inventory committed."
            task_run.completed_at = now
            if _is_v2_receipt_derived_confirmation(confirmation):
                system_result_text = "Receipt stock-in committed."
            else:
                system_result_text = "Inventory stock-in committed."
            should_enqueue_outbox = True
        elif confirmation.confirmation_type == "inventory.stock_out":
            resolved_fields = dict(resolution_payload.get("fields") or {})
            commit_result = commit_v2_inventory_stock_out(
                db_session,
                tenant_id=tenant_id,
                shop_id=shop_id,
                inventory_item_id=str(resolved_fields.get("inventory_item_id") or ""),
                expected_quantity=resolved_fields.get("expected_quantity"),
                stock_out_quantity=resolved_fields.get("stock_out_quantity"),
                reason=str(resolved_fields.get("reason") or ""),
                created_by_account_id=approved_by_account_id,
            )
            append_v2_inventory_commit_records(
                db_session,
                task_run=task_run,
                confirmation=confirmation,
                actor_type="account",
                actor_id=approved_by_account_id,
                inventory_item=commit_result.item,
                ledger_event=commit_result.event,
            )
            task_run.status = COMMITTED_STATUS
            task_run.result_summary = "Confirmation approved and inventory committed."
            task_run.completed_at = now
            system_result_text = "Inventory stock-out committed."
            should_enqueue_outbox = True
        else:
            task_run.status = EXECUTING_STATUS
            task_run.result_summary = "Confirmation approved; deterministic execution pending."
            task_run.completed_at = None

        task_run.error_code = None
        task_run.updated_at = now
        if system_result_text is not None:
            append_v2_system_result_message(
                db_session,
                task_run=task_run,
                confirmation=confirmation,
                text=system_result_text,
            )
        append_v2_task_updated_event(db_session, task_run=task_run)
        db_session.commit()
    except Exception:
        db_session.rollback()
        raise
    if should_enqueue_outbox:
        enqueue_v2_outbox_drain(tenant_id=tenant_id, shop_id=shop_id)
    return confirmation


def reject_v2_confirmation(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    confirmation_id: str,
) -> V2Confirmation:
    try:
        confirmation = _require_v2_confirmation_for_context(
            db_session,
            tenant_id=tenant_id,
            shop_id=shop_id,
            confirmation_id=confirmation_id,
        )
        if confirmation.status != PENDING_STATUS:
            raise V2ConfirmationConflictError(
                f"Confirmation {confirmation_id} must be pending; found '{confirmation.status}'."
            )

        task_run = _require_v2_task_run_for_context(
            db_session,
            tenant_id=tenant_id,
            shop_id=shop_id,
            task_run_id=confirmation.task_run_id,
        )
        if task_run.status != AWAITING_CONFIRMATION_STATUS:
            raise V2TaskRunTransitionError(
                f"Task run {task_run.task_run_id} must be awaiting confirmation; found '{task_run.status}'."
            )

        now = utc_now_naive()
        confirmation.status = REJECTED_STATUS
        confirmation.resolution_payload = None
        confirmation.approved_by_account_id = None
        confirmation.resolved_at = now
        task_run.status = REJECTED_STATUS
        task_run.result_summary = "Confirmation rejected."
        task_run.error_code = None
        task_run.updated_at = now
        task_run.completed_at = now
        append_v2_system_result_message(
            db_session,
            task_run=task_run,
            confirmation=confirmation,
            text="Confirmation rejected; no business change committed.",
        )
        append_v2_task_updated_event(db_session, task_run=task_run)
        db_session.commit()
        return confirmation
    except Exception:
        db_session.rollback()
        raise
