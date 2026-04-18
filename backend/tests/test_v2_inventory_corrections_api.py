from datetime import UTC, datetime
from decimal import Decimal


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


def _seed_v2_shop(
    db_session,
    *,
    shop_id: str,
    code: str,
    name: str,
) -> None:
    from app.models import V2Shop

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
            title="Inventory Corrections API",
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
            payload_json={"text": "inventory change"},
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
) -> str:
    from app.services.v2_inventory import commit_v2_inventory_stock_in

    _seed_v2_task_run_for_inventory(
        db_session,
        task_run_id=task_run_id,
        tenant_id=tenant_id,
        shop_id=shop_id,
    )
    db_session.flush()
    result = commit_v2_inventory_stock_in(
        db_session,
        tenant_id=tenant_id,
        shop_id=shop_id,
        task_run_id=task_run_id,
        created_by_account_id="acct_001",
        payload=payload,
    )
    db_session.commit()
    return result.item.inventory_item_id


def test_v2_submit_inventory_correction_updates_snapshot_and_returns_event_id(client, db_session) -> None:
    from app.models import V2InventoryLedgerEvent, V2InventoryStockSnapshot

    token, context_token = _seed_v2_inventory_api_context(client, db_session)
    inventory_item_id = _commit_inventory_stock_in(
        db_session,
        task_run_id="vtask_correction_seed",
        tenant_id="tenant_a",
        shop_id="shop_a1",
        payload={"item_name": "Cola", "quantity": 2, "unit": "box", "price": 18.5},
    )

    response = client.post(
        "/api/v2/inventory/corrections",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={
            "inventory_item_id": inventory_item_id,
            "expected_quantity": 2,
            "corrected_quantity": 6,
            "reason": "physical recount",
        },
    )

    db_session.expire_all()
    snapshot = db_session.query(V2InventoryStockSnapshot).filter_by(
        inventory_item_id=inventory_item_id,
        shop_id="shop_a1",
    ).one()
    event = db_session.query(V2InventoryLedgerEvent).filter_by(
        inventory_item_id=inventory_item_id,
        event_type="correction",
    ).one()

    assert response.status_code == 200
    assert response.json()["data"]["inventory_item_id"] == inventory_item_id
    assert response.json()["data"]["new_quantity"] == "6"
    assert response.json()["data"]["correction_event_id"].startswith("vevent_")
    assert snapshot.current_quantity == Decimal("6")
    assert event.quantity_after == Decimal("6")
    assert event.reason == "physical recount"


def test_v2_submit_inventory_correction_rejects_stale_expected_quantity(client, db_session) -> None:
    token, context_token = _seed_v2_inventory_api_context(client, db_session)
    inventory_item_id = _commit_inventory_stock_in(
        db_session,
        task_run_id="vtask_correction_stale",
        tenant_id="tenant_a",
        shop_id="shop_a1",
        payload={"item_name": "Cola", "quantity": 2, "unit": "box", "price": 18.5},
    )

    response = client.post(
        "/api/v2/inventory/corrections",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={
            "inventory_item_id": inventory_item_id,
            "expected_quantity": 1,
            "corrected_quantity": 6,
            "reason": "physical recount",
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "inventory_conflict"


def test_v2_submit_inventory_correction_rejects_negative_quantity(client, db_session) -> None:
    token, context_token = _seed_v2_inventory_api_context(client, db_session)
    inventory_item_id = _commit_inventory_stock_in(
        db_session,
        task_run_id="vtask_correction_negative",
        tenant_id="tenant_a",
        shop_id="shop_a1",
        payload={"item_name": "Cola", "quantity": 2, "unit": "box", "price": 18.5},
    )

    response = client.post(
        "/api/v2/inventory/corrections",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={
            "inventory_item_id": inventory_item_id,
            "expected_quantity": 2,
            "corrected_quantity": -1,
            "reason": "physical recount",
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_v2_submit_inventory_correction_rejects_item_outside_current_shop(client, db_session) -> None:
    token, context_token = _seed_v2_inventory_api_context(client, db_session)
    _seed_v2_shop(db_session, shop_id="shop_a2", code="a-2", name="Shop A2")
    inventory_item_id = _commit_inventory_stock_in(
        db_session,
        task_run_id="vtask_correction_other_shop",
        tenant_id="tenant_a",
        shop_id="shop_a2",
        payload={"item_name": "Grape", "quantity": 4, "unit": "box", "price": 15},
    )

    response = client.post(
        "/api/v2/inventory/corrections",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={
            "inventory_item_id": inventory_item_id,
            "expected_quantity": 4,
            "corrected_quantity": 6,
            "reason": "physical recount",
        },
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "inventory_item_not_found"
