"""Voice query service for voice-based stock queries.

This module provides NLP intent parsing and inventory lookup for voice queries.
"""

from dataclasses import dataclass
from decimal import Decimal
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import V2InventoryItem, V2InventoryStockSnapshot


@dataclass(frozen=True)
class StockQueryIntent:
    """Parsed intent from voice query."""

    intent_type: str
    item_name: str | None
    confidence: float


@dataclass(frozen=True)
class StockQueryResult:
    """Result of stock query."""

    item_id: str | None
    item_name: str | None
    quantity: Decimal | None
    unit: str | None
    found: bool


class StockQueryParseError(ValueError):
    """Raised when stock query parsing fails."""

    pass


class StockQueryNotFoundError(LookupError):
    """Raised when queried item is not found."""

    pass


# Common Chinese query patterns for stock queries
_STOCK_QUERY_PATTERNS = [
    # "还有多少X", "X还有几个", "X剩多少"
    r"还有[多好多多少少]?([^还有几个个箱瓶件包]?[^多少剩还]?)",
    r"([^还有几个个箱瓶件包]+?)还有[多少几个]",
    r"([^还有几个个]+?)[剩还余]多少",
    r"([^多少]+?)[的]?库存[多少]?",
    r"查询[一下]?([^查询]+?)[的]?[库存还有]?$",
    r"查看[一下]?([^查看]+?)[的]?[库存还有]?$",
    r"查一下([^查]+?)[的]?[库存]?$",
]


def parse_stock_query_intent(text: str) -> StockQueryIntent:
    """Parse stock query intent from transcribed text.

    Uses rule-based matching for common Chinese stock query patterns.
    In production, this should be replaced with an ML-based NER model.

    Args:
        text: Transcribed text from ASR

    Returns:
        StockQueryIntent with parsed intent type and item name

    Raises:
        StockQueryParseError: If no stock query intent is detected
    """
    if not text or not text.strip():
        raise StockQueryParseError("Empty text input")

    text = text.strip()

    # Check for stock query keywords
    stock_keywords = ["还有", "剩", "余", "库存", "查", "多少"]
    has_stock_keyword = any(kw in text for kw in stock_keywords)

    if not has_stock_keyword:
        return StockQueryIntent(
            intent_type="unknown",
            item_name=None,
            confidence=0.2,
        )

    # Try to extract item name
    item_name = _extract_item_name(text)

    return StockQueryIntent(
        intent_type="stock_query",
        item_name=item_name,
        confidence=0.85 if item_name else 0.6,
    )


def _extract_item_name(text: str) -> str | None:
    """Extract item name from query text.

    Args:
        text: Query text

    Returns:
        Extracted item name or None
    """
    # Remove common stop words and query words
    stop_words = [
        "还有", "多少", "几个", "箱", "瓶", "件", "包", "个",
        "剩", "余", "库存", "查询", "查看", "看一下", "查一下", "查",
        "的", "了", "吗", "呢", "啊",
    ]

    text_clean = text
    for word in stop_words:
        text_clean = text_clean.replace(word, "")

    text_clean = text_clean.strip()

    # If after cleaning we have text, use it as item name
    if text_clean:
        return text_clean

    return None


def query_inventory_stock(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    item_name: str | None,
) -> StockQueryResult:
    """Query inventory stock for given item name.

    Args:
        db_session: Database session
        tenant_id: Tenant ID for multi-tenant isolation
        shop_id: Shop ID for shop-level stock lookup
        item_name: Item name to query (optional)

    Returns:
        StockQueryResult with stock information

    Raises:
        StockQueryNotFoundError: If item is not found
    """
    if not item_name or not item_name.strip():
        # Return first item if no name specified (for demo purposes)
        statement = (
            select(V2InventoryStockSnapshot, V2InventoryItem)
            .join(
                V2InventoryItem,
                V2InventoryItem.inventory_item_id == V2InventoryStockSnapshot.inventory_item_id,
            )
            .where(
                V2InventoryStockSnapshot.tenant_id == tenant_id,
                V2InventoryStockSnapshot.shop_id == shop_id,
            )
            .order_by(V2InventoryStockSnapshot.updated_at.desc())
            .limit(1)
        )
        result = db_session.execute(statement).first()

        if not result:
            return StockQueryResult(
                item_id=None,
                item_name=None,
                quantity=None,
                unit=None,
                found=False,
            )

        snapshot, item = result
        return StockQueryResult(
            item_id=item.inventory_item_id,
            item_name=item.name,
            quantity=snapshot.current_quantity,
            unit=item.default_unit,
            found=True,
        )

    # Search for item by name (fuzzy match)
    # First try exact match
    statement = (
        select(V2InventoryStockSnapshot, V2InventoryItem)
        .join(
            V2InventoryItem,
            V2InventoryItem.inventory_item_id == V2InventoryStockSnapshot.inventory_item_id,
        )
        .where(
            V2InventoryItem.tenant_id == tenant_id,
            V2InventoryStockSnapshot.shop_id == shop_id,
            V2InventoryItem.name == item_name,
        )
        .limit(1)
    )
    result = db_session.execute(statement).first()

    if result:
        snapshot, item = result
        return StockQueryResult(
            item_id=item.inventory_item_id,
            item_name=item.name,
            quantity=snapshot.current_quantity,
            unit=item.default_unit,
            found=True,
        )

    # Try partial match (contains)
    statement = (
        select(V2InventoryStockSnapshot, V2InventoryItem)
        .join(
            V2InventoryItem,
            V2InventoryItem.inventory_item_id == V2InventoryStockSnapshot.inventory_item_id,
        )
        .where(
            V2InventoryItem.tenant_id == tenant_id,
            V2InventoryStockSnapshot.shop_id == shop_id,
            V2InventoryItem.name.ilike(f"%{item_name}%"),
        )
        .order_by(V2InventoryStockSnapshot.updated_at.desc())
        .limit(1)
    )
    result = db_session.execute(statement).first()

    if result:
        snapshot, item = result
        return StockQueryResult(
            item_id=item.inventory_item_id,
            item_name=item.name,
            quantity=snapshot.current_quantity,
            unit=item.default_unit,
            found=True,
        )

    # Item not found
    return StockQueryResult(
        item_id=None,
        item_name=item_name,
        quantity=None,
        unit=None,
        found=False,
    )
