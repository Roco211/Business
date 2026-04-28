"""V2 Chat API with DeepSeek Main Agent orchestration and SSE streaming."""
from __future__ import annotations

import json
import uuid
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps.v2_context import (
    V2AuthenticatedAccount,
    V2ExecutionContext,
    require_v2_authenticated_account,
    require_v2_execution_context,
)
from app.contracts.v2.common import V2DataEnvelope
from app.db.session import get_db_session
from app.services.v2_chat_session import get_chat_session_store
from app.services.v2_main_agent import DeepSeekMainAgent, AgentPlan, ToolCall
from app.services.v2_llm import get_llm_service
from app.services.v2_conversation import create_v2_confirmation, create_v2_message_and_task_run
from app.services.v2_analytics import (
    get_revenue_summary,
    get_sales_ranking,
    get_low_stock_alerts,
)
from app.models.v2_inventory import V2InventoryItem, V2InventoryStockSnapshot

router = APIRouter(prefix="/api/v2", tags=["v2-chat"])


# ───────────────────────────────────────────────
# 1. Non-streaming endpoint (DeepSeek Main Agent)
# ───────────────────────────────────────────────

@router.post("/chat", response_model=V2DataEnvelope[dict])
def chat_v2(
    payload: dict,
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    db_session: Session = Depends(get_db_session),
) -> V2DataEnvelope[dict]:
    """Non-streaming chat endpoint with DeepSeek Main Agent orchestration."""
    chat_input = _normalize_chat_input(payload)
    user_message = chat_input["message"]
    input_type = chat_input["input_type"]
    source = chat_input["source"]
    session_id = payload.get("session_id")

    # Get or create chat session
    session_store = get_chat_session_store()
    session_id, chat_session = session_store.get_or_create(
        session_id=session_id,
        account_id=account.account_id,
        shop_id=context.shop_id,
    )
    chat_session.add_turn("user", user_message)

    # DeepSeek Main Agent: plan + execute + synthesize
    main_agent = _create_main_agent()
    plan = main_agent.plan(user_message, db_session, history=chat_session.to_messages())

    # Execute planned tools
    tool_results = _execute_plan(plan, db_session, context, account, user_message)

    # Synthesize response
    agent_response = main_agent.synthesize(
        user_message=user_message,
        plan=plan,
        tool_results=tool_results,
        history=chat_session.to_messages(),
    )

    chat_session.add_turn("assistant", agent_response.content)

    return V2DataEnvelope(
        data={
            "message_id": str(uuid.uuid4()),
            "reply": agent_response.content,
            "intent": agent_response.intent_type,
            "employee": agent_response.employee_role,
            "confidence": agent_response.confidence,
            "session_id": session_id,
            "input_type": input_type,
            "source": source,
            "tool_results": agent_response.tool_results,
        }
    )


# ───────────────────────────────────────────────
# 2. SSE Streaming endpoint (DeepSeek Main Agent)
# ───────────────────────────────────────────────

