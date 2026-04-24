"""Photo API routes for image-based stock queries and receipt processing."""

import json

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps.v2_context import (
    V2AuthenticatedAccount,
    V2ExecutionContext,
    require_v2_authenticated_account,
    require_v2_execution_context,
)
from app.contracts.v2.common import V2DataEnvelope, V2ErrorBody, V2ErrorEnvelope
from app.db.session import get_db_session
from app.services.v2_photo import process_photo_stock_in, process_photo_stock_query

router = APIRouter(prefix="/api/v2/photo", tags=["v2-photo"])


def _context_account_mismatch() -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content=V2ErrorEnvelope(
            error=V2ErrorBody(code="context_account_mismatch", message="Context account mismatch")
        ).model_dump(),
    )


async def _build_sse_stream(events):
    """Build SSE stream from async iterator.

    正确格式化SSE事件流:
    - event: 事件类型
    - data: JSON序列化的数据
    """
    async def generate():
        async for event in events:
            # 使用json.dumps确保data是有效的JSON字符串
            data_json = json.dumps(event.data, ensure_ascii=False)
            # SSE格式: event: <event_type>\ndata: <json_data>\n\n
            yield f"event: {event.event_type}\ndata: {data_json}\n\n".encode("utf-8")
    return generate()


@router.post("/stock-query", response_class=StreamingResponse)
async def photo_stock_query(
    image: UploadFile = File(...),
    shop_id: str = Form(...),
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    db_session: Session = Depends(get_db_session),
) -> StreamingResponse:
    """Photo stock query - SSE streaming response.
    
    Upload image file (jpeg/png/webp) and get stock query results via SSE.
    
    Event types:
    - processing: {"stage": "ocr", "message": "..."}
    - extraction: {"text": "...", "confidence": 0.85}
    - item_detected: {"item_name": "...", "confidence": 0.8}
    - result: {"found": true/false, "matches": [...]}
    - complete: {}
    - error: {"error": "...", "message": "..."}
    """
    if account.account_id != context.account_id:
        return _context_account_mismatch()

    image_data = await image.read()
    mime_type = image.content_type or "image/jpeg"

    try:
        events = process_photo_stock_query(
            db_session,
            tenant_id=context.tenant_id,
            shop_id=shop_id,
            image_data=image_data,
            mime_type=mime_type,
        )

        return StreamingResponse(
            _build_sse_stream(events),
            media_type="text/event-stream",
        )

    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content=V2ErrorEnvelope(
                error=V2ErrorBody(code="internal_error", message=str(exc))
            ).model_dump(),
        )


@router.post("/stock-in", response_class=StreamingResponse)
async def photo_stock_in(
    image: UploadFile = File(...),
    shop_id: str = Form(...),
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    db_session: Session = Depends(get_db_session),
) -> StreamingResponse:
    """Photo stock in - SSE streaming response.
    
    Upload receipt/invoice image and get stock in draft via SSE.
    
    Event types:
    - processing: {"stage": "ocr", "message": "..."}
    - extraction: {...}
    - draft_created: {"draft_id": "...", "item_count": N}
    - awaiting_confirmation: {"message": "...", "confirmation_id": "..."}
    - complete: {"draft_id": "..."}
    - error: {"error": "...", "message": "..."}
    """
    if account.account_id != context.account_id:
        return _context_account_mismatch()

    image_data = await image.read()
    mime_type = image.content_type or "image/jpeg"

    try:
        events = process_photo_stock_in(
            db_session,
            tenant_id=context.tenant_id,
            shop_id=shop_id,
            account_id=account.account_id,
            image_data=image_data,
            mime_type=mime_type,
        )

        return StreamingResponse(
            _build_sse_stream(events),
            media_type="text/event-stream",
        )

    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content=V2ErrorEnvelope(
                error=V2ErrorBody(code="internal_error", message=str(exc))
            ).model_dump(),
        )
