from datetime import UTC, datetime
from decimal import Decimal


def _utc_now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _seed_v2_task_run(db_session, *, task_run_id: str = "vtask_001") -> None:
    from app.models import (
        V2Account,
        V2ConversationSession,
        V2Message,
        V2Shop,
        V2TaskRun,
        V2Tenant,
    )

    now = _utc_now_naive()
    db_session.add(
        V2Account(
            account_id="acct_001",
            email="owner@example.com",
            display_name="Owner",
            password_hash="hash",
            password_salt="salt",
            status="active",
            created_at=now,
            updated_at=now,
        )
    )
    db_session.add(
        V2Tenant(
            tenant_id="tenant_a",
            name="Tenant A",
            slug="tenant-a",
            status="active",
            plan_code="trial",
            owner_account_id="acct_001",
            created_at=now,
            updated_at=now,
        )
    )
    db_session.add(
        V2Shop(
            shop_id="shop_a1",
            tenant_id="tenant_a",
            code="a-1",
            name="Shop A1",
            locale="zh-CN",
            timezone="Asia/Shanghai",
            status="active",
            created_at=now,
            updated_at=now,
        )
    )
    db_session.add(
        V2ConversationSession(
            session_id="vsess_001",
            tenant_id="tenant_a",
            shop_id="shop_a1",
            session_type="workgroup",
            title="Workgroup",
            status="active",
            initiated_by_account_id="acct_001",
            created_at=now,
            updated_at=now,
        )
    )
    db_session.add(
        V2Message(
            message_id="vmsg_001",
            tenant_id="tenant_a",
            shop_id="shop_a1",
            session_id="vsess_001",
            actor_type="account",
            actor_id="acct_001",
            message_kind="text",
            payload_json={"text": "restock cola"},
            client_request_id="req_001",
            created_at=now,
        )
    )
    db_session.add(
        V2TaskRun(
            task_run_id=task_run_id,
            tenant_id="tenant_a",
            shop_id="shop_a1",
            session_id="vsess_001",
            source_message_id="vmsg_001",
            intent_type="inventory.stock_in",
            status="captured",
            risk_level="medium",
            trace_id="trace_001",
            result_summary=None,
            error_code=None,
            created_at=now,
            updated_at=now,
            completed_at=None,
        )
    )
    db_session.commit()


def _seed_v2_identity_for_api(db_session) -> None:
    from app.models import V2Account, V2Shop, V2ShopAccess, V2Tenant, V2TenantMembership
    from app.services.v2_identity import hash_v2_password

    now = _utc_now_naive()
    password_salt = "11" * 16
    db_session.add(
        V2Account(
            account_id="acct_001",
            email="owner@example.com",
            display_name="Owner",
            password_hash=hash_v2_password("dev-password", password_salt),
            password_salt=password_salt,
            status="active",
            created_at=now,
            updated_at=now,
        )
    )
    db_session.add(
        V2Tenant(
            tenant_id="tenant_a",
            name="Tenant A",
            slug="tenant-a",
            status="active",
            plan_code="trial",
            owner_account_id="acct_001",
            created_at=now,
            updated_at=now,
        )
    )
    db_session.add(
        V2TenantMembership(
            membership_id="mship_tenant_a",
            tenant_id="tenant_a",
            account_id="acct_001",
            role_key="owner",
            status="active",
            joined_at=now,
            updated_at=now,
        )
    )
    db_session.add(
        V2Shop(
            shop_id="shop_a1",
            tenant_id="tenant_a",
            code="a-1",
            name="Shop A1",
            locale="zh-CN",
            timezone="Asia/Shanghai",
            status="active",
            created_at=now,
            updated_at=now,
        )
    )
    db_session.add(
        V2ShopAccess(
            shop_access_id="access_shop_a1",
            tenant_id="tenant_a",
            shop_id="shop_a1",
            membership_id="mship_tenant_a",
            access_level="write",
            status="active",
            created_at=now,
        )
    )
    db_session.commit()


def _create_api_task_run(client, db_session, *, intent_type: str | None = None) -> tuple[str, str, str]:
    token, context_token = _create_api_identity_context(client, db_session)
    session_response = client.post(
        "/api/v2/sessions",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={"session_type": "workgroup", "title": "Workgroup"},
    )
    assert session_response.status_code == 201
    session_id = session_response.json()["data"]["session_id"]

    message_payload = {
        "message_kind": "text",
        "payload_json": {"text": "restock cola"},
        "client_request_id": "confirm_api_msg",
    }
    if intent_type is not None:
        message_payload["intent_type"] = intent_type

    message_response = client.post(
        f"/api/v2/sessions/{session_id}/messages",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json=message_payload,
    )
    assert message_response.status_code == 201
    task_run_id = message_response.json()["data"]["task_run_id"]
    return token, context_token, task_run_id


def _create_api_identity_context(client, db_session) -> tuple[str, str]:
    _seed_v2_identity_for_api(db_session)
    login_response = client.post(
        "/api/v2/auth/login",
        json={"email": "owner@example.com", "password": "dev-password"},
    )
    assert login_response.status_code == 200
    token = login_response.json()["data"]["access_token"]

    context_response = client.post(
        "/api/v2/context/select",
        headers={"Authorization": f"Bearer {token}"},
        json={"tenant_id": "tenant_a", "shop_id": "shop_a1"},
    )
    assert context_response.status_code == 200
    return token, context_response.json()["data"]["context_token"]


def _list_v2_stream_events(client, *, token: str, context_token: str, session_id: str) -> list[dict[str, object]]:
    response = client.get(
        f"/api/v2/sessions/{session_id}/stream-events?after_seq=0",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
    )
    assert response.status_code == 200
    return response.json()["data"]["events"]


