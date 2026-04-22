from dataclasses import dataclass
from datetime import datetime, timezone
UTC = timezone.utc
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.ids import new_prefixed_id
from app.models import InventoryItem, Shop
from app.services.media_uploads import get_ready_media_upload
from app.services.mock_multimodal import recognize_and_query_inventory


class ApprovedFieldsValidationError(ValueError):
    pass


class InventoryItemNotFoundError(LookupError):
    pass


class InventoryItemAmbiguousError(ValueError):
    pass


class InventoryItemInactiveError(ValueError):
    pass


class InventoryUnitMismatchError(ValueError):
    pass


@dataclass(frozen=True)
class ApprovedStockInFields:
    item_id: str | None
    item_name: str | None
    quantity: Decimal
    unit: str
    price: Decimal


@dataclass(frozen=True)
class InventoryItemListPage:
    items: list[InventoryItem]


@dataclass(frozen=True)
class RecognizeAndQueryInventoryPage:
    item_id: str | None
    item_name: str
    confidence: float
    stock: Decimal | None
    unit: str | None
    is_low_stock: bool | None


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def list_inventory_items(
    db_session: Session,
    *,
    shop_id: str,
    query: str | None,
    limit: int,
) -> InventoryItemListPage:
    safe_limit = max(1, min(limit, 50))
    statement = select(InventoryItem).where(
        InventoryItem.shop_id == shop_id,
        InventoryItem.is_active.is_(True),
    )
    if query and query.strip():
        statement = statement.where(InventoryItem.name.ilike(f"%{query.strip()}%"))
    statement = statement.order_by(InventoryItem.updated_at.desc(), InventoryItem.item_id.desc()).limit(
        safe_limit
    )
    return InventoryItemListPage(items=list(db_session.scalars(statement)))


def get_inventory_item(
    db_session: Session,
    *,
    shop_id: str,
    item_id: str,
) -> InventoryItem:
    item = db_session.scalar(
        select(InventoryItem).where(
            InventoryItem.shop_id == shop_id,
            InventoryItem.item_id == item_id,
            InventoryItem.is_active.is_(True),
        )
    )
    if item is None:
        raise LookupError(item_id)
    return item


def recognize_inventory_item_from_media(
    db_session: Session,
    *,
    shop_id: str,
    media_id: str,
) -> RecognizeAndQueryInventoryPage:
    get_ready_media_upload(
        db_session,
        shop_id=shop_id,
        media_id=media_id,
        expected_media_types={"image"},
    )
    result = recognize_and_query_inventory(
        db_session,
        shop_id=shop_id,
        media_ids=[media_id],
        text_hint=None,
    )
    return RecognizeAndQueryInventoryPage(
        item_id=result.item_id,
        item_name=result.item_name,
        confidence=result.confidence,
        stock=result.stock,
        unit=result.unit,
        is_low_stock=result.is_low_stock,
    )


def parse_approved_stock_in_fields(payload: dict[str, Any]) -> ApprovedStockInFields:
    raw_item_id = payload.get("item_id")
    item_id = str(raw_item_id).strip() or None if raw_item_id is not None else None
    raw_item_name = payload.get("item_name")
    item_name = raw_item_name.strip() if isinstance(raw_item_name, str) and raw_item_name.strip() else None
    raw_unit = payload.get("unit")
    unit = raw_unit.strip() if isinstance(raw_unit, str) and raw_unit.strip() else None

    if item_id is None and item_name is None:
        raise ApprovedFieldsValidationError("item_name is required when item_id is absent")
    if unit is None:
        raise ApprovedFieldsValidationError("unit is required")

    try:
        quantity = Decimal(str(payload.get("quantity")))
        price = Decimal(str(payload.get("price")))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ApprovedFieldsValidationError("quantity and price must be numeric") from exc

    if quantity <= 0:
        raise ApprovedFieldsValidationError("quantity must be > 0")
    if price < 0:
        raise ApprovedFieldsValidationError("price must be >= 0")

    return ApprovedStockInFields(
        item_id=item_id,
        item_name=item_name,
        quantity=quantity,
        unit=unit,
        price=price,
    )


def _create_inventory_item(
    db_session: Session,
    *,
    shop: Shop,
    fields: ApprovedStockInFields,
) -> InventoryItem:
    now = _now()
    item = InventoryItem(
        item_id=new_prefixed_id("item"),
        shop_id=shop.shop_id,
        sku=None,
        name=fields.item_name or "",
        category=None,
        barcode=None,
        default_unit=fields.unit,
        current_stock=Decimal("0"),
        current_price=fields.price,
        low_stock_threshold=shop.default_low_stock_threshold,
        image_media_id=None,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    db_session.add(item)
    db_session.flush()
    return item


def resolve_inventory_item_for_stock_in(
    db_session: Session,
    *,
    shop: Shop,
    fields: ApprovedStockInFields,
) -> InventoryItem:
    if fields.item_id is not None:
        item = db_session.get(InventoryItem, fields.item_id)
        if item is None or item.shop_id != shop.shop_id:
            raise InventoryItemNotFoundError(fields.item_id)
        if not item.is_active:
            raise InventoryItemInactiveError(fields.item_id)
    else:
        matches = list(
            db_session.scalars(
                select(InventoryItem).where(
                    InventoryItem.shop_id == shop.shop_id,
                    InventoryItem.name == (fields.item_name or ""),
                    InventoryItem.is_active.is_(True),
                )
            )
        )
        if len(matches) > 1:
            raise InventoryItemAmbiguousError(fields.item_name or "")
        item = matches[0] if matches else _create_inventory_item(db_session, shop=shop, fields=fields)

    if item.default_unit != fields.unit:
        raise InventoryUnitMismatchError(item.item_id)

    return item
