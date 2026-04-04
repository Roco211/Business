from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.models import InventoryItem
from app.services.bootstrap import ensure_default_context
from app.services.inventory_items import (
    ApprovedFieldsValidationError,
    ApprovedStockInFields,
    InventoryItemAmbiguousError,
    InventoryItemInactiveError,
    InventoryItemNotFoundError,
    InventoryUnitMismatchError,
    parse_approved_stock_in_fields,
    resolve_inventory_item_for_stock_in,
)


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _insert_item(db_session, *, item_id: str, name: str, unit: str, is_active: bool = True) -> InventoryItem:
    context = ensure_default_context(db_session)
    item = InventoryItem(
        item_id=item_id,
        shop_id=context.shop.shop_id,
        sku=None,
        name=name,
        category=None,
        barcode=None,
        default_unit=unit,
        current_stock=Decimal("0"),
        current_price=Decimal("12.50"),
        low_stock_threshold=context.shop.default_low_stock_threshold,
        image_media_id=None,
        is_active=is_active,
        created_at=_now(),
        updated_at=_now(),
    )
    db_session.add(item)
    db_session.commit()
    return item


def test_parse_approved_stock_in_fields_accepts_current_owner_payload() -> None:
    assert parse_approved_stock_in_fields(
        {"item_name": "Apple", "quantity": 3, "unit": "box", "price": 18.5}
    ) == ApprovedStockInFields(
        item_id=None,
        item_name="Apple",
        quantity=Decimal("3"),
        unit="box",
        price=Decimal("18.5"),
    )


def test_parse_approved_stock_in_fields_rejects_missing_item_reference() -> None:
    with pytest.raises(ApprovedFieldsValidationError, match="item_name"):
        parse_approved_stock_in_fields({"quantity": 3, "unit": "box", "price": 18.5})


def test_resolve_inventory_item_creates_new_item_when_name_missing(db_session) -> None:
    context = ensure_default_context(db_session)
    item = resolve_inventory_item_for_stock_in(
        db_session,
        shop=context.shop,
        fields=ApprovedStockInFields(
            item_id=None,
            item_name="Apple",
            quantity=Decimal("3"),
            unit="box",
            price=Decimal("18.5"),
        ),
    )

    assert item.shop_id == context.shop.shop_id
    assert item.name == "Apple"
    assert item.default_unit == "box"
    assert item.current_stock == Decimal("0")


def test_resolve_inventory_item_reuses_existing_item_by_item_id(db_session) -> None:
    context = ensure_default_context(db_session)
    existing = _insert_item(db_session, item_id="item_existing", name="Apple", unit="box")

    item = resolve_inventory_item_for_stock_in(
        db_session,
        shop=context.shop,
        fields=ApprovedStockInFields(
            item_id=existing.item_id,
            item_name=None,
            quantity=Decimal("2"),
            unit="box",
            price=Decimal("20"),
        ),
    )

    assert item.item_id == existing.item_id


def test_resolve_inventory_item_reuses_existing_item_by_exact_name(db_session) -> None:
    context = ensure_default_context(db_session)
    existing = _insert_item(db_session, item_id="item_by_name", name="Apple", unit="box")

    item = resolve_inventory_item_for_stock_in(
        db_session,
        shop=context.shop,
        fields=ApprovedStockInFields(
            item_id=None,
            item_name="Apple",
            quantity=Decimal("2"),
            unit="box",
            price=Decimal("20"),
        ),
    )

    assert item.item_id == existing.item_id


def test_resolve_inventory_item_rejects_unknown_item_id(db_session) -> None:
    context = ensure_default_context(db_session)

    with pytest.raises(InventoryItemNotFoundError):
        resolve_inventory_item_for_stock_in(
            db_session,
            shop=context.shop,
            fields=ApprovedStockInFields(
                item_id="item_missing",
                item_name=None,
                quantity=Decimal("2"),
                unit="box",
                price=Decimal("20"),
            ),
        )


def test_resolve_inventory_item_rejects_inactive_item_id(db_session) -> None:
    context = ensure_default_context(db_session)
    existing = _insert_item(db_session, item_id="item_inactive", name="Apple", unit="box", is_active=False)

    with pytest.raises(InventoryItemInactiveError):
        resolve_inventory_item_for_stock_in(
            db_session,
            shop=context.shop,
            fields=ApprovedStockInFields(
                item_id=existing.item_id,
                item_name=None,
                quantity=Decimal("2"),
                unit="box",
                price=Decimal("20"),
            ),
        )


def test_resolve_inventory_item_rejects_ambiguous_name_match(db_session) -> None:
    context = ensure_default_context(db_session)
    _insert_item(db_session, item_id="item_a", name="Apple", unit="box")
    _insert_item(db_session, item_id="item_b", name="Apple", unit="box")

    with pytest.raises(InventoryItemAmbiguousError):
        resolve_inventory_item_for_stock_in(
            db_session,
            shop=context.shop,
            fields=ApprovedStockInFields(
                item_id=None,
                item_name="Apple",
                quantity=Decimal("2"),
                unit="box",
                price=Decimal("20"),
            ),
        )


def test_resolve_inventory_item_rejects_unit_mismatch_for_existing_item(db_session) -> None:
    context = ensure_default_context(db_session)
    existing = _insert_item(db_session, item_id="item_unit_mismatch", name="Apple", unit="box")

    with pytest.raises(InventoryUnitMismatchError):
        resolve_inventory_item_for_stock_in(
            db_session,
            shop=context.shop,
            fields=ApprovedStockInFields(
                item_id=existing.item_id,
                item_name=None,
                quantity=Decimal("2"),
                unit="bottle",
                price=Decimal("20"),
            ),
        )
