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
) -> None:
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
        commit_approved_stock_in_confirmation(
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
    finally:
        db_session.close()


def test_get_audit_logs_lists_inventory_scope_newest_first(client, monkeypatch) -> None:
    _commit_stock_in(
        client,
        monkeypatch,
        client_request_id="audit_logs_api_older",
        item_name="Apple",
        quantity=1,
    )
    _commit_stock_in(
        client,
        monkeypatch,
        client_request_id="audit_logs_api_newer",
        item_name="Orange",
        quantity=2,
    )

    response = client.get("/api/v1/audit-logs?scope=inventory&limit=20", headers=AUTH_HEADERS)

    assert response.status_code == 200
    payload = response.json()
    assert payload["meta"]["count"] == 2
    assert payload["data"][0]["created_at"] >= payload["data"][1]["created_at"]
    assert payload["data"][0]["scope"] == "inventory"


def test_get_audit_logs_rejects_unsupported_scope(client) -> None:
    response = client.get("/api/v1/audit-logs?scope=other", headers=AUTH_HEADERS)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unsupported_audit_scope"
