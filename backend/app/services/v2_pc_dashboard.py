from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    V2Account,
    V2Confirmation,
    V2InventoryItem,
    V2InventoryLedgerEvent,
    V2InventoryStockSnapshot,
    V2Shop,
    V2Tenant,
)
from app.services.v2_analytics import get_daily_revenue_series, get_low_stock_alerts, get_revenue_summary, get_sales_ranking


def _to_float(value: Decimal | int | float | None) -> float:
    if value is None:
        return 0.0
    return float(value)


def _status_for_count(count: int) -> str:
    if count > 0:
        return "attention_needed"
    return "ready"


def _get_pending_confirmation_count(db_session: Session, *, tenant_id: str, shop_id: str) -> int:
    return int(
        db_session.scalar(
            select(func.count(V2Confirmation.confirmation_id)).where(
                V2Confirmation.tenant_id == tenant_id,
                V2Confirmation.shop_id == shop_id,
                V2Confirmation.status == "pending",
            )
        )
        or 0
    )


def _get_recent_activity_count(db_session: Session, *, tenant_id: str, shop_id: str) -> int:
    return int(
        db_session.scalar(
            select(func.count(V2InventoryLedgerEvent.event_id))
            .join(
                V2InventoryItem,
                V2InventoryItem.inventory_item_id == V2InventoryLedgerEvent.inventory_item_id,
            )
            .where(
                V2InventoryLedgerEvent.tenant_id == tenant_id,
                V2InventoryLedgerEvent.shop_id == shop_id,
                V2InventoryItem.tenant_id == tenant_id,
                V2InventoryItem.status == "active",
            )
        )
        or 0
    )


def _get_active_item_count(db_session: Session, *, tenant_id: str) -> int:
    return int(
        db_session.scalar(
            select(func.count(V2InventoryItem.inventory_item_id)).where(
                V2InventoryItem.tenant_id == tenant_id,
                V2InventoryItem.status == "active",
            )
        )
        or 0
    )


def _build_kpis(*, revenue, low_stock_count: int, pending_confirmation_count: int) -> list[dict[str, object]]:
    return [
        {
            "key": "today_sales_amount",
            "label": "今日销售额",
            "value": _to_float(revenue.total_revenue),
            "unit": "元",
            "trend_label": "基于库存出库流水",
            "status": "ready",
        },
        {
            "key": "today_sales_transactions",
            "label": "今日销售笔数",
            "value": int(revenue.transaction_count),
            "unit": "笔",
            "trend_label": "当前版本统计销售出库流水",
            "status": "ready",
        },
        {
            "key": "low_stock_count",
            "label": "低库存商品",
            "value": low_stock_count,
            "unit": "个",
            "trend_label": "由库存风控专员实时检测",
            "status": _status_for_count(low_stock_count),
        },
        {
            "key": "pending_confirmation_count",
            "label": "待确认任务",
            "value": pending_confirmation_count,
            "unit": "个",
            "trend_label": "AI生成的高风险操作需人工确认",
            "status": _status_for_count(pending_confirmation_count),
        },
    ]


def _build_ai_employees(
    *,
    revenue,
    low_stock_count: int,
    pending_confirmation_count: int,
    active_item_count: int,
    recent_activity_count: int,
) -> list[dict[str, object]]:
    return [
        {
            "key": "operations_coordinator",
            "name": "AI运营协调官",
            "description": "统筹AI指令分发、待确认任务和今日重点事项",
            "status": "attention_needed" if pending_confirmation_count else "working",
            "metrics": [{"label": "待确认任务", "value": pending_confirmation_count, "unit": "个"}],
            "primary_action": {"label": "查看任务", "route": "/tasks"},
        },
        {
            "key": "business_data_analyst",
            "name": "经营数据分析员",
            "description": "分析销售额、销售笔数、排行和趋势",
            "status": "working",
            "metrics": [
                {"label": "今日销售额", "value": _to_float(revenue.total_revenue), "unit": "元"},
                {"label": "今日销售笔数", "value": int(revenue.transaction_count), "unit": "笔"},
            ],
            "primary_action": {"label": "查看经营数据", "route": "/dashboard"},
        },
        {
            "key": "inventory_risk_controller",
            "name": "库存风控专员",
            "description": "监控低库存、库存变化和补货风险",
            "status": "attention_needed" if low_stock_count else "working",
            "metrics": [{"label": "低库存商品", "value": low_stock_count, "unit": "个"}],
            "primary_action": {"label": "查看库存预警", "route": "/inventory?filter=low-stock"},
        },
        {
            "key": "product_catalog_manager",
            "name": "商品档案管理员",
            "description": "维护商品档案、SKU、单位和审计入口",
            "status": "working",
            "metrics": [{"label": "在售商品", "value": active_item_count, "unit": "个"}],
            "primary_action": {"label": "管理商品", "route": "/products"},
        },
        {
            "key": "business_strategy_advisor",
            "name": "经营策略顾问",
            "description": "基于库存与流水生成可解释经营建议",
            "status": "working" if recent_activity_count else "idle",
            "metrics": [{"label": "今日动态", "value": recent_activity_count, "unit": "条"}],
            "primary_action": {"label": "查看建议", "route": "/dashboard#suggestions"},
        },
    ]


