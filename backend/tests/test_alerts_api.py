from decimal import Decimal

from sqlalchemy import select

from app.api.routes import messages as message_routes
from app.db.session import get_session_factory
from app.models import Confirmation
from app.runtime.processor import process_task_run
from app.services.approved_stock_in_commits import commit_approved_stock_in_confirmation
from app.services.bootstrap import ensure_default_context
from conftest import auth_headers, login_and_get_token

def _auth_headers(client, monkeypatch=None) -> dict[str, str]:
    return auth_headers(login_and_get_token(client, monkeypatch))


def _create_pending_confirmation(client, monkeypatch, *, client_request_id: str) -> str:
    monkeypatch.setattr(message_routes, "enqueue_runtime_task", lambda _task_run_id: True)
    create_response = client.post(
        "/api/v1/sessions/sess_default/messages",
        headers=_auth_headers(client, monkeypatch),
        json={
            "message_type": "text",
            "text": "restock apples today",
            "media_ids": [],
            "client_request_id": client_request_id,
        },
    )
    assert create_response.status_code == 201
    return create_response.json()["data"]["task_run_id"]


def _commit_low_stock_item(client, monkeypatch, *, client_request_id: str, item_name: str) -> str:
    task_run_id = _create_pending_confirmation(
        client,
        monkeypatch,
        client_request_id=client_request_id,
    )
    db_session = get_session_factory()()
    try:
        context = ensure_default_context(db_session)
        context.shop.default_low_stock_threshold = Decimal("5")
        db_session.commit()

        runtime_result = process_task_run(db_session, task_run_id)
        assert runtime_result.status == "awaiting-confirmation"
        confirmation = db_session.scalar(
            select(Confirmation).where(Confirmation.task_run_id == task_run_id)
        )
        assert confirmation is not None
        result = commit_approved_stock_in_confirmation(
            db_session,
            confirmation_id=confirmation.confirmation_id,
            payload_fields={"item_name": item_name, "quantity": 3, "unit": "box", "price": 12.5},
            approved_by_actor_id="owner_default",
        )
        return result.inventory_item.item_id
    finally:
        db_session.close()


def test_get_alerts_returns_open_low_stock_alerts_with_item_context(client, monkeypatch) -> None:
    item_id = _commit_low_stock_item(
        client,
        monkeypatch,
        client_request_id="alerts_api_open_item",
        item_name="Apple",
    )

    response = client.get("/api/v1/alerts?type=low-stock&limit=20", headers=_auth_headers(client))

    assert response.status_code == 200
    payload = response.json()
    assert payload["meta"]["count"] == 1
    assert payload["data"][0]["item_id"] == item_id
    assert payload["data"][0]["item_name"] == "Apple"
    assert payload["data"][0]["status"] == "open"
    assert payload["data"][0]["stock"] == "3.000"
    assert payload["data"][0]["threshold"] == "5.000"


def test_get_alerts_rejects_unsupported_type(client) -> None:
    response = client.get("/api/v1/alerts?type=other", headers=_auth_headers(client))

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unsupported_alert_type"
