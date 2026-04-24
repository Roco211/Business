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
from app.services.v2_conversation import create_v2_message_and_task_run
from app.services.v2_inventory import (
    commit_v2_inventory_stock_in,
    commit_v2_inventory_stock_out,
)
from app.services.v2_analytics import (
    get_revenue_summary,
    get_sales_ranking,
    get_low_stock_alerts,
    get_daily_revenue_series,
)
from app.models.v2_inventory import V2InventoryItem, V2InventoryStockSnapshot

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
    intent = llm_service.parse_intent(user_message, db_session, history=chat_session.to_messages())
    
    # Execute stock transaction if applicable
    tx_reply = _execute_stock_transaction(intent, db_session, context, account, user_message)
    
    # Query inventory if needed
    query_result = _query_inventory_for_intent(intent, db_session, context)
    
    # Generate response with history context
    if tx_reply:
        reply = tx_reply
    elif query_result and intent.intent_type not in ("revenue_query", "sales_query", "alert_query"):
        response = llm_service.generate_response(
            query_result, user_message, history=chat_session.to_messages()
        )
        reply = response.content
    else:
        reply = _build_fallback_reply(intent, query_result)
    
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
        intent = llm_service.parse_intent(user_message, db_session, history=chat_session.to_messages())
        role = _get_employee_role(intent.intent_type)
        yield _sse_event("intent", {
            "intent_type": intent.intent_type,
            "item_name": intent.item_name,
            "quantity": intent.quantity,
            "confidence": intent.confidence,
            "employee": role,
            "session_id": session_id,
        })
        
        # 2. Execute stock transaction if applicable
        tx_reply = _execute_stock_transaction(intent, db_session, context, account, user_message)
        
        # 3. Query inventory
        query_result = _query_inventory_for_intent(intent, db_session, context)
        if query_result:
            yield _sse_event("inventory", {**query_result, "employee": role})
        
        # 4. Generate and stream response with history context
        reply_text = ""
        if tx_reply:
            reply_text = tx_reply
            for event in _stream_text(reply_text):
                yield event
        elif query_result and intent.intent_type not in ("revenue_query", "sales_query", "alert_query"):
            response = llm_service.generate_response(
                query_result, user_message, history=chat_session.to_messages()
            )
            reply_text = response.content
            for event in _stream_text(reply_text):
                yield event
        else:
            reply_text = _build_fallback_reply(intent, query_result)
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
    context,
) -> dict | None:
    """Query inventory or analytics based on parsed intent."""
    from sqlalchemy import select
    
    if intent.intent_type == "revenue_query":
        summary = get_revenue_summary(
            db_session,
            tenant_id=context.tenant_id,
            shop_id=context.shop_id,
            days=30,
        )
        return {
            "type": "revenue_summary",
            "total_revenue": summary.total_revenue,
            "total_cost": summary.total_cost,
            "gross_profit": summary.gross_profit,
            "transaction_count": summary.transaction_count,
            "items_sold": summary.items_sold,
        }
    
    if intent.intent_type == "sales_query":
        ranking = get_sales_ranking(
            db_session,
            tenant_id=context.tenant_id,
            shop_id=context.shop_id,
            days=30,
            limit=5,
        )
        return {
            "type": "sales_ranking",
            "ranking": [
                {
                    "rank": item.rank,
                    "item_name": item.item_name,
                    "total_sold": item.total_sold,
                    "total_revenue": item.total_revenue,
                }
                for item in ranking
            ],
        }
    
    if intent.intent_type == "alert_query":
        alerts = get_low_stock_alerts(
            db_session,
            tenant_id=context.tenant_id,
            shop_id=context.shop_id,
            limit=10,
        )
        return {
            "type": "low_stock_alerts",
            "alerts": [
                {
                    "item_name": alert.item_name,
                    "current_quantity": alert.current_quantity,
                    "threshold": alert.threshold,
                    "shortage": alert.shortage,
                    "unit": alert.unit,
                }
                for alert in alerts
            ],
            "count": len(alerts),
        }
    
    if intent.intent_type not in ("stock_query", "stock_in", "stock_out"):
        return None
    
    if not intent.item_name:
        return None
    
    # Find matching item
    stmt = (
        select(V2InventoryItem, V2InventoryStockSnapshot)
        .join(V2InventoryStockSnapshot, V2InventoryStockSnapshot.inventory_item_id == V2InventoryItem.inventory_item_id)
        .where(
            V2InventoryStockSnapshot.shop_id == context.shop_id,
        )
    )
    
    for item, snapshot in db_session.execute(stmt).all():
        if intent.item_name in item.name or item.name in intent.item_name:
            return {
                "type": "stock",
                "item_id": item.inventory_item_id,
                "item_name": item.name,
                "sku": item.sku,
                "quantity": float(snapshot.current_quantity) if snapshot.current_quantity else 0,
                "unit": item.default_unit or "个",
                "threshold": float(snapshot.low_stock_threshold) if snapshot.low_stock_threshold else None,
            }
    
    return None