def _build_top_priorities(*, low_stock_count: int, pending_confirmation_count: int, revenue) -> list[dict[str, object]]:
    priorities: list[dict[str, object]] = []
    if pending_confirmation_count:
        priorities.append(
            {
                "id": "priority_pending_confirmations",
                "title": "处理待确认AI任务",
                "reason": f"当前有{pending_confirmation_count}个AI生成任务等待人工确认",
                "severity": "high",
                "evidence": ["AI运营协调官检测到待确认任务", "库存写操作必须人工确认后落账"],
                "action": {"label": "查看任务", "route": "/tasks"},
            }
        )
    if low_stock_count:
        priorities.append(
            {
                "id": "priority_low_stock",
                "title": "优先处理低库存商品",
                "reason": f"当前有{low_stock_count}个商品低于安全库存",
                "severity": "high",
                "evidence": ["库存风控专员检测到库存低于阈值"],
                "action": {"label": "查看库存预警", "route": "/inventory?filter=low-stock"},
            }
        )
    if revenue.transaction_count == 0:
        priorities.append(
            {
                "id": "priority_no_sales",
                "title": "今天还没有销售流水",
                "reason": "完成一次销售出库后，经营数据会自动更新",
                "severity": "medium",
                "evidence": ["经营数据分析员未检测到今日销售出库流水"],
                "action": {"label": "去做出库", "route": "/inventory?action=stock-out"},
            }
        )
    if not priorities:
        priorities.append(
            {
                "id": "priority_all_good",
                "title": "经营状态正常",
                "reason": "暂无待确认任务或库存风险",
                "severity": "low",
                "evidence": ["AI运营协调官未发现高优先级事项"],
                "action": {"label": "查看工作台", "route": "/dashboard"},
            }
        )
    return priorities[:3]


def _build_suggestions(*, low_stock_count: int, pending_confirmation_count: int, revenue) -> list[dict[str, object]]:
    suggestions: list[dict[str, object]] = []
    if low_stock_count:
        suggestions.append(
            {
                "id": "suggestion_low_stock_replenishment",
                "type": "inventory_replenishment",
                "title": "建议生成补货清单",
                "summary": "有商品低于安全库存，建议优先检查并补货",
                "evidence": [f"低库存商品数: {low_stock_count}"],
                "risk": "补货建议基于当前库存阈值，未包含供应商交期和真实采购成本",
                "confidence": "medium",
                "requires_confirmation": True,
                "action": {"label": "查看低库存", "route": "/inventory?filter=low-stock"},
            }
        )
    if pending_confirmation_count:
        suggestions.append(
            {
                "id": "suggestion_review_ai_tasks",
                "type": "confirmation_review",
                "title": "建议先审批待确认任务",
                "summary": "AI已生成业务草稿，审批后才会写入库存事实账本",
                "evidence": [f"待确认任务数: {pending_confirmation_count}"],
                "risk": "忽略待确认任务会导致库存流水未及时落账",
                "confidence": "high",
                "requires_confirmation": False,
                "action": {"label": "处理待确认", "route": "/tasks"},
            }
        )
    if not suggestions:
        suggestions.append(
            {
                "id": "suggestion_keep_monitoring",
                "type": "business_monitoring",
                "title": "继续关注今日销售与库存",
                "summary": "当前暂无高风险事项，可继续通过AI运营协调官查询经营情况",
                "evidence": [f"今日销售笔数: {int(revenue.transaction_count)}"],
                "risk": "当前建议基于商品、库存和销售流水，未包含客户和订单模块",
                "confidence": "medium",
                "requires_confirmation": False,
                "action": {"label": "询问AI运营协调官", "route": "/ai"},
            }
        )
    return suggestions[:3]


def _build_activities(*, low_stock_count: int, pending_confirmation_count: int, revenue) -> list[dict[str, object]]:
    activities: list[dict[str, object]] = []
    if revenue.transaction_count:
        activities.append(
            {
                "id": "activity_sales_summary",
                "time_label": "今日",
                "actor_name": "经营数据分析员",
                "summary": f"记录到{int(revenue.transaction_count)}笔销售出库流水",
                "impact": f"销售额{_to_float(revenue.total_revenue):.2f}元",
                "route": "/dashboard",
            }
        )
    if low_stock_count:
        activities.append(
            {
                "id": "activity_low_stock",
                "time_label": "今日",
                "actor_name": "库存风控专员",
                "summary": "检测到低库存商品",
                "impact": f"需要关注{low_stock_count}个商品",
                "route": "/inventory?filter=low-stock",
            }
        )
    if pending_confirmation_count:
        activities.append(
            {
                "id": "activity_pending_confirmation",
                "time_label": "今日",
                "actor_name": "AI运营协调官",
                "summary": "发现待确认AI任务",
                "impact": f"{pending_confirmation_count}个任务等待处理",
                "route": "/tasks",
            }
        )
    if not activities:
        activities.append(
            {
                "id": "activity_empty",
                "time_label": "今日",
                "actor_name": "AI运营协调官",
                "summary": "暂无新的经营动态",
                "impact": "完成入库、出库或AI任务后这里会自动更新",
                "route": "/dashboard",
            }
        )
    return activities[:5]


