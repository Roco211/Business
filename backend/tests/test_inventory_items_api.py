from sqlalchemy import select

from app.api.routes import messages as message_routes
from app.db.session import get_session_factory
from app.models import Confirmation
from app.runtime.processor import process_task_run
from app.services.approved_stock_in_commits import commit_approved_stock_in_confirmation


AUTH_HEADERS = {"Authorization": "Bearer mock_owner_token"}


def _commit_stock_in(
    client,
    monkeypatch,
    *,
    client_request_id: str,
    item_name: str,
    quantity: int,
) -> str:
    monkeypatch.setattr(message_routes, "enqueue_runtime_task", lambda _task_run_id: True)
    create_response = client.post(
        "/api/v1/sessions/sess_default/messages",
        headers=AUTH_HEADERS,
        json={
            "message_type": "text",
            "text": f"restock {item_name}",
            "media_ids": [],
            "client_request_id": client_request_id,
        },
    )
    assert create_response.status_code == 201

    task_run_id = create_response.json()["data"]["task_run_id"]
    db_session = get_session_factory()()
    try:
        result = process_task_run(db_session, task_run_id)
        assert result.status == "awaiting-confirmation"
        confirmation = db_session.scalar(
            select(Confirmation).where(Confirmation.task_run_id == task_run_id)
        )
        assert confirmation is not None

        commit_result = commit_approved_stock_in_confirmation(
            db_session,
            confirmation_id=confirmation.confirmation_id,
            payload_fields={
                "item_name": item_name,
                "quantity": quantity,
                "unit": "box",
                "price": 12.5,
            },
            approved_by_actor_id="owner_default",
        )
        return commit_result.inventory_item.item_id
    finally:
        db_session.close()


def test_get_inventory_items_lists_active_items_newest_first(client, monkeypatch) -> None:
    older_item_id = _commit_stock_in(
        client,
        monkeypatch,
        client_request_id="inventory_items_api_older",
        item_name="Apple",
        quantity=1,
    )
    newer_item_id = _commit_stock_in(
        client,
        monkeypatch,
        client_request_id="inventory_items_api_newer",
        item_name="Orange",
        quantity=2,
    )

    response = client.get("/api/v1/inventory-items?limit=20", headers=AUTH_HEADERS)

    assert response.status_code == 200
    payload = response.json()
    assert payload["meta"]["count"] == 2
    assert [item["item_id"] for item in payload["data"][:2]] == [newer_item_id, older_item_id]


def test_get_inventory_items_filters_by_query(client, monkeypatch) -> None:
    _commit_stock_in(
        client,
        monkeypatch,
        client_request_id="inventory_items_api_query_apple",
        item_name="Apple",
        quantity=1,
    )
    _commit_stock_in(
        client,
        monkeypatch,
        client_request_id="inventory_items_api_query_orange",
        item_name="Orange",
        quantity=2,
    )

    response = client.get("/api/v1/inventory-items?query=ora", headers=AUTH_HEADERS)

    assert response.status_code == 200
    payload = response.json()
    assert [item["name"] for item in payload["data"]] == ["Orange"]


def test_get_inventory_item_returns_detail_and_not_found(client, monkeypatch) -> None:
    item_id = _commit_stock_in(
        client,
        monkeypatch,
        client_request_id="inventory_items_api_detail",
        item_name="Apple",
        quantity=3,
    )

    response = client.get(f"/api/v1/inventory-items/{item_id}", headers=AUTH_HEADERS)
    not_found_response = client.get("/api/v1/inventory-items/item_missing", headers=AUTH_HEADERS)

    assert response.status_code == 200
    assert response.json()["data"]["item_id"] == item_id
    assert response.json()["data"]["current_stock"] == "3.000"
    assert not_found_response.status_code == 404
    assert not_found_response.json()["error"]["code"] == "inventory_item_not_found"
