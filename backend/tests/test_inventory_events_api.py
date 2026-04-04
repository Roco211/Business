from datetime import UTC, datetime
from decimal import Decimal

from app.db.session import get_session_factory
from app.models import InventoryItem
from app.services.bootstrap import ensure_default_context


AUTH_HEADERS = {"Authorization": "Bearer mock_owner_token"}


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _insert_item(
    *,
    item_id: str,
    name: str,
    stock: Decimal,
    threshold: Decimal | None,
    is_active: bool = True,
) -> InventoryItem:
    db_session = get_session_factory()()
    try:
        context = ensure_default_context(db_session)
        item = InventoryItem(
            item_id=item_id,
            shop_id=context.shop.shop_id,
            sku=None,
            name=name,
            category=None,
            barcode=None,
            default_unit="box",
            current_stock=stock,
            current_price=Decimal("12.50"),
            low_stock_threshold=threshold,
            image_media_id=None,
            is_active=is_active,
            created_at=_now(),
            updated_at=_now(),
        )
        db_session.add(item)
        db_session.commit()
        return item
    finally:
        db_session.close()


def test_post_inventory_correction_updates_stock_and_returns_event_id(client) -> None:
    item = _insert_item(
        item_id="item_correction_api_success",
        name="Apple",
        stock=Decimal("2"),
        threshold=Decimal("5"),
    )

    response = client.post(
        "/api/v1/inventory-events/corrections",
        headers=AUTH_HEADERS,
        json={
            "item_id": item.item_id,
            "corrected_quantity": 6,
            "reason": "Physical recount",
        },
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["item_id"] == item.item_id
    assert payload["new_quantity"] == "6"
    assert payload["correction_event_id"].startswith("inv_evt_")


def test_post_inventory_correction_returns_item_not_found(client) -> None:
    response = client.post(
        "/api/v1/inventory-events/corrections",
        headers=AUTH_HEADERS,
        json={
            "item_id": "item_missing",
            "corrected_quantity": 6,
            "reason": "Physical recount",
        },
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "item_not_found"


def test_post_inventory_correction_returns_validation_error_for_negative_quantity(client) -> None:
    item = _insert_item(
        item_id="item_correction_api_validation",
        name="Orange",
        stock=Decimal("2"),
        threshold=Decimal("5"),
    )

    response = client.post(
        "/api/v1/inventory-events/corrections",
        headers=AUTH_HEADERS,
        json={
            "item_id": item.item_id,
            "corrected_quantity": -1,
            "reason": "Physical recount",
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_post_inventory_correction_returns_inventory_conflict_for_inactive_item(client) -> None:
    item = _insert_item(
        item_id="item_correction_api_inactive",
        name="Pear",
        stock=Decimal("2"),
        threshold=Decimal("5"),
        is_active=False,
    )

    response = client.post(
        "/api/v1/inventory-events/corrections",
        headers=AUTH_HEADERS,
        json={
            "item_id": item.item_id,
            "corrected_quantity": 3,
            "reason": "Physical recount",
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "inventory_conflict"
