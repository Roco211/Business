from datetime import UTC, datetime


def _utc_now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _seed_v2_identity_for_runtime(db_session) -> None:
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
            name="A 商家",
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
            name="A 一号店",
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


def seed_v2_login_and_context(client, db_session) -> tuple[str, str]:
    _seed_v2_identity_for_runtime(db_session)
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


def test_v2_runtime_schema_persists_tenant_and_shop_boundaries(db_session) -> None:
    from sqlalchemy import select

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
            name="A 商家",
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
            name="A 一号店",
            locale="zh-CN",
            timezone="Asia/Shanghai",
            status="active",
            created_at=now,
            updated_at=now,
        )
    )

    session = V2ConversationSession(
        session_id="vsess_001",
        tenant_id="tenant_a",
        shop_id="shop_a1",
        session_type="workgroup",
        title="A 一号店工作群",
        status="active",
        initiated_by_account_id="acct_001",
        created_at=now,
        updated_at=now,
    )
    message = V2Message(
        message_id="vmsg_001",
        tenant_id="tenant_a",
        shop_id="shop_a1",
        session_id="vsess_001",
        actor_type="account",
        actor_id="acct_001",
        message_kind="text",
        payload_json={"text": "今天到货两箱可乐"},
        client_request_id="req_001",
        created_at=now,
    )
    task_run = V2TaskRun(
        task_run_id="vtask_001",
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
    db_session.add_all([session, message, task_run])
    db_session.commit()

    persisted_task_run = db_session.scalar(
        select(V2TaskRun).where(V2TaskRun.task_run_id == "vtask_001")
    )

    assert persisted_task_run is not None
    assert persisted_task_run.tenant_id == "tenant_a"
    assert persisted_task_run.shop_id == "shop_a1"


def test_v2_create_session_uses_execution_context_boundaries(client, db_session) -> None:
    token, context_token = seed_v2_login_and_context(client, db_session)

    response = client.post(
        "/api/v2/sessions",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Context-Token": context_token,
        },
        json={
            "session_type": "workgroup",
            "title": "A 一号店工作群",
        },
    )

    assert response.status_code == 201
    payload = response.json()["data"]
    assert payload["tenant_id"] == "tenant_a"
    assert payload["shop_id"] == "shop_a1"
    assert payload["session_type"] == "workgroup"