def _build_todos(*, low_stock_count: int, pending_confirmation_count: int) -> list[dict[str, object]]:
    return [
        {
            "key": "pending_confirmations",
            "title": "待确认AI任务",
            "count": pending_confirmation_count,
            "severity": "high" if pending_confirmation_count else "low",
            "route": "/tasks",
        },
        {
            "key": "low_stock_items",
            "title": "低库存商品",
            "count": low_stock_count,
            "severity": "high" if low_stock_count else "low",
            "route": "/inventory?filter=low-stock",
        },
    ]


def get_pc_dashboard_overview(
    db_session: Session,
    *,
    account_id: str,
    tenant_id: str,
    shop_id: str,
) -> dict[str, object]:
    account = db_session.get(V2Account, account_id)
    tenant = db_session.get(V2Tenant, tenant_id)
    shop = db_session.get(V2Shop, shop_id)

    revenue = get_revenue_summary(db_session, tenant_id=tenant_id, shop_id=shop_id, days=1)
    ranking = get_sales_ranking(db_session, tenant_id=tenant_id, shop_id=shop_id, days=7, limit=5)
    low_stock_alerts = get_low_stock_alerts(db_session, tenant_id=tenant_id, shop_id=shop_id, limit=20)
    daily_revenue_series = get_daily_revenue_series(db_session, tenant_id=tenant_id, shop_id=shop_id, days=7)
    pending_confirmation_count = _get_pending_confirmation_count(db_session, tenant_id=tenant_id, shop_id=shop_id)
    low_stock_count = len(low_stock_alerts)
    active_item_count = _get_active_item_count(db_session, tenant_id=tenant_id)
    recent_activity_count = _get_recent_activity_count(db_session, tenant_id=tenant_id, shop_id=shop_id)

    return {
        "store": {
            "tenant_id": tenant_id,
            "tenant_name": tenant.name if tenant is not None else "当前租户",
            "shop_id": shop_id,
            "shop_name": shop.name if shop is not None else "当前门店",
            "plan_label": "本地演示版" if tenant is None or tenant.plan_code == "trial" else tenant.plan_code,
        },
        "user": {
            "account_id": account_id,
            "display_name": account.display_name if account is not None else "当前用户",
            "role_label": "店主",
        },
        "kpis": _build_kpis(
            revenue=revenue,
            low_stock_count=low_stock_count,
            pending_confirmation_count=pending_confirmation_count,
        ),
        "ai_employees": _build_ai_employees(
            revenue=revenue,
            low_stock_count=low_stock_count,
            pending_confirmation_count=pending_confirmation_count,
            active_item_count=active_item_count,
            recent_activity_count=recent_activity_count,
        ),
        "top_priorities": _build_top_priorities(
            low_stock_count=low_stock_count,
            pending_confirmation_count=pending_confirmation_count,
            revenue=revenue,
        ),
        "suggestions": _build_suggestions(
            low_stock_count=low_stock_count,
            pending_confirmation_count=pending_confirmation_count,
            revenue=revenue,
        ),
        "activities": _build_activities(
            low_stock_count=low_stock_count,
            pending_confirmation_count=pending_confirmation_count,
            revenue=revenue,
        ),
        "todos": _build_todos(
            low_stock_count=low_stock_count,
            pending_confirmation_count=pending_confirmation_count,
        ),
        "notifications": {"unread_count": 0},
        "sales_ranking": [
            {
                "rank": item.rank,
                "item_id": item.item_id,
                "item_name": item.item_name,
                "sku": item.sku,
                "total_sold": item.total_sold,
                "total_revenue": item.total_revenue,
                "avg_price": item.avg_price,
            }
            for item in ranking
        ],
        "low_stock": {
            "count": low_stock_count,
            "items": [
                {
                    "item_id": alert.item_id,
                    "item_name": alert.item_name,
                    "sku": alert.sku,
                    "current_quantity": alert.current_quantity,
                    "threshold": alert.threshold,
                    "shortage": alert.shortage,
                    "unit": alert.unit,
                }
                for alert in low_stock_alerts
            ],
        },
        "daily_revenue_series": daily_revenue_series,
        "coming_soon_modules": [
            {"key": "customers", "label": "客户管理"},
            {"key": "marketing", "label": "营销中心"},
            {"key": "finance", "label": "财务对账"},
        ],
    }