def _execute_stock_transaction(
    intent,
    db_session: Session,
    context,
    account,
    user_message: str,
) -> str | None:
    """Execute stock in/out transaction based on intent.
    
    Returns a reply message if transaction was executed, None otherwise.
    """
    from sqlalchemy import select
    from decimal import Decimal
    from app.models.v2_conversation import V2ConversationSession
    from app.services.v2_conversation import create_v2_session
    
    if intent.intent_type not in ("stock_in", "stock_out"):
        return None
    
    if not intent.item_name or not intent.quantity:
        return None
    
    # Find matching item
    stmt = (
        select(V2InventoryItem, V2InventoryStockSnapshot)
        .join(V2InventoryStockSnapshot, V2InventoryStockSnapshot.inventory_item_id == V2InventoryItem.inventory_item_id)
        .where(
            V2InventoryStockSnapshot.shop_id == context.shop_id,
        )
    )
    
    matched = None
    for item, snapshot in db_session.execute(stmt).all():
        if intent.item_name in item.name or item.name in intent.item_name:
            matched = (item, snapshot)
            break
    
    if not matched:
        return None
    
    item, snapshot = matched
    
    try:
        if intent.intent_type == "stock_in":
            # Create/get conversation session for task run
            chat_session_id = f"chat_tx_{account.account_id}"
            session = db_session.scalar(
                select(V2ConversationSession).where(
                    V2ConversationSession.session_id == chat_session_id,
                    V2ConversationSession.tenant_id == context.tenant_id,
                    V2ConversationSession.shop_id == context.shop_id,
                )
            )
            if not session:
                session_result = create_v2_session(
                    db_session,
                    tenant_id=context.tenant_id,
                    shop_id=context.shop_id,
                    title="Chat Stock Transaction",
                    initiated_by_account_id=account.account_id,
                    session_type="chat",
                )
                session = db_session.scalar(
                    select(V2ConversationSession).where(
                        V2ConversationSession.session_id == session_result.session_id,
                    )
                )
            
            # Create task run for stock in
            msg_task = create_v2_message_and_task_run(
                db_session,
                tenant_id=context.tenant_id,
                shop_id=context.shop_id,
                session_id=session.session_id,
                actor_id=account.account_id,
                message_kind="stock_in",
                payload_json={
                    "item_name": item.name,
                    "quantity": intent.quantity,
                    "unit": item.default_unit or "个",
                    "price": float(snapshot.current_price) if snapshot.current_price else 0,
                },
                client_request_id=None,
                intent_type="inventory.stock_in",
            )
            if not msg_task:
                return None
            
            _, task_run = msg_task
            
            # Execute stock in
            result = commit_v2_inventory_stock_in(
                db_session,
                tenant_id=context.tenant_id,
                shop_id=context.shop_id,
                task_run_id=task_run.task_run_id,
                created_by_account_id=account.account_id,
                payload={
                    "item_id": item.inventory_item_id,
                    "item_name": item.name,
                    "quantity": intent.quantity,
                    "unit": item.default_unit or "个",
                    "price": float(snapshot.current_price) if snapshot.current_price else 0,
                },
            )
            db_session.commit()
            
            return (
                f"✅ 入库成功！\n"
                f"商品：{result.item.name}\n"
                f"入库数量：{intent.quantity} {item.default_unit or '个'}\n"
                f"当前库存：{float(result.snapshot.current_quantity)} {item.default_unit or '个'}"
            )
        
        elif intent.intent_type == "stock_out":
            current_qty = Decimal(snapshot.current_quantity) if snapshot.current_quantity else Decimal(0)
            
            if current_qty < Decimal(intent.quantity):
                return (
                    f"❌ 出库失败！库存不足。\n"
                    f"商品：{item.name}\n"
                    f"当前库存：{float(current_qty)} {item.default_unit or '个'}\n"
                    f"请求出库：{intent.quantity} {item.default_unit or '个'}"
                )
            
            result = commit_v2_inventory_stock_out(
                db_session,
                tenant_id=context.tenant_id,
                shop_id=context.shop_id,
                inventory_item_id=item.inventory_item_id,
                expected_quantity=current_qty,
                stock_out_quantity=Decimal(intent.quantity),
                reason="chat stock out",
                created_by_account_id=account.account_id,
            )
            db_session.commit()
            
            return (
                f"✅ 出库成功！\n"
                f"商品：{item.name}\n"
                f"出库数量：{intent.quantity} {item.default_unit or '个'}\n"
                f"当前库存：{float(result.snapshot.current_quantity)} {item.default_unit or '个'}"
            )
    
    except Exception as exc:
        db_session.rollback()
        return f"❌ 操作失败：{exc}"
    
    return None


def _build_fallback_reply(intent, query_result: dict | None = None) -> str:
    """Build fallback reply when no inventory data is found."""
    if intent.intent_type == "revenue_query":
        if query_result:
            return (
                f"过去30天营业概况：\n"
                f"总营业额：¥{query_result['total_revenue']:.2f}\n"
                f"总成本：¥{query_result['total_cost']:.2f}\n"
                f"毛利润：¥{query_result['gross_profit']:.2f}\n"
                f"交易笔数：{query_result['transaction_count']}笔\n"
                f"售出商品：{query_result['items_sold']:.0f}件"
            )
        return "暂无营收数据，请先进行销售出库操作。"
    
    if intent.intent_type == "sales_query":
        if query_result and query_result.get("ranking"):
            lines = ["过去30天热销排行："]
            for item in query_result["ranking"]:
                lines.append(f"{item['rank']}. {item['item_name']} - 售出{item['total_sold']:.0f}件 (¥{item['total_revenue']:.2f})")
            return "\n".join(lines)
        return "暂无销售数据，请先进行销售出库操作。"
    
    if intent.intent_type == "alert_query":
        if query_result and query_result.get("alerts"):
            lines = [f"⚠️ 发现{query_result['count']}个商品库存不足："]
            for alert in query_result["alerts"]:
                lines.append(
                    f"• {alert['item_name']}: 当前{alert['current_quantity']}{alert['unit']}，"
                    f"低于阈值{alert['threshold']}{alert['unit']}，缺{alert['shortage']}{alert['unit']}"
                )
            return "\n".join(lines)
        return "✅ 所有商品库存充足，暂无预警。"
    
    if intent.intent_type == "unknown":
        return "抱歉，我不理解您的意思。您可以问我：查库存、进货、出货、查营业额、热销排行、库存预警。"
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
