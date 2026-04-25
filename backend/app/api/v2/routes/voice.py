"""Voice API routes for stock queries and stock in."""

import json

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
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
from app.models import V2Account
from app.services.v2_voice import (
    VoiceASRError,
    VoiceIntentParseError,
    VoiceInventoryQueryError,
    process_voice_stock_query,
    process_voice_stock_in,
)

router = APIRouter(prefix="/api/v2/voice", tags=["v2-voice"])


def _context_account_mismatch() -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content=V2ErrorEnvelope(
            error=V2ErrorBody(code="context_account_mismatch", message="Context account mismatch")
        ).model_dump(),
    )


def _build_sse_stream(events):
    """Build SSE stream from async iterator."""
    async def generate():
        async for event in events:
            data_str = json.dumps(event.data, ensure_ascii=False)
            yield f"event: {event.event_type}\ndata: {data_str}\n\n".encode("utf-8")
    return generate()


@router.post("/stock-query", response_class=StreamingResponse)
async def voice_stock_query(
    audio: UploadFile = File(...),
    shop_id: str = Form(...),
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    db_session: Session = Depends(get_db_session),
) -> StreamingResponse:
    """Voice stock query - SSE streaming response.
    
    Upload audio file (webm/wav/mp3) and get stock query results via SSE.
    
    Event types:
    - transcription: {"text": "...", "confidence": 0.95}
    - intent: {"intent": "stock_query", "item_name": "...", "confidence": 0.85}
    - result: {"item": {...}, "stock": {...}, "found": true}
    - complete: {}
    - error: {"error": "...", "message": "..."}
    """
    if account.account_id != context.account_id:
        return _context_account_mismatch()

    # Read audio data
    audio_data = await audio.read()
    mime_type = audio.content_type or "audio/webm"

    try:
        events = process_voice_stock_query(
            db_session,
            tenant_id=context.tenant_id,
            shop_id=shop_id,
            audio_data=audio_data,
            mime_type=mime_type,
        )

        return StreamingResponse(
            _build_sse_stream(events),
            media_type="text/event-stream",
        )

    except VoiceASRError as exc:
        return JSONResponse(
            status_code=400,
            content=V2ErrorEnvelope(
                error=V2ErrorBody(code="asr_failed", message=str(exc))
            ).model_dump(),
        )
    except VoiceIntentParseError as exc:
        return JSONResponse(
            status_code=400,
            content=V2ErrorEnvelope(
                error=V2ErrorBody(code="intent_parse_failed", message=str(exc))
            ).model_dump(),
        )
@router.post("/stock-in", response_class=StreamingResponse)
async def voice_stock_in(
    audio: UploadFile = File(...),
    shop_id: str = Form(...),
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    db_session: Session = Depends(get_db_session),
) -> StreamingResponse:
    """Voice stock in - SSE streaming response.
    
    Upload audio describing stock in operation.
    
    Event types:
    - transcription: {"text": "...", "confidence": 0.95}
    - intent: {"intent": "stock_in", "items": [...], "supplier": "..."}
    - draft_created: {"draft_id": "...", "item_count": 3}
    - awaiting_confirmation: {"confirmation_id": "..."}
    - complete: {"draft_id": "..."}
    - error: {"error": "...", "message": "..."}
    """
    if account.account_id != context.account_id:
        return _context_account_mismatch()

    audio_data = await audio.read()
    mime_type = audio.content_type or "audio/webm"

    try:
        events = process_voice_stock_in(
            db_session,
            tenant_id=context.tenant_id,
            shop_id=shop_id,
            account_id=account.account_id,
            audio_data=audio_data,
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
