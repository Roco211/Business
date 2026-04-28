"""Photo service for image-based stock queries and receipt processing."""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from decimal import Decimal
import json
from typing import Any

from sqlalchemy.orm import Session

from app.services.v2_ai_confirmation import create_v2_ai_stock_in_confirmation
from app.services.v2_inventory import list_v2_inventory_items
from app.services.ocr_gateway import get_default_ocr_gateway
from app.services.ocr_types import OcrMediaInput
from app.services.vision_gateway import get_default_vision_gateway
from app.services.vision_types import VisionMediaInput


class PhotoProcessingError(ValueError):
    """Raised when photo processing fails."""
    pass


class PhotoItemNotFoundError(LookupError):
    """Raised when item is not found in photo."""
    pass


@dataclass(frozen=True)
class PhotoStockQueryResult:
    """Result of photo stock query."""
    item_id: str | None
    item_name: str | None
    quantity: float | None
    unit: str | None
    found: bool
    confidence: float


@dataclass(frozen=True)
class PhotoStockInDraftResult:
    """Result of photo stock in extraction."""
    draft_id: str
    items: list[dict]
    supplier: str | None
    total_amount: float | None


@dataclass(frozen=True)
class PhotoQueryEvent:
    """SSE event for photo processing stream."""
    event_type: str
    data: dict[str, Any]


async def process_photo_stock_query(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    image_data: bytes,
    mime_type: str,
) -> AsyncIterator[PhotoQueryEvent]:
    """Process photo stock query. 完整实现.

    Flow:
    1. OCR / Vision API 识别图片文字
    2. 解析并匹配库存商品 (fuzzy)
    3. 查询库存快照
    4. 流式返回结果 (SSE)
    """
    extracted = None
    item_name = None

    try:
        # Step 1: OCR extraction - 开始处理
        yield PhotoQueryEvent(
            event_type="processing",
            data={"stage": "ocr", "message": "正在识别图片..."},
        )

        extracted = await _extract_text_from_image(image_data, mime_type)

        yield PhotoQueryEvent(
            event_type="extraction",
            data={
                "raw_text": extracted.get("raw_text", ""),
                "confidence": extracted.get("confidence", 0.0),
                "cleaned_text": extracted.get("cleaned_text", ""),
                "provider": extracted.get("provider", ""),
                "used_fallback": extracted.get("used_fallback", False),
            },
        )

        # Step 2: Parse and match items
        yield PhotoQueryEvent(
            event_type="processing",
            data={"stage": "parsing", "message": "正在解析商品信息..."},
        )

        item_name = _parse_item_from_text(extracted)

        if not item_name:
            yield PhotoQueryEvent(
                event_type="error",
                data={"error": "no_item_found", "message": "未能从图片中识别出商品"},
            )
            return

        yield PhotoQueryEvent(
            event_type="item_detected",
            data={"item_name": item_name, "confidence": extracted.get("confidence", 0.8)},
        )

        # Step 3: Query inventory
        yield PhotoQueryEvent(
            event_type="processing",
            data={"stage": "querying", "message": "正在查询库存..."},
        )

        items = list_v2_inventory_items(
            db_session,
            tenant_id=tenant_id,
            query=item_name,
            limit=5,
        )

        if not items:
            yield PhotoQueryEvent(
                event_type="result",
                data={
                    "found": False,
                    "item_name": item_name,
                    "matches": [],
                    "message": f"未找到商品 '{item_name}' 的库存信息"
                },
            )
        else:
            from app.services.v2_inventory import list_v2_inventory_stock

            # Get stock for matched items
            stock_items = []
            for item in items[:3]:
                # 查询特定商品的库存快照
                stock = list_v2_inventory_stock(
                    db_session,
                    tenant_id=tenant_id,
                    shop_id=shop_id,
                    limit=50,  # 获取足够的数据进行筛选
                )

                # 查找匹配当前商品的库存
                matching_stock = None
                for snapshot, stock_item in stock:
                    if stock_item.inventory_item_id == item.inventory_item_id:
                        matching_stock = snapshot
                        break

                stock_entry = {
                    "item_id": item.inventory_item_id,
                    "item_name": item.name,
                    "quantity": float(matching_stock.current_quantity) if matching_stock else 0.0,
                    "unit": item.default_unit or "件",
                    "matched": matching_stock is not None
                }
                stock_items.append(stock_entry)

            yield PhotoQueryEvent(
                event_type="result",
                data={
                    "found": True,
                    "item_name": item_name,
                    "matches": stock_items,
                    "match_count": len(stock_items),
                },
            )

        # Step 4: Complete
        yield PhotoQueryEvent(
            event_type="complete",
            data={"message": "查询完成"},
        )

    except Exception as exc:
        yield PhotoQueryEvent(
            event_type="error",
            data={"error": "processing_failed", "message": str(exc)},
        )


