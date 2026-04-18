from datetime import UTC, datetime


def _utc_now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _seed_v2_inventory_api_identity(db_session) -> None:
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


def _seed_v2_inventory_api_context(client, db_session) -> tuple[str, str]:
    _seed_v2_inventory_api_identity(db_session)
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


def _seed_v2_inventory_shop_and_access(
    db_session,
    *,
    shop_id: str,
    code: str,
    name: str,
) -> None:
    from app.models import V2Shop, V2ShopAccess

    now = _utc_now_naive()
    db_session.add(
        V2Shop(
            shop_id=shop_id,
            tenant_id="tenant_a",
            code=code,
            name=name,
            locale="zh-CN",
            timezone="Asia/Shanghai",
            status="active",
            created_at=now,
            updated_at=now,
        )
    )
    db_session.add(
        V2ShopAccess(
            shop_access_id=f"access_{shop_id}",
            tenant_id="tenant_a",
            shop_id=shop_id,
            membership_id="mship_tenant_a",
            access_level="write",
            status="active",
            created_at=now,
        )
    )
    db_session.commit()


def _seed_v2_task_run_for_inventory(
    db_session,
    *,
    task_run_id: str,
    tenant_id: str,
    shop_id: str,
) -> None:
    from app.models import V2ConversationSession, V2Message, V2TaskRun

    now = _utc_now_naive()
    session_id = f"vsess_{task_run_id}"[:40]
    message_id = f"vmsg_{task_run_id}"[:40]
    db_session.add(
        V2ConversationSession(
            session_id=session_id,
            tenant_id=tenant_id,
            shop_id=shop_id,
            session_type="workgroup",
            title="Inventory Read API",
            status="active",
            initiated_by_account_id="acct_001",
            created_at=now,
            updated_at=now,
        )
    )
    db_session.add(
        V2Message(
            message_id=message_id,
            tenant_id=tenant_id,
            shop_id=shop_id,
            session_id=session_id,
            actor_type="account",
            actor_id="acct_001",
            message_kind="text",
            payload_json={"text": "restock"},
            client_request_id=f"req_{task_run_id}"[:64],
            created_at=now,
        )
    )
    db_session.add(
        V2TaskRun(
            task_run_id=task_run_id,
            tenant_id=tenant_id,
            shop_id=shop_id,
            session_id=session_id,
            source_message_id=message_id,
            intent_type="inventory.stock_in",
            status="executing",
            risk_level="medium",
            trace_id=f"trace_{task_run_id}"[:64],
            result_summary=None,
            error_code=None,
            created_at=now,
            updated_at=now,
            completed_at=None,
        )
    )


def _commit_inventory_stock_in(
    db_session,
    *,
    task_run_id: str,
    tenant_id: str,
    shop_id: str,
    payload: dict[str, object],
) -> None:
    from app.services.v2_inventory import commit_v2_inventory_stock_in

    _seed_v2_task_run_for_inventory(
        db_session,
        task_run_id=task_run_id,
        tenant_id=tenant_id,
        shop_id=shop_id,
    )
    db_session.flush()
    commit_v2_inventory_stock_in(
        db_session,
        tenant_id=tenant_id,
        shop_id=shop_id,
        task_run_id=task_run_id,
        created_by_account_id="acct_001",
        payload=payload,
    )
    db_session.commit()


def test_v2_list_inventory_items_returns_tenant_scoped_items(client, db_session) -> None:
    token, context_token = _seed_v2_inventory_api_context(client, db_session)
    _commit_inventory_stock_in(
        db_session,
        task_run_id="vtask_items_1",
        tenant_id="tenant_a",
        shop_id="shop_a1",
        payload={"item_name": "Cola", "quantity": 2, "unit": "box", "price": 18.5},
    )
    _commit_inventory_stock_in(
        db_session,
        task_run_id="vtask_items_2",
        tenant_id="tenant_a",
        shop_id="shop_a1",
        payload={"item_name": "Orange", "quantity": 1, "unit": "box", "price": 12},
    )

    response = client.get(
        "/api/v2/inventory/items?limit=20",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["count"] == 2
    assert [item["name"] for item in payload["items"]] == ["Orange", "Cola"]


def test_v2_list_inventory_stock_returns_current_shop_snapshots(client, db_session) -> None:
    token, context_token = _seed_v2_inventory_api_context(client, db_session)
    _seed_v2_inventory_shop_and_access(
        db_session,
        shop_id="shop_a2",
        code="a-2",
        name="Shop A2",
    )
    _commit_inventory_stock_in(
        db_session,
        task_run_id="vtask_stock_a1",
        tenant_id="tenant_a",
        shop_id="shop_a1",
        payload={"item_name": "Cola", "quantity": 2, "unit": "box", "price": 18.5},
    )
    _commit_inventory_stock_in(
        db_session,
        task_run_id="vtask_stock_a2",
        tenant_id="tenant_a",
        shop_id="shop_a2",
        payload={"item_name": "Cola", "quantity": 5, "unit": "box", "price": 19},
    )

    response = client.get(
        "/api/v2/inventory/stock?limit=20",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["count"] == 1
    assert payload["items"][0]["shop_id"] == "shop_a1"
    assert payload["items"][0]["item_name"] == "Cola"


def test_v2_list_inventory_events_returns_current_shop_events_newest_first(client, db_session) -> None:
    token, context_token = _seed_v2_inventory_api_context(client, db_session)
    _commit_inventory_stock_in(
        db_session,
        task_run_id="vtask_events_1",
        tenant_id="tenant_a",
        shop_id="shop_a1",
        payload={"item_name": "Cola", "quantity": 2, "unit": "box", "price": 18.5},
    )
    _commit_inventory_stock_in(
        db_session,
        task_run_id="vtask_events_2",
        tenant_id="tenant_a",
        shop_id="shop_a1",
        payload={"item_name": "Orange", "quantity": 1, "unit": "box", "price": 12},
    )

    response = client.get(
        "/api/v2/inventory/events?limit=20",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["count"] == 2
    assert [item["item_name"] for item in payload["events"]] == ["Orange", "Cola"]