def test_v2_list_sessions_only_returns_current_context_scope(client, db_session) -> None:
    token, context_token = seed_v2_login_and_context(client, db_session)

    first = client.post(
        "/api/v2/sessions",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={"session_type": "workgroup", "title": "会话一"},
    )
    second = client.post(
        "/api/v2/sessions",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={"session_type": "receipt", "title": "会话二"},
    )
    response = client.get(
        "/api/v2/sessions",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert response.status_code == 200
    assert [item["title"] for item in response.json()["data"]["sessions"]] == ["会话二", "会话一"]


def test_v2_post_message_creates_message_and_captured_task_run(client, db_session) -> None:
    token, context_token = seed_v2_login_and_context(client, db_session)
    session_response = client.post(
        "/api/v2/sessions",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={"session_type": "workgroup", "title": "工作群"},
    )
    session_id = session_response.json()["data"]["session_id"]

    response = client.post(
        f"/api/v2/sessions/{session_id}/messages",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={
            "message_kind": "text",
            "payload_json": {"text": "今天到货两箱可乐"},
            "client_request_id": "v2_msg_001",
        },
    )

    assert response.status_code == 201
    payload = response.json()["data"]
    assert payload["message_id"].startswith("vmsg_")
    assert payload["task_run_id"].startswith("vtask_")
    assert payload["intent_type"] == "conversation.capture"
    assert payload["status"] == "captured"


def test_v2_post_message_accepts_explicit_inventory_intent(client, db_session) -> None:
    token, context_token = seed_v2_login_and_context(client, db_session)
    session_response = client.post(
        "/api/v2/sessions",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={"session_type": "workgroup", "title": "工作群"},
    )
    session_id = session_response.json()["data"]["session_id"]

    response = client.post(
        f"/api/v2/sessions/{session_id}/messages",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={
            "message_kind": "text",
            "payload_json": {"text": "sell two cola"},
            "client_request_id": "v2_msg_stock_out_intent",
            "intent_type": "inventory.stock_out",
        },
    )
    task_run_id = response.json()["data"]["task_run_id"]

    task_response = client.get(
        f"/api/v2/task-runs/{task_run_id}",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
    )

    assert response.status_code == 201
    assert response.json()["data"]["intent_type"] == "inventory.stock_out"
    assert task_response.status_code == 200
    assert task_response.json()["data"]["intent_type"] == "inventory.stock_out"


def test_v2_post_receipt_message_defaults_to_receipt_extraction_intent(client, db_session) -> None:
    token, context_token = seed_v2_login_and_context(client, db_session)
    session_response = client.post(
        "/api/v2/sessions",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={"session_type": "receipt", "title": "票据会话"},
    )
    session_id = session_response.json()["data"]["session_id"]

    response = client.post(
        f"/api/v2/sessions/{session_id}/messages",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={
            "message_kind": "receipt-image",
            "payload_json": {"text": "extract receipt"},
            "client_request_id": "v2_msg_receipt_intent",
        },
    )
    task_run_id = response.json()["data"]["task_run_id"]

    task_response = client.get(
        f"/api/v2/task-runs/{task_run_id}",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
    )

    assert response.status_code == 201
    assert response.json()["data"]["intent_type"] == "document.receipt.extract"
    assert task_response.status_code == 200
    assert task_response.json()["data"]["intent_type"] == "document.receipt.extract"


def test_v2_post_message_rejects_unknown_intent_type(client, db_session) -> None:
    token, context_token = seed_v2_login_and_context(client, db_session)
    session_response = client.post(
        "/api/v2/sessions",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={"session_type": "workgroup", "title": "工作群"},
    )
    session_id = session_response.json()["data"]["session_id"]

    response = client.post(
        f"/api/v2/sessions/{session_id}/messages",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={
            "message_kind": "text",
            "payload_json": {"text": "do something"},
            "client_request_id": "v2_msg_unknown_intent",
            "intent_type": "inventory.delete_all",
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_v2_list_messages_returns_session_scoped_history(client, db_session) -> None:
    token, context_token = seed_v2_login_and_context(client, db_session)
    session_response = client.post(
        "/api/v2/sessions",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={"session_type": "workgroup", "title": "工作群"},
    )
    session_id = session_response.json()["data"]["session_id"]
    client.post(
        f"/api/v2/sessions/{session_id}/messages",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={"message_kind": "text", "payload_json": {"text": "one"}, "client_request_id": "v2_msg_hist_1"},
    )
    client.post(
        f"/api/v2/sessions/{session_id}/messages",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={"message_kind": "text", "payload_json": {"text": "two"}, "client_request_id": "v2_msg_hist_2"},
    )

    response = client.get(
        f"/api/v2/sessions/{session_id}/messages",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
    )

    assert response.status_code == 200
    assert [item["payload_json"]["text"] for item in response.json()["data"]["messages"]] == ["one", "two"]


def test_v2_get_task_run_returns_runtime_state_shape(client, db_session) -> None:
    token, context_token = seed_v2_login_and_context(client, db_session)
    session_response = client.post(
        "/api/v2/sessions",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={"session_type": "workgroup", "title": "工作群"},
    )
    session_id = session_response.json()["data"]["session_id"]
    message_response = client.post(
        f"/api/v2/sessions/{session_id}/messages",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={"message_kind": "text", "payload_json": {"text": "task"}, "client_request_id": "v2_task_query_1"},
    )
    task_run_id = message_response.json()["data"]["task_run_id"]

    response = client.get(
        f"/api/v2/task-runs/{task_run_id}",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["task_run_id"] == task_run_id
    assert payload["status"] == "captured"
    assert payload["intent_type"] == "conversation.capture"
    assert payload["tenant_id"] == "tenant_a"
    assert payload["shop_id"] == "shop_a1"