def _seed_v2_inventory_task_run_in_existing_context(
    db_session,
    *,
    task_run_id: str,
    intent_type: str = "inventory.stock_in",
) -> None:
    from app.models import V2ConversationSession, V2Message, V2TaskRun

    now = _utc_now_naive()
    session_id = f"vsess_{task_run_id}"[:40]
    message_id = f"vmsg_{task_run_id}"[:40]
    db_session.add(
        V2ConversationSession(
            session_id=session_id,
            tenant_id="tenant_a",
            shop_id="shop_a1",
            session_type="workgroup",
            title="Inventory Seed",
            status="active",
            initiated_by_account_id="acct_001",
            created_at=now,
            updated_at=now,
        )
    )
    db_session.add(
        V2Message(
            message_id=message_id,
            tenant_id="tenant_a",
            shop_id="shop_a1",
            session_id=session_id,
            actor_type="account",
            actor_id="acct_001",
            message_kind="text",
            payload_json={"text": "seed inventory"},
            client_request_id=f"req_{task_run_id}"[:64],
            created_at=now,
        )
    )
    db_session.add(
        V2TaskRun(
            task_run_id=task_run_id,
            tenant_id="tenant_a",
            shop_id="shop_a1",
            session_id=session_id,
            source_message_id=message_id,
            intent_type=intent_type,
            status="captured",
            risk_level="medium",
            trace_id=f"trace_{task_run_id}"[:64],
            result_summary=None,
            error_code=None,
            created_at=now,
            updated_at=now,
            completed_at=None,
        )
    )
    db_session.commit()


def test_v2_clarification_and_confirmation_schema_persist_context_boundaries(db_session) -> None:
    from sqlalchemy import select

    from app.models import V2Clarification, V2Confirmation

    now = _utc_now_naive()
    _seed_v2_task_run(db_session)
    clarification = V2Clarification(
        clarification_id="vclar_001",
        tenant_id="tenant_a",
        shop_id="shop_a1",
        task_run_id="vtask_001",
        status="pending",
        reason_code="missing_quantity",
        question_text="How many boxes should be stocked in?",
        requested_fields=["quantity"],
        draft_payload={"item_name": "Cola"},
        answer_payload=None,
        answered_by_account_id=None,
        created_at=now,
        answered_at=None,
    )
    confirmation = V2Confirmation(
        confirmation_id="vconf_001",
        tenant_id="tenant_a",
        shop_id="shop_a1",
        task_run_id="vtask_001",
        confirmation_type="inventory.stock_in",
        status="pending",
        draft_payload={"item_name": "Cola", "quantity": 2},
        approved_by_account_id=None,
        resolution_payload=None,
        created_at=now,
        resolved_at=None,
    )
    db_session.add_all([clarification, confirmation])
    db_session.commit()

    persisted = db_session.scalar(
        select(V2Confirmation).where(V2Confirmation.confirmation_id == "vconf_001")
    )

    assert persisted is not None
    assert persisted.tenant_id == "tenant_a"
    assert persisted.shop_id == "shop_a1"


def test_v2_task_draft_schema_persists_context_boundaries(db_session) -> None:
    from sqlalchemy import select

    from app.models import V2TaskDraft

    now = _utc_now_naive()
    _seed_v2_task_run(db_session, task_run_id="vtask_draft_schema")
    draft = V2TaskDraft(
        task_draft_id="vdraft_001",
        tenant_id="tenant_a",
        shop_id="shop_a1",
        task_run_id="vtask_draft_schema",
        draft_type="inventory.stock_in",
        payload_json={"item_name": "Cola", "quantity": 2, "unit": "box"},
        created_by_account_id="acct_001",
        created_at=now,
        updated_at=now,
    )
    db_session.add(draft)
    db_session.commit()

    persisted = db_session.scalar(
        select(V2TaskDraft).where(V2TaskDraft.task_draft_id == "vdraft_001")
    )
    assert persisted is not None
    assert persisted.tenant_id == "tenant_a"
    assert persisted.shop_id == "shop_a1"


def test_v2_create_clarification_moves_task_to_needs_clarification(db_session) -> None:
    from app.models import V2TaskRun
    from app.services.v2_conversation import create_v2_clarification

    _seed_v2_task_run(db_session, task_run_id="vtask_clarify")

    clarification = create_v2_clarification(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        task_run_id="vtask_clarify",
        reason_code="missing_quantity",
        question_text="How many boxes should be stocked in?",
        requested_fields=["quantity"],
        draft_payload={"item_name": "Cola"},
    )

    task_run = db_session.get(V2TaskRun, "vtask_clarify")
    assert clarification.status == "pending"
    assert task_run is not None
    assert task_run.status == "needs_clarification"
    assert task_run.completed_at is None


def test_v2_create_confirmation_moves_task_to_awaiting_confirmation(db_session) -> None:
    from app.models import V2TaskRun
    from app.services.v2_conversation import create_v2_confirmation

    _seed_v2_task_run(db_session, task_run_id="vtask_confirm")

    confirmation = create_v2_confirmation(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        task_run_id="vtask_confirm",
        confirmation_type="inventory.stock_in",
        draft_payload={"item_name": "Cola", "quantity": 2, "unit": "box"},
    )

    task_run = db_session.get(V2TaskRun, "vtask_confirm")
    assert confirmation.status == "pending"
    assert task_run is not None
    assert task_run.status == "awaiting_confirmation"
    assert task_run.completed_at is None


