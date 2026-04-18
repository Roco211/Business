from datetime import datetime

from pydantic import BaseModel, Field


class V2CreateSessionRequest(BaseModel):
    session_type: str
    title: str


class V2SessionData(BaseModel):
    session_id: str
    tenant_id: str
    shop_id: str
    session_type: str
    title: str
    status: str
    initiated_by_account_id: str


class V2SessionListData(BaseModel):
    sessions: list[V2SessionData]


class V2CreateMessageRequest(BaseModel):
    message_kind: str
    payload_json: dict[str, object]
    client_request_id: str | None = None
    intent_type: str | None = None


class V2CreateMessageData(BaseModel):
    message_id: str
    task_run_id: str
    intent_type: str
    status: str


class V2MessageData(BaseModel):
    message_id: str
    tenant_id: str
    shop_id: str
    session_id: str
    actor_type: str
    actor_id: str
    message_kind: str
    payload_json: dict[str, object]
    client_request_id: str | None
    created_at: datetime


class V2MessageListData(BaseModel):
    messages: list[V2MessageData]


class V2TaskRunData(BaseModel):
    task_run_id: str
    tenant_id: str
    shop_id: str
    session_id: str
    source_message_id: str
    intent_type: str
    status: str
    risk_level: str
    trace_id: str
    result_summary: str | None
    error_code: str | None
    draft_payload: dict[str, object] | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class V2CreateTaskDraftRequest(BaseModel):
    draft_type: str
    draft_payload: dict[str, object] = Field(default_factory=dict)


class V2RequestConfirmationFromDraftRequest(BaseModel):
    confirmation_type: str


class V2ApproveConfirmationRequest(BaseModel):
    resolution_payload: dict[str, object] = Field(default_factory=dict)


class V2ConfirmationData(BaseModel):
    confirmation_id: str
    tenant_id: str
    shop_id: str
    task_run_id: str
    confirmation_type: str
    status: str
    draft_payload: dict[str, object]
    approved_by_account_id: str | None
    resolution_payload: dict[str, object] | None
    created_at: datetime
    resolved_at: datetime | None


class V2ConfirmationListData(BaseModel):
    confirmations: list[V2ConfirmationData]
    count: int


class V2AnswerClarificationRequest(BaseModel):
    answer_payload: dict[str, object] = Field(default_factory=dict)


class V2ClarificationData(BaseModel):
    clarification_id: str
    tenant_id: str
    shop_id: str
    task_run_id: str
    status: str
    reason_code: str
    question_text: str
    requested_fields: list[str]
    draft_payload: dict[str, object] | None
    answer_payload: dict[str, object] | None
    answered_by_account_id: str | None
    created_at: datetime
    answered_at: datetime | None


class V2ClarificationListData(BaseModel):
    clarifications: list[V2ClarificationData]
    count: int
