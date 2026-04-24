"""V2 Chat API with SSE streaming for AI assistant interactions."""
from __future__ import annotations

import json
import uuid
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps.v2_context import (
    V2AuthenticatedAccount,
    V2ExecutionContext,
    require_v2_authenticated_account,
    require_v2_execution_context,
)
from app.contracts.v2.common import V2DataEnvelope, V2ErrorBody, V2ErrorEnvelope
from app.core.config import get_settings
from app.db.session import get_db_session
from app.services.v2_chat_session import get_chat_session_store
from app.services.v2_llm import LLMService, get_llm_service

router = APIRouter(prefix="/api/v2", tags=["v2-chat"])


@router.post("/chat", response_model=V2DataEnvelope[dict])
def chat_v2(
    payload: dict,
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    db_session: Session = Depends(get_db_session),
) -> V2DataEnvelope[dict]:
    """Non-streaming chat endpoint for simple queries with session support."""
    user_message = payload.get("message", "")
    session_id = payload.get("session_id")
    
    # Get or create chat session
    session_store = get_chat_session_store()
    session_id, chat_session = session_store.get_or_create(
        session_id=session_id,
        account_id=account.account_id,
        shop_id=context.shop_id,
    )
    
    # Save user message to history
    chat_session.add_turn("user", user_message)
    
    llm_service = get_llm_service()
    intent = llm_service.parse_intent(user_message, db_session)
    
    # Query inventory if needed
    query_result = _query_inventory_for_intent(intent, db_session, context.shop_id)
    
    # Generate response with history context
    if query_result:
        response = llm_service.generate_response(
            query_result, user_message, history=chat_session.to_messages()
        )
        reply = response.content
    else:
        reply = _build_fallback_reply(intent)
    
    # Save assistant response to history
    chat_session.add_turn("assistant", reply)
    
    return V2DataEnvelope(
        data={
            "message_id": str(uuid.uuid4()),
            "reply": reply,
            "intent": intent.intent_type,
            "item_name": intent.item_name,
            "confidence": intent.confidence,
            "session_id": session_id,
        }
    )


@router.post("/chat/stream")
def chat_stream_v2(
    request: Request,
    payload: dict,
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    db_session: Session = Depends(get_db_session),
) -> StreamingResponse:
    """SSE streaming chat endpoint for real-time AI responses with session support."""
    user_message = payload.get("message", "")
    session_id = payload.get("session_id")
    
    # Get or create chat session
    session_store = get_chat_session_store()
    session_id, chat_session = session_store.get_or_create(
        session_id=session_id,
        account_id=account.account_id,
        shop_id=context.shop_id,
    )
    
    # Save user message to history
    chat_session.add_turn("user", user_message)
    
    async def event_generator() -> AsyncGenerator[str, None]:
        llm_service = get_llm_service()
        
        # 1. Send intent recognition event with employee role
        intent = llm_service.parse_intent(user_message, db_session)
        role = _get_employee_role(intent.intent_type)
        yield _sse_event("intent", {
            "intent_type": intent.intent_type,
            "item_name": intent.item_name,
            "quantity": intent.quantity,
            "confidence": intent.confidence,
            "employee": role,
            "session_id": session_id,
        })
        
        # 2. Query inventory
        query_result = _query_inventory_for_intent(intent, db_session, context.shop_id)
        if query_result:
            yield _sse_event("inventory", {**query_result, "employee": role})
        
        # 3. Generate and stream response with history context
        reply_text = ""
        if query_result:
            response = llm_service.generate_response(
                query_result, user_message, history=chat_session.to_messages()
            )
            reply_text = response.content
            for event in _stream_text(reply_text):
                yield event
        else:
            reply_text = _build_fallback_reply(intent)
            for event in _stream_text(reply_text):
                yield event
        
        # Save assistant response to history
        chat_session.add_turn("assistant", reply_text)
        
        # 4. Send completion event with role
        yield _sse_event("done", {
            "message_id": str(uuid.uuid4()),
            "employee": role,
            "session_id": session_id,
        })
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _query_inventory_for_intent(
    intent,
    db_session: Session,
    shop_id: str,
) -> dict | None:
    """Query inventory based on parsed intent."""
    from sqlalchemy import select
    from app.models.v2_inventory import V2InventoryItem, V2InventoryStockSnapshot
    
    if intent.intent_type not in ("stock_query", "stock_in", "stock_out"):
        return None
    
    if not intent.item_name:
        return None
    
    # Find matching item
    stmt = (
        select(V2InventoryItem, V2InventoryStockSnapshot)
        .join(V2InventoryStockSnapshot, V2InventoryStockSnapshot.inventory_item_id == V2InventoryItem.inventory_item_id)
        .where(
            V2InventoryStockSnapshot.shop_id == shop_id,
        )
    )
    
    for item, snapshot in db_session.execute(stmt).all():
        if intent.item_name in item.name or item.name in intent.item_name:
            return {
                "item_id": item.inventory_item_id,
                "item_name": item.name,
                "sku": item.sku,
                "quantity": float(snapshot.current_quantity) if snapshot.current_quantity else 0,
                "unit": item.default_unit or "个",
                "threshold": float(snapshot.low_stock_threshold) if snapshot.low_stock_threshold else None,
            }
    
    return None


def _build_fallback_reply(intent) -> str:
    """Build fallback reply when no inventory data is found."""
    if intent.intent_type == "unknown":
        return "抱歉，我不理解您的意思。您可以问我：查库存、进货、出货。"
    elif intent.intent_type == "stock_query":
        if intent.item_name:
            return f"未找到商品 \"{intent.item_name}\"，请确认商品名称是否正确。"
        return "请告诉我您想查询什么商品的库存。"
    elif intent.intent_type == "stock_in":
        return f"收到入库请求：{intent.item_name or '未知商品'} x {intent.quantity or '?'}，请确认。"
    elif intent.intent_type == "stock_out":
        return f"收到出库请求：{intent.item_name or '未知商品'} x {intent.quantity or '?'}，请确认。"
    return "请问有什么可以帮您的？"


def _sse_event(event_type: str, data: dict) -> str:
    """Format SSE event."""
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _stream_text(text: str, chunk_size: int = 3):
    """Stream text in chunks that respect character boundaries.
    
    Uses chunk_size=3 for Chinese text to balance smooth typing effect
    with SSE efficiency. For mixed content, this avoids splitting
    UTF-8 code points since Python strings are Unicode code point sequences.
    """
    for i in range(0, len(text), chunk_size):
        chunk = text[i:i + chunk_size]
        yield _sse_event("token", {"token": chunk})


def _get_employee_role(intent_type: str) -> dict:
    """Get AI employee role info based on intent type."""
    roles = {
        "stock_query": {"name": "库存守护员", "color": "#10B981", "badge": "库存"},
        "stock_in": {"name": "库存守护员", "color": "#10B981", "badge": "入库"},
        "stock_out": {"name": "库存守护员", "color": "#10B981", "badge": "出库"},
        "price_query": {"name": "价格参谋", "color": "#F59E0B", "badge": "价格"},
        "sales_query": {"name": "销售分析员", "color": "#3B82F6", "badge": "销售"},
        "revenue_query": {"name": "营业数据员", "color": "#8B5CF6", "badge": "营收"},
        "alert_query": {"name": "库存守护员", "color": "#EF4444", "badge": "预警"},
        "unknown": {"name": "AI参谋", "color": "#6B7280", "badge": "助手"},
    }
    return roles.get(intent_type, roles["unknown"])
