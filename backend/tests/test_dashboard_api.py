from decimal import Decimal

from sqlalchemy import select

from app.api.routes import messages as message_routes
from app.db.session import get_session_factory
from app.models import Confirmation
from app.runtime.processor import process_task_run
from app.services.approved_stock_in_commits import commit_approved_stock_in_confirmation
from app.services.bootstrap import ensure_default_context


AUTH_HEADERS = {"Authorization": "Bearer mock_owner_token"}


def _create_pending_confirmation(client, monkeypatch, *, client_request_id: str) -> str:
    monkeypatch.setattr(message_routes, "enqueue_runtime_task", lambda _task_run_id: True)
    create_response = client.post(
        "/api/v1/sessions/sess_default/messages",
        headers=AUTH_HEADERS,
        json={
            "message_type": "text",
            "text": "restock apples today",
            "media_ids": [],
            "client_request_id": client_request_id,
        },
    )
    assert create_response.status_code == 201
    task_run_id = create_response.json()["data"]["task_run_id"]

    db_session = get_session_factory()()
    try:
        runtime_result = process_task_run(db_session, task_run_id)
        assert runtime_result.status == "awaiting-confirmation"
    finally:
        db_session.close()

    return task_run_id


def _create_open_low_stock_alert(client, monkeypatch, *, client_request_id: str) -> None:
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
        confirmation = db_session.scalar(
            select(Confirmation).where(Confirmation.task_run_id == task_run_id)
        )
        assert confirmation is not None
        commit_approved_stock_in_confirmation(
            db_session,
            confirmation_id=confirmation.confirmation_id,
            payload_fields={"item_name": "Apple", "quantity": 3, "unit": "box", "price": 12.5},
            approved_by_actor_id="owner_default",
        )
    finally:
        db_session.close()


def test_get_dashboard_summary_returns_current_shop_counts(client, monkeypatch) -> None:
    _create_open_low_stock_alert(
        client,
        monkeypatch,
        client_request_id="dashboard_summary_stock_in",
    )
    _create_pending_confirmation(
        client,
        monkeypatch,
        client_request_id="dashboard_summary_pending_confirmation",
    )

    response = client.get("/api/v1/dashboard/summary", headers=AUTH_HEADERS)

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["shop_id"] == "shop_default"
    assert payload["today_stock_in_count"] == 1
    assert payload["today_task_completed_count"] == 1
    assert payload["pending_confirmations_count"] == 1
    assert payload["open_low_stock_alert_count"] == 1
    assert payload["last_inventory_event_at"] is not None
