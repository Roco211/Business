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


def _seed_v2_login_and_context(client, db_session) -> tuple[str, str]:
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


def test_v2_session_stream_api_replays_message_and_task_events(client, db_session) -> None:
    token, context_token = _seed_v2_login_and_context(client, db_session)
    session_response = client.post(
        "/api/v2/sessions",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={"session_type": "workgroup", "title": "Stream test"},
    )
    session_id = session_response.json()["data"]["session_id"]

    message_response = client.post(
        f"/api/v2/sessions/{session_id}/messages",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={
            "message_kind": "text",
            "payload_json": {"text": "restock cola"},
            "client_request_id": "v2_stream_001",
        },
    )

    unauthorized = client.get(f"/api/v2/sessions/{session_id}/stream-events?after_seq=0")
    response = client.get(
        f"/api/v2/sessions/{session_id}/stream-events?after_seq=0",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
    )

    assert message_response.status_code == 201
    assert unauthorized.status_code == 401
    assert response.status_code == 200
    assert response.json()["data"]["session_id"] == session_id
    assert response.json()["data"]["count"] == 2
    assert response.json()["data"]["last_event_seq"] == 2
    assert [event["event_type"] for event in response.json()["data"]["events"]] == [
        "message.created",
        "task.updated",
    ]


def test_v2_session_stream_api_respects_after_seq_limit_and_session_scope(client, db_session) -> None:
    token, context_token = _seed_v2_login_and_context(client, db_session)
    session_response = client.post(
        "/api/v2/sessions",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={"session_type": "workgroup", "title": "Scoped stream"},
    )
    session_id = session_response.json()["data"]["session_id"]

    client.post(
        f"/api/v2/sessions/{session_id}/messages",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={
            "message_kind": "text",
            "payload_json": {"text": "one"},
            "client_request_id": "v2_stream_limit_1",
        },
    )
    client.post(
        f"/api/v2/sessions/{session_id}/messages",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={
            "message_kind": "text",
            "payload_json": {"text": "two"},
            "client_request_id": "v2_stream_limit_2",
        },
    )

    replay_response = client.get(
        f"/api/v2/sessions/{session_id}/stream-events?after_seq=2&limit=2",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
    )
    missing_response = client.get(
        "/api/v2/sessions/vsess_missing/stream-events?after_seq=0",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
    )

    assert replay_response.status_code == 200
    assert replay_response.json()["data"]["count"] == 2
    assert [event["seq"] for event in replay_response.json()["data"]["events"]] == [3, 4]
    assert missing_response.status_code == 404
    assert missing_response.json()["error"]["code"] == "session_not_found"
