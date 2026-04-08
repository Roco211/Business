from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import Confirmation
from app.runtime.processor import process_task_run
from app.services.approved_stock_in_commits import commit_approved_stock_in_confirmation
from app.services.audit_logs import UnsupportedAuditScopeError, list_audit_logs
from app.services.bootstrap import ensure_default_context
from app.services.inventory_items import get_inventory_item, list_inventory_items
from app.services.messages import create_message


def _seed_committed_stock_in(
    db_session,
    *,
    client_request_id: str,
    item_name: str,
    quantity: int,
) -> str:
    context = ensure_default_context(db_session)
    message_result = create_message(
        db_session,
        session_id=context.session.session_id,
        actor_type="owner",
        actor_id="owner_default",
        message_type="text",
        text=f"restock {item_name}",
        media_ids=[],
        client_request_id=client_request_id,
    )
    runtime_result = process_task_run(db_session, message_result.task_run_id)
    assert runtime_result.status == "awaiting-confirmation"

    confirmation = db_session.scalar(
        select(Confirmation).where(Confirmation.task_run_id == message_result.task_run_id)
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


def test_list_inventory_items_orders_by_updated_at_desc_and_filters_by_query(db_session) -> None:
    older_item_id = _seed_committed_stock_in(
        db_session,
        client_request_id="inventory_read_service_older",
        item_name="Apple",
        quantity=1,
    )
    newer_item_id = _seed_committed_stock_in(
        db_session,
        client_request_id="inventory_read_service_newer",
        item_name="Orange",
        quantity=2,
    )

    all_items = list_inventory_items(db_session, shop_id="shop_default", query=None, limit=20)
    filtered_items = list_inventory_items(db_session, shop_id="shop_default", query="ora", limit=20)

    assert [item.item_id for item in all_items.items[:2]] == [newer_item_id, older_item_id]
    assert [item.name for item in filtered_items.items] == ["Orange"]


def test_get_inventory_item_returns_matching_shop_item(db_session) -> None:
    item_id = _seed_committed_stock_in(
        db_session,
        client_request_id="inventory_read_service_detail",
        item_name="Apple",
        quantity=3,
    )

    item = get_inventory_item(db_session, shop_id="shop_default", item_id=item_id)

    assert item.item_id == item_id
    assert item.current_stock == Decimal("3")


def test_get_inventory_item_raises_lookup_error_for_missing_item(db_session) -> None:
    ensure_default_context(db_session)

    with pytest.raises(LookupError):
        get_inventory_item(db_session, shop_id="shop_default", item_id="item_missing")


def test_list_audit_logs_orders_newest_first_and_requires_inventory_scope(db_session) -> None:
    _seed_committed_stock_in(
        db_session,
        client_request_id="inventory_read_service_audit_older",
        item_name="Apple",
        quantity=1,
    )
    _seed_committed_stock_in(
        db_session,
        client_request_id="inventory_read_service_audit_newer",
        item_name="Orange",
        quantity=2,
    )

    page = list_audit_logs(db_session, shop_id="shop_default", scope="inventory", limit=20)

    assert len(page.items) == 2
    assert page.items[0].created_at >= page.items[1].created_at
    assert page.items[0].scope == "inventory"

    with pytest.raises(UnsupportedAuditScopeError):
        list_audit_logs(db_session, shop_id="shop_default", scope="other", limit=20)