@router.post("/chat/stream")
def chat_stream_v2(
    request: Request,
    payload: dict,
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    db_session: Session = Depends(get_db_session),
) -> StreamingResponse:
    """SSE streaming chat endpoint with DeepSeek Main Agent orchestration."""
    chat_input = _normalize_chat_input(payload)
    user_message = chat_input["message"]
    input_type = chat_input["input_type"]
    source = chat_input["source"]
    session_id = payload.get("session_id")

    session_store = get_chat_session_store()
    session_id, chat_session = session_store.get_or_create(
        session_id=session_id,
        account_id=account.account_id,
        shop_id=context.shop_id,
    )
    chat_session.add_turn("user", user_message)

    async def event_generator() -> AsyncGenerator[str, None]:
        main_agent = _create_main_agent()

        # 1. Planning phase: DeepSeek understands intent
        plan = main_agent.plan(user_message, db_session, history=chat_session.to_messages())
        yield _sse_event("intent", {
            "intent_type": plan.intent_type,
            "employee": plan.employee_role,
            "needs_confirmation": plan.needs_confirmation,
            "tools": [t.tool_name for t in plan.tool_calls],
            "session_id": session_id,
            "input_type": input_type,
            "source": source,
        })

        # 2. Tool execution phase
        tool_results = _execute_plan(plan, db_session, context, account, user_message)
        for result in tool_results:
            yield _sse_event("tool_result", {
                "type": result.get("type"),
                "employee": plan.employee_role,
            })

        # 3. Synthesis phase: DeepSeek synthesizes final reply
        agent_response = main_agent.synthesize(
            user_message=user_message,
            plan=plan,
            tool_results=tool_results,
            history=chat_session.to_messages(),
        )

        # Stream the synthesized response
        for event in _stream_text(agent_response.content):
            yield event

        chat_session.add_turn("assistant", agent_response.content)

        # 4. Completion
        yield _sse_event("done", {
            "message_id": str(uuid.uuid4()),
            "employee": agent_response.employee_role,
            "session_id": session_id,
            "input_type": input_type,
            "source": source,
            "confidence": agent_response.confidence,
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


def _normalize_chat_input(payload: dict) -> dict[str, str | None]:
    input_type = str(payload.get("input_type") or "text").strip().lower()
    source = payload.get("source")
    source = str(source).strip() if source is not None else None
    if input_type not in {"text", "voice_text"}:
        raise HTTPException(status_code=422, detail="unsupported chat input_type")

    user_message = str(payload.get("message") or "").strip()
    if not user_message:
        raise HTTPException(status_code=422, detail="message is required")

    if input_type == "voice_text":
        source = source or "client_asr"
        if source != "client_asr":
            raise HTTPException(status_code=422, detail="voice_text requires source=client_asr")
    return {"message": user_message, "input_type": input_type, "source": source}


# ───────────────────────────────────────────────
# 3. Tool Execution Engine
# ───────────────────────────────────────────────

def _create_main_agent() -> DeepSeekMainAgent:
    """Create a Main Agent bound to the currently configured real LLM service."""
    return DeepSeekMainAgent(llm_service=get_llm_service())


def _execute_plan(
    plan: AgentPlan,
    db_session: Session,
    context,
    account,
    user_message: str,
) -> list[dict]:
    """Execute all planned tool calls and return results."""
    results: list[dict] = []

    for tool_call in plan.tool_calls:
        result = _execute_tool(tool_call, db_session, context, account, user_message)
        if result:
            results.append(result)

    # Handle write operations (stock_in/stock_out) that need confirmation
    if plan.intent_type in ("stock_in", "stock_out") and plan.tool_calls:
        tx_result = _execute_stock_transaction_from_plan(plan, db_session, context, account, user_message)
        if tx_result:
            results.append(tx_result)

    return results


def _execute_tool(
    tool_call: ToolCall,
    db_session: Session,
    context,
    account,
    user_message: str,
) -> dict | None:
    """Execute a single tool call."""
    tool_name = tool_call.tool_name
    params = tool_call.parameters

    if tool_name == "query_inventory":
        return _tool_query_inventory(params, db_session, context)
    if tool_name == "query_revenue":
        return _tool_query_revenue(params, db_session, context)
    if tool_name == "query_sales_ranking":
        return _tool_query_sales_ranking(params, db_session, context)
    if tool_name == "query_low_stock_alerts":
        return _tool_query_low_stock_alerts(params, db_session, context)
    if tool_name in ("draft_stock_in", "draft_stock_out"):
        # Write operations handled separately for confirmation-first
        return None
    if tool_name == "general_chat":
        return None

    logger = __import__("logging").getLogger(__name__)
    logger.warning("Unknown tool: %s", tool_name)
    return None


def _tool_query_inventory(params: dict, db_session: Session, context) -> dict | None:
    from sqlalchemy import select
    item_name = params.get("item_name")
    if not item_name:
        return None

    stmt = (
        select(V2InventoryItem, V2InventoryStockSnapshot)
        .join(V2InventoryStockSnapshot, V2InventoryStockSnapshot.inventory_item_id == V2InventoryItem.inventory_item_id)
        .where(V2InventoryStockSnapshot.shop_id == context.shop_id)
    )
    for item, snapshot in db_session.execute(stmt).all():
        if item_name in item.name or item.name in item_name:
            return {
                "type": "stock",
                "item_id": item.inventory_item_id,
                "item_name": item.name,
                "sku": item.sku,
                "quantity": float(snapshot.current_quantity) if snapshot.current_quantity else 0,
                "unit": item.default_unit or "个",
                "threshold": float(snapshot.low_stock_threshold) if snapshot.low_stock_threshold else None,
            }
    return {"type": "stock_not_found", "item_name": item_name}


def _tool_query_revenue(params: dict, db_session: Session, context) -> dict:
    days = params.get("days", 30)
    summary = get_revenue_summary(db_session, tenant_id=context.tenant_id, shop_id=context.shop_id, days=days)
    return {
        "type": "revenue_summary",
        "total_revenue": summary.total_revenue,
        "total_cost": summary.total_cost,
        "gross_profit": summary.gross_profit,
        "transaction_count": summary.transaction_count,
        "items_sold": summary.items_sold,
        "days": days,
    }


def _tool_query_sales_ranking(params: dict, db_session: Session, context) -> dict:
    days = params.get("days", 30)
    limit = params.get("limit", 5)
    ranking = get_sales_ranking(db_session, tenant_id=context.tenant_id, shop_id=context.shop_id, days=days, limit=limit)
    return {
        "type": "sales_ranking",
        "ranking": [
            {"rank": item.rank, "item_name": item.item_name, "total_sold": item.total_sold, "total_revenue": item.total_revenue}
            for item in ranking
        ],
        "days": days,
    }


def _tool_query_low_stock_alerts(params: dict, db_session: Session, context) -> dict:
    limit = params.get("limit", 10)
    alerts = get_low_stock_alerts(db_session, tenant_id=context.tenant_id, shop_id=context.shop_id, limit=limit)
    return {
        "type": "low_stock_alerts",
        "alerts": [
            {"item_name": a.item_name, "current_quantity": a.current_quantity, "threshold": a.threshold, "shortage": a.shortage, "unit": a.unit}
            for a in alerts
        ],
        "count": len(alerts),
    }


def _execute_stock_transaction_from_plan(
    plan: AgentPlan,
    db_session: Session,
    context,
    account,
    user_message: str,
) -> dict | None:
    """Create pending confirmation for stock writes (confirmation-first)."""
    from decimal import Decimal
    from sqlalchemy import select
    from app.models.v2_conversation import V2ConversationSession
    from app.services.v2_conversation import create_v2_session

    # Find the draft tool call
    draft_tool = None
    for tc in plan.tool_calls:
        if tc.tool_name in ("draft_stock_in", "draft_stock_out"):
            draft_tool = tc
            break
    if not draft_tool:
        return None

    item_name = draft_tool.parameters.get("item_name")
    quantity = draft_tool.parameters.get("quantity")
    if not item_name or not quantity:
        return None

    stmt = (
        select(V2InventoryItem, V2InventoryStockSnapshot)
        .join(V2InventoryStockSnapshot, V2InventoryStockSnapshot.inventory_item_id == V2InventoryItem.inventory_item_id)
        .where(
            V2InventoryItem.tenant_id == context.tenant_id,
            V2InventoryStockSnapshot.tenant_id == context.tenant_id,
            V2InventoryStockSnapshot.shop_id == context.shop_id,
        )
    )
    matched = None
    for item, snapshot in db_session.execute(stmt).all():
        if item_name in item.name or item.name in item_name:
            matched = (item, snapshot)
            break
    if not matched:
        return {"type": "stock_tx_error", "error": f"未找到商品: {item_name}"}

    item, snapshot = matched
    current_qty = Decimal(snapshot.current_quantity) if snapshot.current_quantity else Decimal(0)
    qty = Decimal(str(quantity))

    intent_type = plan.intent_type  # "stock_in" or "stock_out"

    if intent_type == "stock_out" and current_qty < qty:
        return {
            "type": "stock_tx_error",
            "error": "库存不足",
            "item_name": item.name,
            "current_quantity": float(current_qty),
            "requested_quantity": int(quantity),
            "unit": item.default_unit or "个",
        }

    try:
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
        if session is None:
            return {"type": "stock_tx_error", "error": "创建会话失败"}

        if intent_type == "stock_in":
            confirmation_type = "inventory.stock_in"
            message_kind = "stock_in"
            draft_payload = {
                "item_id": item.inventory_item_id,
                "item_name": item.name,
                "quantity": int(quantity),
                "unit": item.default_unit or "个",
                "price": float(snapshot.current_price) if snapshot.current_price else 0,
                "source_text": user_message,
            }
        else:
            confirmation_type = "inventory.stock_out"
            message_kind = "stock_out"
            draft_payload = {
                "inventory_item_id": item.inventory_item_id,
                "item_name": item.name,
                "expected_quantity": float(current_qty),
                "stock_out_quantity": int(quantity),
                "unit": item.default_unit or "个",
                "reason": "chat stock out",
                "source_text": user_message,
            }

        msg_task = create_v2_message_and_task_run(
            db_session,
            tenant_id=context.tenant_id,
            shop_id=context.shop_id,
            session_id=session.session_id,
            actor_id=account.account_id,
            message_kind=message_kind,
            payload_json=draft_payload,
            client_request_id=None,
            intent_type=confirmation_type,
        )
        if not msg_task:
            return {"type": "stock_tx_error", "error": "创建任务失败"}

        _, task_run = msg_task
        confirmation = create_v2_confirmation(
            db_session,
            tenant_id=context.tenant_id,
            shop_id=context.shop_id,
            task_run_id=task_run.task_run_id,
            confirmation_type=confirmation_type,
            draft_payload=draft_payload,
        )

        action_label = "入库" if intent_type == "stock_in" else "出库"
        return {
            "type": "stock_tx_pending",
            "action": action_label,
            "item_name": item.name,
            "quantity": int(quantity),
            "unit": item.default_unit or "个",
            "confirmation_id": confirmation.confirmation_id,
            "current_quantity": float(current_qty),
        }

    except Exception as exc:
        db_session.rollback()
        return {"type": "stock_tx_error", "error": str(exc)}


# ───────────────────────────────────────────────
# 4. SSE Helpers
# ───────────────────────────────────────────────

def _sse_event(event_type: str, data: dict) -> str:
    """Format SSE event."""
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _stream_text(text: str, chunk_size: int = 3):
    """Stream text in chunks respecting character boundaries."""
    for i in range(0, len(text), chunk_size):
        chunk = text[i:i + chunk_size]
        yield _sse_event("token", {"token": chunk})