async def process_photo_stock_in(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    account_id: str,
    image_data: bytes,
    mime_type: str,
) -> AsyncIterator[PhotoQueryEvent]:
    """Process photo stock in (receipt/invoice).

    Flow:
    1. OCR / Vision API 识别票据
    2. Extract structured data
    3. Create stock in draft
    4. Stream results
    """
    try:
        # Step 1: OCR
        yield PhotoQueryEvent(
            event_type="processing",
            data={"stage": "ocr", "message": "正在识别票据..."},
        )

        # Step 2: Extract receipt data
        extracted = await _extract_receipt_from_image(image_data, mime_type)

        yield PhotoQueryEvent(
            event_type="extraction",
            data=extracted,
        )

        # Step 3: Create a real pending confirmation. The photo/OCR path may
        # identify a stock-in draft, but inventory truth changes only after approval.
        items = list(extracted.get("items", []))
        if not items:
            yield PhotoQueryEvent(
                event_type="error",
                data={"error": "no_items_found", "message": "未能从票据中识别出入库商品"},
            )
            return
        first_item = items[0]
        draft_payload = {
            "item_name": first_item.get("name") or first_item.get("item_name"),
            "quantity": first_item.get("quantity"),
            "unit": first_item.get("unit") or "件",
            "price": first_item.get("price", 0),
            "supplier": extracted.get("supplier"),
        }
        created_confirmation = create_v2_ai_stock_in_confirmation(
            db_session,
            tenant_id=tenant_id,
            shop_id=shop_id,
            account_id=account_id,
            source_type="photo",
            source_text=json.dumps(extracted, ensure_ascii=False),
            draft_payload=draft_payload,
        )
        confirmation_id = created_confirmation.confirmation.confirmation_id
        task_run_id = created_confirmation.task_run.task_run_id

        yield PhotoQueryEvent(
            event_type="draft_created",
            data={
                "draft_id": confirmation_id,
                "confirmation_id": confirmation_id,
                "task_run_id": task_run_id,
                "item_count": len(items),
            },
        )

        # Step 4: Await confirmation
        yield PhotoQueryEvent(
            event_type="awaiting_confirmation",
            data={
                "message": "请确认入库信息",
                "confirmation_id": confirmation_id,
                "task_run_id": task_run_id,
            },
        )

        yield PhotoQueryEvent(
            event_type="complete",
            data={
                "draft_id": confirmation_id,
                "confirmation_id": confirmation_id,
                "task_run_id": task_run_id,
            },
        )

    except Exception as exc:
        yield PhotoQueryEvent(
            event_type="error",
            data={"error": "processing_failed", "message": str(exc)},
        )


async def _extract_text_from_image(image_data: bytes, mime_type: str) -> dict:
    """Extract product information from an image through the Vision gateway."""
    _validate_image_input(image_data, mime_type)

    recognition = get_default_vision_gateway().recognize_product(
        VisionMediaInput(
            media_id="inline-photo-stock-query",
            public_url=None,
            content_type=mime_type,
            file_name=None,
            image_bytes=image_data,
        )
    )
    candidates = list(recognition.candidates)
    top_candidate = candidates[0] if candidates else None
    item_name = top_candidate.item_name if top_candidate is not None else ""
    confidence = top_candidate.confidence if top_candidate is not None else 0.0
    packaging_hint = top_candidate.packaging_hint if top_candidate is not None else None
    return {
        "raw_text": item_name,
        "cleaned_text": item_name,
        "item_name": item_name,
        "category": packaging_hint,
        "confidence": confidence,
        "provider": recognition.provider_name,
        "used_fallback": recognition.used_fallback,
        "candidates": [
            {
                "item_name": candidate.item_name,
                "confidence": candidate.confidence,
                "packaging_hint": candidate.packaging_hint,
            }
            for candidate in candidates
        ],
        "raw_payload": recognition.raw_payload,
    }