def test_v2_list_confirmations_returns_current_context_pending_items(client, db_session) -> None:
    from app.services.v2_conversation import create_v2_confirmation

    token, context_token, task_run_id = _create_api_task_run(client, db_session)
    confirmation = create_v2_confirmation(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        task_run_id=task_run_id,
        confirmation_type="inventory.stock_in",
        draft_payload={"item_name": "Cola", "quantity": 2, "unit": "box"},
    )

    response = client.get(
        "/api/v2/confirmations?status=pending&limit=20",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["count"] == 1
    assert payload["confirmations"][0]["confirmation_id"] == confirmation.confirmation_id
    assert payload["confirmations"][0]["tenant_id"] == "tenant_a"
    assert payload["confirmations"][0]["shop_id"] == "shop_a1"


def test_v2_approve_confirmation_records_resolution_and_moves_task_to_executing(client, db_session) -> None:
    from app.models import V2TaskRun
    from app.services.v2_conversation import create_v2_confirmation

    token, context_token, task_run_id = _create_api_task_run(client, db_session)
    confirmation = create_v2_confirmation(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        task_run_id=task_run_id,
        confirmation_type="workflow.manual_review",
        draft_payload={"note": "Need manual follow-up"},
    )

    response = client.post(
        f"/api/v2/confirmations/{confirmation.confirmation_id}/approve",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={"resolution_payload": {"fields": {"note": "approved for next worker"}}},
    )

    db_session.expire_all()
    task_run = db_session.get(V2TaskRun, task_run_id)
    stream_events = _list_v2_stream_events(
        client,
        token=token,
        context_token=context_token,
        session_id=task_run.session_id if task_run is not None else "",
    )
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "approved"
    assert response.json()["data"]["approved_by_account_id"] == "acct_001"
    assert task_run is not None
    assert task_run.status == "executing"
    assert task_run.completed_at is None
    assert [event["event_type"] for event in stream_events] == [
        "message.created",
        "task.updated",
        "task.updated",
        "task.updated",
    ]
    assert [event["data"].get("status") for event in stream_events if event["event_type"] == "task.updated"] == [
        "captured",
        "awaiting_confirmation",
        "executing",
    ]


def test_v2_approve_confirmation_commits_inventory_and_appends_system_result_message(client, db_session) -> None:
    from app.models import V2InventoryItem, V2InventoryLedgerEvent, V2InventoryStockSnapshot, V2TaskRun
    from app.services.v2_conversation import create_v2_confirmation

    token, context_token, task_run_id = _create_api_task_run(client, db_session)
    confirmation = create_v2_confirmation(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        task_run_id=task_run_id,
        confirmation_type="inventory.stock_in",
        draft_payload={"item_name": "Cola", "quantity": 2, "unit": "box", "price": 18.5},
    )

    response = client.post(
        f"/api/v2/confirmations/{confirmation.confirmation_id}/approve",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={
            "resolution_payload": {
                "fields": {"item_name": "Cola", "quantity": 2, "unit": "box", "price": 18.5}
            }
        },
    )

    db_session.expire_all()
    task_run = db_session.get(V2TaskRun, task_run_id)
    items = db_session.query(V2InventoryItem).all()
    snapshots = db_session.query(V2InventoryStockSnapshot).all()
    events = db_session.query(V2InventoryLedgerEvent).all()

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "approved"
    assert task_run is not None
    assert task_run.status == "committed"
    assert task_run.completed_at is not None

    messages_response = client.get(
        f"/api/v2/sessions/{task_run.session_id}/messages",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
    )
    messages = messages_response.json()["data"]["messages"]

    assert len(items) == 1
    assert items[0].tenant_id == "tenant_a"
    assert snapshots[0].shop_id == "shop_a1"
    assert snapshots[0].current_quantity == 2
    assert events[0].shop_id == "shop_a1"
    assert events[0].quantity_after == 2
    assert messages_response.status_code == 200
    assert len(messages) == 2
    assert messages[-1]["actor_type"] == "system"
    assert messages[-1]["actor_id"] == "runtime_system"
    assert messages[-1]["message_kind"] == "system_result"
    assert messages[-1]["payload_json"]["task_run_id"] == task_run_id
    assert messages[-1]["payload_json"]["confirmation_id"] == confirmation.confirmation_id
    assert messages[-1]["payload_json"]["confirmation_type"] == "inventory.stock_in"
    assert messages[-1]["payload_json"]["task_run_status"] == "committed"
    assert "stock-in committed" in messages[-1]["payload_json"]["text"].lower()


def test_v2_approve_stock_in_confirmation_appends_audit_log_and_outbox_event(client, db_session) -> None:
    from sqlalchemy import select

    from app.models import V2AuditLog, V2OutboxEvent, V2TaskRun
    from app.services.v2_conversation import create_v2_confirmation

    token, context_token, task_run_id = _create_api_task_run(client, db_session)
    confirmation = create_v2_confirmation(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        task_run_id=task_run_id,
        confirmation_type="inventory.stock_in",
        draft_payload={"item_name": "Cola", "quantity": 2, "unit": "box", "price": 18.5},
    )

    response = client.post(
        f"/api/v2/confirmations/{confirmation.confirmation_id}/approve",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={
            "resolution_payload": {
                "fields": {"item_name": "Cola", "quantity": 2, "unit": "box", "price": 18.5}
            }
        },
    )

    db_session.expire_all()
    task_run = db_session.get(V2TaskRun, task_run_id)
    audit_log = db_session.scalar(
        select(V2AuditLog)
        .where(V2AuditLog.task_run_id == task_run_id)
        .order_by(V2AuditLog.created_at.desc(), V2AuditLog.audit_log_id.desc())
    )
    outbox_event = db_session.scalar(
        select(V2OutboxEvent)
        .where(
            V2OutboxEvent.aggregate_type == "task_run",
            V2OutboxEvent.aggregate_id == task_run_id,
        )
        .order_by(V2OutboxEvent.created_at.desc(), V2OutboxEvent.outbox_event_id.desc())
    )

    assert response.status_code == 200
    assert task_run is not None
    assert audit_log is not None
    assert audit_log.tenant_id == "tenant_a"
    assert audit_log.shop_id == "shop_a1"
    assert audit_log.session_id == task_run.session_id
    assert audit_log.task_run_id == task_run_id
    assert audit_log.action == "inventory.stock_in_committed"
    assert audit_log.actor_type == "account"
    assert audit_log.actor_id == "acct_001"
    assert audit_log.target_type == "inventory_item"
    assert audit_log.metadata_json["confirmation_id"] == confirmation.confirmation_id
    assert audit_log.metadata_json["event_type"] == "stock_in"
    assert outbox_event is not None
    assert outbox_event.tenant_id == "tenant_a"
    assert outbox_event.shop_id == "shop_a1"
    assert outbox_event.aggregate_type == "task_run"
    assert outbox_event.aggregate_id == task_run_id
    assert outbox_event.event_type == "inventory.stock_in.committed"
    assert outbox_event.status == "pending"
    assert outbox_event.attempt_count == 0
    assert outbox_event.payload_json["confirmation_id"] == confirmation.confirmation_id
    assert outbox_event.payload_json["task_run_id"] == task_run_id


def test_v2_approve_inventory_confirmation_enqueues_outbox_drain_after_commit(
    db_session, monkeypatch
) -> None:
    from sqlalchemy import select

    import app.services.v2_conversation as v2_conversation
    from app.db.session import get_session_factory
    from app.models import V2OutboxEvent, V2TaskRun
    from app.services.v2_conversation import approve_v2_confirmation, create_v2_confirmation

    task_run_id = "vtask_enqueue_after_commit"
    _seed_v2_task_run(db_session, task_run_id=task_run_id)
    confirmation = create_v2_confirmation(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        task_run_id=task_run_id,
        confirmation_type="inventory.stock_in",
        draft_payload={"item_name": "Cola", "quantity": 2, "unit": "box", "price": 18.5},
    )
    observed: dict[str, object | None] = {}

    def fake_enqueue_v2_outbox_drain(*, tenant_id: str, shop_id: str, **kwargs) -> bool:
        verification_session = get_session_factory()()
        try:
            verification_task_run = verification_session.get(V2TaskRun, task_run_id)
            verification_outbox = verification_session.scalar(
                select(V2OutboxEvent)
                .where(
                    V2OutboxEvent.aggregate_type == "task_run",
                    V2OutboxEvent.aggregate_id == task_run_id,
                )
                .order_by(V2OutboxEvent.created_at.desc(), V2OutboxEvent.outbox_event_id.desc())
            )
            observed["tenant_id"] = tenant_id
            observed["shop_id"] = shop_id
            observed["batch_limit"] = kwargs.get("batch_limit", 50)
            observed["max_batches"] = kwargs.get("max_batches", 10)
            observed["retry_after_seconds"] = kwargs.get("retry_after_seconds", 60)
            observed["task_status"] = verification_task_run.status if verification_task_run is not None else None
            observed["outbox_status"] = verification_outbox.status if verification_outbox is not None else None
        finally:
            verification_session.close()
        return True

    monkeypatch.setattr(v2_conversation, "enqueue_v2_outbox_drain", fake_enqueue_v2_outbox_drain)

    approved = approve_v2_confirmation(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        confirmation_id=confirmation.confirmation_id,
        resolution_payload={
            "fields": {"item_name": "Cola", "quantity": 2, "unit": "box", "price": 18.5}
        },
        approved_by_account_id="acct_001",
    )

    assert approved.status == "approved"
    assert observed == {
        "tenant_id": "tenant_a",
        "shop_id": "shop_a1",
        "batch_limit": 50,
        "max_batches": 10,
        "retry_after_seconds": 60,
        "task_status": "committed",
        "outbox_status": "pending",
    }


def test_v2_approve_manual_review_confirmation_does_not_enqueue_outbox_drain(
    db_session, monkeypatch
) -> None:
    import app.services.v2_conversation as v2_conversation
    from app.services.v2_conversation import approve_v2_confirmation, create_v2_confirmation

    task_run_id = "vtask_manual_review_no_enqueue"
    _seed_v2_task_run(db_session, task_run_id=task_run_id)
    confirmation = create_v2_confirmation(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        task_run_id=task_run_id,
        confirmation_type="workflow.manual_review",
        draft_payload={"note": "Need manual follow-up"},
    )
    calls: list[dict[str, object]] = []

    def fake_enqueue_v2_outbox_drain(**kwargs) -> bool:
        calls.append(kwargs)
        return True

    monkeypatch.setattr(v2_conversation, "enqueue_v2_outbox_drain", fake_enqueue_v2_outbox_drain)

    approved = approve_v2_confirmation(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        confirmation_id=confirmation.confirmation_id,
        resolution_payload={"fields": {"note": "approved for next worker"}},
        approved_by_account_id="acct_001",
    )

    assert approved.status == "approved"
    assert calls == []


def test_v2_approve_stock_out_confirmation_commits_inventory_and_appends_system_result_message(
    client, db_session
) -> None:
    from app.models import V2InventoryLedgerEvent, V2InventoryStockSnapshot, V2TaskRun
    from app.services.v2_conversation import create_v2_confirmation
    from app.services.v2_inventory import commit_v2_inventory_stock_in

    token, context_token, task_run_id = _create_api_task_run(client, db_session)
    seed_task_run_id = "vtask_seed_stock_out_confirm"
    _seed_v2_inventory_task_run_in_existing_context(db_session, task_run_id=seed_task_run_id)
    seeded = commit_v2_inventory_stock_in(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        task_run_id=seed_task_run_id,
        created_by_account_id="acct_001",
        payload={"item_name": "Cola", "quantity": 5, "unit": "box", "price": 18.5},
    )
    db_session.commit()

    confirmation = create_v2_confirmation(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        task_run_id=task_run_id,
        confirmation_type="inventory.stock_out",
        draft_payload={
            "inventory_item_id": seeded.item.inventory_item_id,
            "expected_quantity": 5,
            "stock_out_quantity": 2,
            "reason": "counter sale",
        },
    )

    response = client.post(
        f"/api/v2/confirmations/{confirmation.confirmation_id}/approve",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={
            "resolution_payload": {
                "fields": {
                    "inventory_item_id": seeded.item.inventory_item_id,
                    "expected_quantity": 5,
                    "stock_out_quantity": 2,
                    "reason": "counter sale",
                }
            }
        },
    )

    db_session.expire_all()
    task_run = db_session.get(V2TaskRun, task_run_id)
    snapshot = db_session.query(V2InventoryStockSnapshot).filter_by(
        inventory_item_id=seeded.item.inventory_item_id,
        shop_id="shop_a1",
    ).one()
    event = db_session.query(V2InventoryLedgerEvent).filter_by(
        inventory_item_id=seeded.item.inventory_item_id,
        event_type="stock_out",
    ).one()

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "approved"
    assert task_run is not None
    assert task_run.status == "committed"
    assert task_run.completed_at is not None

    messages_response = client.get(
        f"/api/v2/sessions/{task_run.session_id}/messages",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
    )
    messages = messages_response.json()["data"]["messages"]

    assert snapshot.current_quantity == Decimal("3")
    assert event.quantity_after == Decimal("3")
    assert event.reason == "counter sale"
    assert messages_response.status_code == 200
    assert len(messages) == 2
    assert messages[-1]["actor_type"] == "system"
    assert messages[-1]["actor_id"] == "runtime_system"
    assert messages[-1]["message_kind"] == "system_result"
    assert messages[-1]["payload_json"]["task_run_id"] == task_run_id
    assert messages[-1]["payload_json"]["confirmation_id"] == confirmation.confirmation_id
    assert messages[-1]["payload_json"]["confirmation_type"] == "inventory.stock_out"
    assert messages[-1]["payload_json"]["task_run_status"] == "committed"
    assert "stock-out committed" in messages[-1]["payload_json"]["text"].lower()


def test_v2_approve_stock_out_confirmation_appends_audit_log_and_outbox_event(client, db_session) -> None:
    from sqlalchemy import select

    from app.models import V2AuditLog, V2OutboxEvent, V2TaskRun
    from app.services.v2_conversation import create_v2_confirmation
    from app.services.v2_inventory import commit_v2_inventory_stock_in

    token, context_token, task_run_id = _create_api_task_run(client, db_session)
    seed_task_run_id = "vtask_seed_stock_out_audit_outbox"
    _seed_v2_inventory_task_run_in_existing_context(db_session, task_run_id=seed_task_run_id)
    seeded = commit_v2_inventory_stock_in(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        task_run_id=seed_task_run_id,
        created_by_account_id="acct_001",
        payload={"item_name": "Cola", "quantity": 5, "unit": "box", "price": 18.5},
    )
    db_session.commit()

    confirmation = create_v2_confirmation(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        task_run_id=task_run_id,
        confirmation_type="inventory.stock_out",
        draft_payload={
            "inventory_item_id": seeded.item.inventory_item_id,
            "expected_quantity": 5,
            "stock_out_quantity": 2,
            "reason": "counter sale",
        },
    )

    response = client.post(
        f"/api/v2/confirmations/{confirmation.confirmation_id}/approve",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={
            "resolution_payload": {
                "fields": {
                    "inventory_item_id": seeded.item.inventory_item_id,
                    "expected_quantity": 5,
                    "stock_out_quantity": 2,
                    "reason": "counter sale",
                }
            }
        },
    )

    db_session.expire_all()
    task_run = db_session.get(V2TaskRun, task_run_id)
    audit_log = db_session.scalar(
        select(V2AuditLog)
        .where(V2AuditLog.task_run_id == task_run_id)
        .order_by(V2AuditLog.created_at.desc(), V2AuditLog.audit_log_id.desc())
    )
    outbox_event = db_session.scalar(
        select(V2OutboxEvent)
        .where(
            V2OutboxEvent.aggregate_type == "task_run",
            V2OutboxEvent.aggregate_id == task_run_id,
        )
        .order_by(V2OutboxEvent.created_at.desc(), V2OutboxEvent.outbox_event_id.desc())
    )

    assert response.status_code == 200
    assert task_run is not None
    assert audit_log is not None
    assert audit_log.tenant_id == "tenant_a"
    assert audit_log.shop_id == "shop_a1"
    assert audit_log.session_id == task_run.session_id
    assert audit_log.task_run_id == task_run_id
    assert audit_log.action == "inventory.stock_out_committed"
    assert audit_log.actor_type == "account"
    assert audit_log.actor_id == "acct_001"
    assert audit_log.target_type == "inventory_item"
    assert audit_log.metadata_json["confirmation_id"] == confirmation.confirmation_id
    assert audit_log.metadata_json["event_type"] == "stock_out"
    assert outbox_event is not None
    assert outbox_event.tenant_id == "tenant_a"
    assert outbox_event.shop_id == "shop_a1"
    assert outbox_event.aggregate_type == "task_run"
    assert outbox_event.aggregate_id == task_run_id
    assert outbox_event.event_type == "inventory.stock_out.committed"
    assert outbox_event.status == "pending"
    assert outbox_event.attempt_count == 0
    assert outbox_event.payload_json["confirmation_id"] == confirmation.confirmation_id
    assert outbox_event.payload_json["task_run_id"] == task_run_id


def test_v2_approve_stock_out_confirmation_rejects_insufficient_stock_and_rolls_back(client, db_session) -> None:
    from app.models import V2Confirmation, V2InventoryStockSnapshot, V2TaskRun
    from app.services.v2_conversation import create_v2_confirmation
    from app.services.v2_inventory import commit_v2_inventory_stock_in

    token, context_token, task_run_id = _create_api_task_run(client, db_session)
    seed_task_run_id = "vtask_seed_stock_out_insufficient"
    _seed_v2_inventory_task_run_in_existing_context(db_session, task_run_id=seed_task_run_id)
    seeded = commit_v2_inventory_stock_in(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        task_run_id=seed_task_run_id,
        created_by_account_id="acct_001",
        payload={"item_name": "Cola", "quantity": 1, "unit": "box", "price": 18.5},
    )
    db_session.commit()

    confirmation = create_v2_confirmation(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        task_run_id=task_run_id,
        confirmation_type="inventory.stock_out",
        draft_payload={
            "inventory_item_id": seeded.item.inventory_item_id,
            "expected_quantity": 1,
            "stock_out_quantity": 2,
            "reason": "counter sale",
        },
    )

    response = client.post(
        f"/api/v2/confirmations/{confirmation.confirmation_id}/approve",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={
            "resolution_payload": {
                "fields": {
                    "inventory_item_id": seeded.item.inventory_item_id,
                    "expected_quantity": 1,
                    "stock_out_quantity": 2,
                    "reason": "counter sale",
                }
            }
        },
    )

    db_session.expire_all()
    persisted_confirmation = db_session.get(V2Confirmation, confirmation.confirmation_id)
    persisted_task_run = db_session.get(V2TaskRun, task_run_id)
    snapshot = db_session.query(V2InventoryStockSnapshot).filter_by(
        inventory_item_id=seeded.item.inventory_item_id,
        shop_id="shop_a1",
    ).one()

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert persisted_confirmation is not None
    assert persisted_confirmation.status == "pending"
    assert persisted_confirmation.approved_by_account_id is None
    assert persisted_task_run is not None
    assert persisted_task_run.status == "awaiting_confirmation"
    assert persisted_task_run.completed_at is None
    assert snapshot.current_quantity == Decimal("1")


def test_v2_approve_confirmation_rolls_back_when_inventory_commit_fails(db_session, monkeypatch) -> None:
    import pytest

    from app.models import V2Confirmation, V2TaskRun
    from app.services import v2_conversation as conversation_service
    from app.services.v2_conversation import approve_v2_confirmation, create_v2_confirmation

    _seed_v2_task_run(db_session, task_run_id="vtask_v2_approve_rollback")
    confirmation = create_v2_confirmation(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        task_run_id="vtask_v2_approve_rollback",
        confirmation_type="inventory.stock_in",
        draft_payload={"item_name": "Cola", "quantity": 2, "unit": "box", "price": 18.5},
    )

    def blow_up(*args, **kwargs):
        raise RuntimeError("inventory commit failed")

    monkeypatch.setattr(conversation_service, "commit_v2_inventory_stock_in", blow_up)

    with pytest.raises(RuntimeError, match="inventory commit failed"):
        approve_v2_confirmation(
            db_session,
            tenant_id="tenant_a",
            shop_id="shop_a1",
            confirmation_id=confirmation.confirmation_id,
            resolution_payload={
                "fields": {"item_name": "Cola", "quantity": 2, "unit": "box", "price": 18.5}
            },
            approved_by_account_id="acct_001",
        )

    db_session.expire_all()
    persisted_task_run = db_session.get(V2TaskRun, "vtask_v2_approve_rollback")
    persisted_confirmation = db_session.get(V2Confirmation, confirmation.confirmation_id)
    assert persisted_confirmation is not None
    assert persisted_confirmation.status == "pending"
    assert persisted_confirmation.approved_by_account_id is None
    assert persisted_task_run is not None
    assert persisted_task_run.status == "awaiting_confirmation"
    assert persisted_task_run.completed_at is None


def test_v2_reject_confirmation_marks_task_rejected_and_appends_system_result_message(
    client, db_session
) -> None:
    from app.models import V2TaskRun
    from app.services.v2_conversation import create_v2_confirmation

    token, context_token, task_run_id = _create_api_task_run(client, db_session)
    confirmation = create_v2_confirmation(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        task_run_id=task_run_id,
        confirmation_type="inventory.stock_in",
        draft_payload={"item_name": "Cola", "quantity": 2, "unit": "box"},
    )

    response = client.post(
        f"/api/v2/confirmations/{confirmation.confirmation_id}/reject",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
    )

    db_session.expire_all()
    task_run = db_session.get(V2TaskRun, task_run_id)
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "rejected"
    assert task_run is not None
    assert task_run.status == "rejected"
    assert task_run.completed_at is not None

    messages_response = client.get(
        f"/api/v2/sessions/{task_run.session_id}/messages",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
    )
    stream_events = _list_v2_stream_events(
        client,
        token=token,
        context_token=context_token,
        session_id=task_run.session_id,
    )
    messages = messages_response.json()["data"]["messages"]

    assert messages_response.status_code == 200
    assert len(messages) == 2
    assert messages[-1]["actor_type"] == "system"
    assert messages[-1]["actor_id"] == "runtime_system"
    assert messages[-1]["message_kind"] == "system_result"
    assert messages[-1]["payload_json"]["task_run_id"] == task_run_id
    assert messages[-1]["payload_json"]["confirmation_id"] == confirmation.confirmation_id
    assert messages[-1]["payload_json"]["confirmation_type"] == "inventory.stock_in"
    assert messages[-1]["payload_json"]["task_run_status"] == "rejected"
    assert "rejected" in messages[-1]["payload_json"]["text"].lower()
    assert [event["event_type"] for event in stream_events] == [
        "message.created",
        "task.updated",
        "task.updated",
        "message.created",
        "task.updated",
    ]
    assert stream_events[-2]["data"]["message_kind"] == "system_result"
    assert stream_events[-2]["data"]["actor_type"] == "system"
    assert stream_events[-1]["data"]["status"] == "rejected"


def test_v2_list_clarifications_returns_current_context_pending_items(client, db_session) -> None:
    from app.services.v2_conversation import create_v2_clarification

    token, context_token, task_run_id = _create_api_task_run(client, db_session)
    clarification = create_v2_clarification(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        task_run_id=task_run_id,
        reason_code="missing_quantity",
        question_text="How many boxes should be stocked in?",
        requested_fields=["quantity"],
        draft_payload={"item_name": "Cola"},
    )

    response = client.get(
        "/api/v2/clarifications?status=pending&limit=20",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["count"] == 1
    assert payload["clarifications"][0]["clarification_id"] == clarification.clarification_id
    assert payload["clarifications"][0]["status"] == "pending"


def test_v2_answer_clarification_records_answer_and_moves_task_to_drafted(client, db_session) -> None:
    from app.models import V2TaskRun
    from app.services.v2_conversation import create_v2_clarification

    token, context_token, task_run_id = _create_api_task_run(client, db_session)
    clarification = create_v2_clarification(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        task_run_id=task_run_id,
        reason_code="missing_quantity",
        question_text="How many boxes should be stocked in?",
        requested_fields=["quantity"],
        draft_payload={"item_name": "Cola"},
    )

    response = client.post(
        f"/api/v2/clarifications/{clarification.clarification_id}/answer",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={"answer_payload": {"quantity": 2, "unit": "box"}},
    )

    db_session.expire_all()
    task_run = db_session.get(V2TaskRun, task_run_id)
    stream_events = _list_v2_stream_events(
        client,
        token=token,
        context_token=context_token,
        session_id=task_run.session_id if task_run is not None else "",
    )
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "answered"
    assert response.json()["data"]["answered_by_account_id"] == "acct_001"
    assert response.json()["data"]["answer_payload"] == {"quantity": 2, "unit": "box"}
    assert task_run is not None
    assert task_run.status == "drafted"
    assert task_run.completed_at is None
    assert [event["event_type"] for event in stream_events] == [
        "message.created",
        "task.updated",
        "task.updated",
        "task.updated",
    ]
    assert [event["data"].get("status") for event in stream_events if event["event_type"] == "task.updated"] == [
        "captured",
        "needs_clarification",
        "drafted",
    ]


def test_v2_answer_clarification_materializes_task_draft(client, db_session) -> None:
    from app.services.v2_conversation import create_v2_clarification

    token, context_token, task_run_id = _create_api_task_run(client, db_session)
    clarification = create_v2_clarification(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        task_run_id=task_run_id,
        reason_code="missing_quantity",
        question_text="How many boxes should be stocked in?",
        requested_fields=["quantity"],
        draft_payload={"item_name": "Cola"},
    )
    answer_response = client.post(
        f"/api/v2/clarifications/{clarification.clarification_id}/answer",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={"answer_payload": {"quantity": 2, "unit": "box"}},
    )
    task_response = client.get(
        f"/api/v2/task-runs/{task_run_id}",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
    )

    assert answer_response.status_code == 200
    assert task_response.status_code == 200
    assert task_response.json()["data"]["draft_payload"] == {
        "item_name": "Cola",
        "quantity": 2,
        "unit": "box",
    }


def test_v2_answer_clarification_rejects_non_pending_record(db_session) -> None:
    import pytest

    from app.services.v2_conversation import (
        V2ConfirmationConflictError,
        answer_v2_clarification,
        create_v2_clarification,
    )

    _seed_v2_task_run(db_session, task_run_id="vtask_answer_once")
    clarification = create_v2_clarification(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        task_run_id="vtask_answer_once",
        reason_code="missing_quantity",
        question_text="How many boxes should be stocked in?",
        requested_fields=["quantity"],
        draft_payload={"item_name": "Cola"},
    )
    answer_v2_clarification(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        clarification_id=clarification.clarification_id,
        answer_payload={"quantity": 2},
        answered_by_account_id="acct_001",
    )

    with pytest.raises(V2ConfirmationConflictError):
        answer_v2_clarification(
            db_session,
            tenant_id="tenant_a",
            shop_id="shop_a1",
            clarification_id=clarification.clarification_id,
            answer_payload={"quantity": 3},
            answered_by_account_id="acct_001",
        )


def test_v2_request_confirmation_from_draft_creates_pending_confirmation(client, db_session) -> None:
    from app.services.v2_conversation import create_v2_clarification

    token, context_token, task_run_id = _create_api_task_run(client, db_session)
    clarification = create_v2_clarification(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        task_run_id=task_run_id,
        reason_code="missing_quantity",
        question_text="How many boxes should be stocked in?",
        requested_fields=["quantity"],
        draft_payload={"item_name": "Cola"},
    )
    answer_response = client.post(
        f"/api/v2/clarifications/{clarification.clarification_id}/answer",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={"answer_payload": {"quantity": 2, "unit": "box"}},
    )
    assert answer_response.status_code == 200

    response = client.post(
        f"/api/v2/task-runs/{task_run_id}/confirmations",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={"confirmation_type": "inventory.stock_in"},
    )
    task_response = client.get(
        f"/api/v2/task-runs/{task_run_id}",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
    )

    assert response.status_code == 201
    assert response.json()["data"]["status"] == "pending"
    assert response.json()["data"]["draft_payload"] == {
        "item_name": "Cola",
        "quantity": 2,
        "unit": "box",
    }
    assert task_response.json()["data"]["status"] == "awaiting_confirmation"


def test_v2_request_confirmation_from_draft_rejects_missing_draft(client, db_session) -> None:
    token, context_token, task_run_id = _create_api_task_run(client, db_session)

    response = client.post(
        f"/api/v2/task-runs/{task_run_id}/confirmations",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={"confirmation_type": "inventory.stock_in"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "draft_not_ready"


def test_v2_request_confirmation_from_generic_draft_specializes_task_and_draft_type(client, db_session) -> None:
    from app.models import V2TaskDraft
    from app.services.v2_conversation import create_v2_clarification

    token, context_token, task_run_id = _create_api_task_run(client, db_session)
    clarification = create_v2_clarification(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        task_run_id=task_run_id,
        reason_code="missing_quantity",
        question_text="How many boxes should be stocked in?",
        requested_fields=["quantity"],
        draft_payload={"item_name": "Cola"},
    )
    answer_response = client.post(
        f"/api/v2/clarifications/{clarification.clarification_id}/answer",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={"answer_payload": {"quantity": 2, "unit": "box"}},
    )
    confirmation_response = client.post(
        f"/api/v2/task-runs/{task_run_id}/confirmations",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={"confirmation_type": "inventory.stock_in"},
    )
    task_response = client.get(
        f"/api/v2/task-runs/{task_run_id}",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
    )

    db_session.expire_all()
    draft = db_session.query(V2TaskDraft).filter_by(task_run_id=task_run_id).one()

    assert answer_response.status_code == 200
    assert confirmation_response.status_code == 201
    assert task_response.json()["data"]["intent_type"] == "inventory.stock_in"
    assert draft.draft_type == "inventory.stock_in"


def test_v2_create_typed_task_draft_materializes_draft_and_marks_task_drafted(client, db_session) -> None:
    token, context_token, task_run_id = _create_api_task_run(
        client,
        db_session,
        intent_type="inventory.stock_in",
    )

    response = client.post(
        f"/api/v2/task-runs/{task_run_id}/draft",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={
            "draft_type": "inventory.stock_in",
            "draft_payload": {"item_name": "Cola", "quantity": 2, "unit": "box", "price": 18.5},
        },
    )
    confirm_response = client.post(
        f"/api/v2/task-runs/{task_run_id}/confirmations",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={"confirmation_type": "inventory.stock_in"},
    )
    task_response = client.get(
        f"/api/v2/task-runs/{task_run_id}",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
    )
    stream_events = _list_v2_stream_events(
        client,
        token=token,
        context_token=context_token,
        session_id=task_response.json()["data"]["session_id"],
    )

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "drafted"
    assert response.json()["data"]["intent_type"] == "inventory.stock_in"
    assert response.json()["data"]["draft_payload"] == {
        "item_name": "Cola",
        "quantity": 2,
        "unit": "box",
        "price": 18.5,
    }
    assert confirm_response.status_code == 201
    assert confirm_response.json()["data"]["draft_payload"] == response.json()["data"]["draft_payload"]
    assert task_response.status_code == 200
    assert task_response.json()["data"]["status"] == "awaiting_confirmation"
    assert [event["event_type"] for event in stream_events] == [
        "message.created",
        "task.updated",
        "task.updated",
        "task.updated",
    ]
    assert [event["data"].get("status") for event in stream_events if event["event_type"] == "task.updated"] == [
        "captured",
        "drafted",
        "awaiting_confirmation",
    ]


def test_v2_create_typed_task_draft_rejects_type_mismatch(client, db_session) -> None:
    token, context_token = _create_api_identity_context(client, db_session)
    task_run_id = "vtask_typed_draft_mismatch"
    _seed_v2_inventory_task_run_in_existing_context(
        db_session,
        task_run_id=task_run_id,
        intent_type="inventory.stock_out",
    )

    response = client.post(
        f"/api/v2/task-runs/{task_run_id}/draft",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={
            "draft_type": "inventory.stock_in",
            "draft_payload": {"item_name": "Cola", "quantity": 2, "unit": "box", "price": 18.5},
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "draft_type_mismatch"


def test_v2_create_typed_task_draft_rejects_non_draftable_task_status(client, db_session) -> None:
    from app.services.v2_conversation import create_v2_confirmation

    token, context_token = _create_api_identity_context(client, db_session)
    task_run_id = "vtask_typed_draft_not_draftable"
    _seed_v2_inventory_task_run_in_existing_context(
        db_session,
        task_run_id=task_run_id,
        intent_type="inventory.stock_in",
    )
    create_v2_confirmation(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        task_run_id=task_run_id,
        confirmation_type="inventory.stock_in",
        draft_payload={"item_name": "Cola", "quantity": 2, "unit": "box", "price": 18.5},
    )

    response = client.post(
        f"/api/v2/task-runs/{task_run_id}/draft",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={
            "draft_type": "inventory.stock_in",
            "draft_payload": {"item_name": "Cola", "quantity": 3, "unit": "box", "price": 18.5},
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "task_run_not_draftable"


def test_v2_create_typed_task_draft_specializes_generic_task_intent(client, db_session) -> None:
    token, context_token, task_run_id = _create_api_task_run(client, db_session)

    response = client.post(
        f"/api/v2/task-runs/{task_run_id}/draft",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={
            "draft_type": "inventory.stock_in",
            "draft_payload": {"item_name": "Cola", "quantity": 2, "unit": "box", "price": 18.5},
        },
    )
    confirm_response = client.post(
        f"/api/v2/task-runs/{task_run_id}/confirmations",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={"confirmation_type": "inventory.stock_in"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["intent_type"] == "inventory.stock_in"
    assert response.json()["data"]["status"] == "drafted"
    assert confirm_response.status_code == 201


def test_v2_create_stock_in_task_draft_rejects_invalid_payload(client, db_session) -> None:
    token, context_token, task_run_id = _create_api_task_run(
        client,
        db_session,
        intent_type="inventory.stock_in",
    )

    response = client.post(
        f"/api/v2/task-runs/{task_run_id}/draft",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={
            "draft_type": "inventory.stock_in",
            "draft_payload": {"item_name": "Cola", "quantity": 2, "price": 18.5},
        },
    )
    task_response = client.get(
        f"/api/v2/task-runs/{task_run_id}",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert task_response.status_code == 200
    assert task_response.json()["data"]["status"] == "captured"
    assert task_response.json()["data"]["draft_payload"] is None


def test_v2_create_stock_out_task_draft_rejects_invalid_payload(client, db_session) -> None:
    token, context_token = _create_api_identity_context(client, db_session)
    task_run_id = "vtask_stock_out_invalid_draft"
    _seed_v2_inventory_task_run_in_existing_context(
        db_session,
        task_run_id=task_run_id,
        intent_type="inventory.stock_out",
    )

    response = client.post(
        f"/api/v2/task-runs/{task_run_id}/draft",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={
            "draft_type": "inventory.stock_out",
            "draft_payload": {
                "inventory_item_id": "vitem_seed",
                "expected_quantity": 5,
                "stock_out_quantity": 0,
                "reason": "counter sale",
            },
        },
    )
    task_response = client.get(
        f"/api/v2/task-runs/{task_run_id}",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert task_response.status_code == 200
    assert task_response.json()["data"]["status"] == "captured"
    assert task_response.json()["data"]["draft_payload"] is None


def test_v2_request_stock_out_confirmation_from_draft_creates_pending_confirmation(client, db_session) -> None:
    from app.services.v2_conversation import create_v2_clarification

    token, context_token = _create_api_identity_context(client, db_session)
    task_run_id = "vtask_stock_out_draft_confirm"
    _seed_v2_inventory_task_run_in_existing_context(
        db_session,
        task_run_id=task_run_id,
        intent_type="inventory.stock_out",
    )
    clarification = create_v2_clarification(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        task_run_id=task_run_id,
        reason_code="missing_stock_out_quantity",
        question_text="How many boxes should be stocked out?",
        requested_fields=["stock_out_quantity", "reason"],
        draft_payload={"inventory_item_id": "vitem_seed", "expected_quantity": 5},
    )

    answer_response = client.post(
        f"/api/v2/clarifications/{clarification.clarification_id}/answer",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={"answer_payload": {"stock_out_quantity": 2, "reason": "counter sale"}},
    )
    response = client.post(
        f"/api/v2/task-runs/{task_run_id}/confirmations",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={"confirmation_type": "inventory.stock_out"},
    )

    assert answer_response.status_code == 200
    assert response.status_code == 201
    assert response.json()["data"]["confirmation_type"] == "inventory.stock_out"
    assert response.json()["data"]["draft_payload"] == {
        "inventory_item_id": "vitem_seed",
        "expected_quantity": 5,
        "stock_out_quantity": 2,
        "reason": "counter sale",
    }


def test_v2_request_confirmation_from_draft_rejects_type_mismatch(client, db_session) -> None:
    from app.services.v2_conversation import create_v2_clarification

    token, context_token = _create_api_identity_context(client, db_session)
    task_run_id = "vtask_stock_out_type_mismatch"
    _seed_v2_inventory_task_run_in_existing_context(
        db_session,
        task_run_id=task_run_id,
        intent_type="inventory.stock_out",
    )
    clarification = create_v2_clarification(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        task_run_id=task_run_id,
        reason_code="missing_stock_out_quantity",
        question_text="How many boxes should be stocked out?",
        requested_fields=["stock_out_quantity", "reason"],
        draft_payload={"inventory_item_id": "vitem_seed", "expected_quantity": 5},
    )

    answer_response = client.post(
        f"/api/v2/clarifications/{clarification.clarification_id}/answer",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={"answer_payload": {"stock_out_quantity": 2, "reason": "counter sale"}},
    )
    response = client.post(
        f"/api/v2/task-runs/{task_run_id}/confirmations",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={"confirmation_type": "inventory.stock_in"},
    )

    assert answer_response.status_code == 200
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "confirmation_type_mismatch"
