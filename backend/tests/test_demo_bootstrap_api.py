from datetime import datetime, timezone
UTC = timezone.utc
from decimal import Decimal

from app.db.session import get_session_factory
from app.models import OwnerAccount, Shop, ShopMembership
from app.services.auth_sessions import issue_auth_session
from conftest import auth_headers, login_and_get_token

DEFAULT_SESSION_ID = "sess_default"


def _auth_headers(client, monkeypatch=None) -> dict[str, str]:
    return auth_headers(login_and_get_token(client, monkeypatch))


def _post_demo_bootstrap(client) -> dict[str, object]:
    response = client.post("/api/v1/system/demo/bootstrap", headers=_auth_headers(client))
    assert response.status_code == 200
    return response.json()["data"]


def test_demo_bootstrap_endpoint_requires_owner_auth(client) -> None:
    response = client.post("/api/v1/system/demo/bootstrap")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_demo_bootstrap_endpoint_returns_stable_summary_and_seeded_state(client) -> None:
    summary = _post_demo_bootstrap(client)
    messages_response = client.get(f"/api/v1/sessions/{DEFAULT_SESSION_ID}/messages", headers=_auth_headers(client))
    dashboard_response = client.get("/api/v1/dashboard/summary", headers=_auth_headers(client))

    assert summary == {
        "shop_id": "shop_default",
        "session_id": "sess_default",
        "inventory_item_count": 3,
        "inventory_item_names": ["Coca Cola 500ml", "Cola", "Red Bull 250ml"],
        "pending_confirmation_count": 2,
        "pending_confirmation_types": ["receipt-stock-in-batch", "stock-out"],
        "open_low_stock_alert_count": 1,
        "open_low_stock_item_names": ["Cola"],
        "message_count": 10,
        "task_run_count": 4,
    }
    assert messages_response.status_code == 200
    assert len(messages_response.json()["data"]) == 10
    assert dashboard_response.status_code == 200
    assert dashboard_response.json()["data"]["today_stock_in_count"] == 3
    assert dashboard_response.json()["data"]["pending_confirmations_count"] == 2
    assert dashboard_response.json()["data"]["open_low_stock_alert_count"] == 1


def test_demo_bootstrap_endpoint_is_repeatable(client) -> None:
    first_summary = _post_demo_bootstrap(client)
    second_summary = _post_demo_bootstrap(client)

    assert second_summary == first_summary


def test_demo_bootstrap_endpoint_rejects_non_default_authenticated_shop(client) -> None:
    db_session = get_session_factory()()
    try:
        now = datetime.now(UTC).replace(tzinfo=None)
        shop = Shop(
            shop_id="shop_other",
            name="Other Shop",
            owner_name="Owner",
            industry="retail",
            locale="zh-CN",
            timezone="Asia/Shanghai",
            require_price_confirmation=True,
            require_new_item_confirmation=True,
            low_confidence_threshold=Decimal("0.8500"),
            default_low_stock_threshold=None,
            created_at=now,
            updated_at=now,
        )
        owner = OwnerAccount(
            actor_id="owner_other",
            email="other@example.com",
            display_name="Other Owner",
            password_hash="hash",
            password_salt="salt",
            status="active",
            created_at=now,
            updated_at=now,
        )
        membership = ShopMembership(
            membership_id="mship_other",
            shop_id=shop.shop_id,
            actor_id=owner.actor_id,
            role="owner",
            is_default_shop=True,
            created_at=now,
            updated_at=now,
        )
        db_session.add(shop)
        db_session.add(owner)
        db_session.add(membership)
        db_session.commit()

        token = issue_auth_session(
            db_session,
            actor_id=owner.actor_id,
            shop_id=shop.shop_id,
            ttl_minutes=30,
        ).access_token
    finally:
        db_session.close()

    response = client.post(
        "/api/v1/system/demo/bootstrap",
        headers=auth_headers(token),
    )

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "shop_not_found",
            "message": "Shop not found",
            "details": [],
        }
    }