async def _extract_receipt_from_image(image_data: bytes, mime_type: str) -> dict:
    """Extract purchase receipt data through the OCR gateway."""
    _validate_image_input(image_data, mime_type)

    extraction = get_default_ocr_gateway().extract_purchase_receipt(
        OcrMediaInput(
            media_id="inline-photo-stock-in",
            public_url=None,
            content_type=mime_type,
            file_name=None,
            image_bytes=image_data,
        )
    )
    raw_payload = extraction.raw_payload or {}
    supplier = raw_payload.get("supplier") or raw_payload.get("supplier_name")
    items = [
        {
            "name": line.item_name,
            "quantity": line.quantity,
            "unit": line.unit or "件",
            "price": line.price if line.price is not None else 0,
        }
        for line in extraction.line_items
        if line.item_name
    ]
    return {
        "provider": extraction.provider_name,
        "document_type": extraction.document_type,
        "raw_text": extraction.raw_text,
        "supplier": supplier,
        "items": items,
        "total_amount": extraction.total_amount,
        "low_confidence_fields": list(extraction.low_confidence_fields),
        "used_fallback": extraction.used_fallback,
        "raw_payload": raw_payload,
    }


def _validate_image_input(image_data: bytes, mime_type: str) -> None:
    valid_types = {"image/jpeg", "image/png", "image/webp", "image/jpg"}
    if mime_type not in valid_types:
        raise PhotoProcessingError(f"Unsupported image type: {mime_type}")
    if not image_data:
        raise PhotoProcessingError("Empty image data")


def _parse_item_from_text(extracted: dict | str | None) -> str | None:
    """Parse item name from extracted OCR result.

    Args:
        extracted: OCR提取结果 (dict 或字符串)

    Returns:
        商品名称或None
    """
    if extracted is None:
        return None

    # 如果已经是结构化提取结果，优先使用item_name
    if isinstance(extracted, dict):
        item_name = extracted.get("item_name")
        if item_name and item_name.strip():
            return item_name.strip()

        # 其次使用cleaned_text
        cleaned_text = extracted.get("cleaned_text", "")
        if cleaned_text and cleaned_text.strip():
            return _clean_item_name(cleaned_text.strip())

        # 最后使用raw_text
        raw_text = extracted.get("raw_text", "")
        if raw_text and raw_text.strip():
            return _clean_item_name(raw_text.strip())

        # 向后兼容: 如果是字符串
    if isinstance(extracted, str):
        return _clean_item_name(extracted.strip())

    return None


def _clean_item_name(text: str) -> str | None:
    """Clean and extract item name from text string."""
    if not text:
        return None

    lines = text.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue

        # 移除常见计量单位和数量词
        cleaned = line
        quantity_patterns = ['把', '个', '件', '箱', '瓶', '袋', '盒', '套', '双', '副']
        number_patterns = ['50', '100', '200', '500', '1000', '1', '2', '3', '5', '10', '20']
        desc_patterns = ['十字', '一字', '大号', '中号', '小号', '加粗', '标准', 'JIS']

        # 先尝试保留描述性词汇，只去除数量
        for pattern in quantity_patterns + number_patterns:
            cleaned = cleaned.replace(pattern, '')

        cleaned = cleaned.strip()

        # 如果清理后仍有内容且长度>=2
        if cleaned and len(cleaned) >= 2:
            return cleaned

        # 如果清理后太短，返回原始行
        if line and len(line) >= 2:
            return line

    return lines[0].strip() if lines else None



def _build_sse_event(event_type: str, data: dict[str, Any]) -> str:
    """Build SSE formatted event string."""
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
