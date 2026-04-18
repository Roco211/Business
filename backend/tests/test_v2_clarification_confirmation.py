from datetime import UTC, datetime


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


def _create_api_task_run(client, db_session) -> tuple[str, str, str]:
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
    context_token = context_response.json()["data"]["context_token"]

    session_response = client.post(
        "/api/v2/sessions",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={"session_type": "workgroup", "title": "Workgroup"},
    )
    assert session_response.status_code == 201
    session_id = session_response.json()["data"]["session_id"]

    message_response = client.post(
        f"/api/v2/sessions/{session_id}/messages",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={
            "message_kind": "text",
            "payload_json": {"text": "restock cola"},
            "client_request_id": "confirm_api_msg",
        },
    )
    assert message_response.status_code == 201
    task_run_id = message_response.json()["data"]["task_run_id"]
    return token, context_token, task_run_id


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
        confirmation_type="inventory.stock_in",
        draft_payload={"item_name": "Cola", "quantity": 2, "unit": "box"},
    )

    response = client.post(
        f"/api/v2/confirmations/{confirmation.confirmation_id}/approve",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={"resolution_payload": {"fields": {"item_name": "Cola", "quantity": 2, "unit": "box"}}},
    )

    db_session.expire_all()
    task_run = db_session.get(V2TaskRun, task_run_id)
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "approved"
    assert response.json()["data"]["approved_by_account_id"] == "acct_001"
    assert task_run is not None
    assert task_run.status == "executing"
    assert task_run.completed_at is None


def test_v2_reject_confirmation_marks_task_rejected(client, db_session) -> None:
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
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "answered"
    assert response.json()["data"]["answered_by_account_id"] == "acct_001"
    assert response.json()["data"]["answer_payload"] == {"quantity": 2, "unit": "box"}
    assert task_run is not None
    assert task_run.status == "drafted"
    assert task_run.completed_at is None


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
