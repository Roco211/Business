from __future__ import annotations

from datetime import datetime, timedelta
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
    V2TaskRun,
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


def _employee_key_for_intent(intent_type: str | None) -> str:
    normalized = (intent_type or "").lower()
    if normalized.startswith("sales") or "revenue" in normalized or "sales" in normalized:
        return "business_data_analyst"
    if normalized.startswith("purchase"):
        return "purchase_replenishment_specialist"
    if "inventory" in normalized or normalized in {"stock_in", "stock_out"} or "stock" in normalized:
        return "inventory_risk_controller"
    if "catalog" in normalized or "product" in normalized or "item" in normalized:
        return "product_catalog_manager"
    return "operations_coordinator"


def _status_label(status: str, *, pending_count: int, failed_count: int) -> str:
    if pending_count > 0 or status == "attention_needed":
        return "等待老板确认"
    if failed_count > 0 or status == "error":
        return "需要处理异常"
    if status == "working":
        return "员工工作中"
    if status == "ready":
        return "已待命"
    return "空闲待命"


def _build_employee_runtime_stats(db_session: Session, *, tenant_id: str, shop_id: str) -> dict[str, dict[str, object]]:
    stats: dict[str, dict[str, object]] = {}
    task_runs = list(
        db_session.scalars(
            select(V2TaskRun)
            .where(
                V2TaskRun.tenant_id == tenant_id,
                V2TaskRun.shop_id == shop_id,
            )
            .order_by(V2TaskRun.updated_at.desc(), V2TaskRun.created_at.desc())
        )
    )
    pending_confirmations = list(
        db_session.scalars(
            select(V2Confirmation).where(
                V2Confirmation.tenant_id == tenant_id,
                V2Confirmation.shop_id == shop_id,
                V2Confirmation.status == "pending",
            )
        )
    )
    task_key_by_id = {task.task_run_id: _employee_key_for_intent(task.intent_type) for task in task_runs}

    def ensure(key: str) -> dict[str, object]:
        return stats.setdefault(
            key,
            {
                "today_task_count": 0,
                "pending_confirmation_count": 0,
                "completed_task_count": 0,
                "failed_task_count": 0,
                "last_activity_label": "暂无新任务",
            },
        )

    for task in task_runs:
        key = task_key_by_id[task.task_run_id]
        entry = ensure(key)
        entry["today_task_count"] = int(entry["today_task_count"]) + 1
        if task.status in {"completed", "approved", "committed"} or task.completed_at is not None:
            entry["completed_task_count"] = int(entry["completed_task_count"]) + 1
        if task.status in {"failed", "error"} or task.error_code:
            entry["failed_task_count"] = int(entry["failed_task_count"]) + 1
        if entry["last_activity_label"] == "暂无新任务" and task.result_summary:
            entry["last_activity_label"] = task.result_summary

    coordinator = ensure("operations_coordinator")
    if task_runs:
        coordinator["today_task_count"] = len(task_runs)
        coordinator["completed_task_count"] = sum(
            1 for task in task_runs if task.status in {"completed", "approved", "committed"} or task.completed_at is not None
        )
        coordinator["failed_task_count"] = sum(1 for task in task_runs if task.status in {"failed", "error"} or task.error_code)
        first_summary = next((task.result_summary for task in task_runs if task.result_summary), None)
        if first_summary:
            coordinator["last_activity_label"] = first_summary
    for confirmation in pending_confirmations:
        key = task_key_by_id.get(confirmation.task_run_id, "operations_coordinator")
        ensure(key)["pending_confirmation_count"] = int(ensure(key)["pending_confirmation_count"]) + 1
        coordinator["pending_confirmation_count"] = int(coordinator["pending_confirmation_count"]) + 1

    if pending_confirmations and coordinator["last_activity_label"] == "暂无新任务":
        coordinator["last_activity_label"] = "有AI草稿等待确认"
    return stats


def _merge_employee_runtime(employee: dict[str, object], stats: dict[str, dict[str, object]]) -> dict[str, object]:
    key = str(employee["key"])
    runtime = stats.get(
        key,
        {
            "today_task_count": 0,
            "pending_confirmation_count": 0,
            "completed_task_count": 0,
            "failed_task_count": 0,
            "last_activity_label": "暂无新任务",
        },
    )
    pending_count = int(runtime["pending_confirmation_count"])
    failed_count = int(runtime["failed_task_count"])
    status = "attention_needed" if pending_count else "error" if failed_count else str(employee.get("status", "idle"))
    metrics = list(employee.get("metrics", []))
    metrics = [
        {"label": "今日任务", "value": int(runtime["today_task_count"]), "unit": "个"},
        {"label": "待确认", "value": pending_count, "unit": "个"},
        {"label": "已完成", "value": int(runtime["completed_task_count"]), "unit": "个"},
        *metrics,
    ]
    return {
        **employee,
        "status": status,
        "status_label": _status_label(status, pending_count=pending_count, failed_count=failed_count),
        "today_task_count": int(runtime["today_task_count"]),
        "pending_confirmation_count": pending_count,
        "completed_task_count": int(runtime["completed_task_count"]),
        "failed_task_count": failed_count,
        "last_activity_label": str(runtime["last_activity_label"]),
        "metrics": metrics,
    }


def _build_ai_employees(
    *,
    revenue,
    low_stock_count: int,
    pending_confirmation_count: int,
    active_item_count: int,
    recent_activity_count: int,
    employee_stats: dict[str, dict[str, object]],
) -> list[dict[str, object]]:
    employees = [
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
    return [_merge_employee_runtime(employee, employee_stats) for employee in employees]


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


def _build_notifications(
    *,
    pending_confirmation_count: int,
    low_stock_alerts: list[object],
    daily_advisor_report: dict[str, object],
) -> dict[str, object]:
    items: list[dict[str, object]] = []
    now = datetime.utcnow().replace(microsecond=0).isoformat()

    if pending_confirmation_count:
        items.append(
            {
                "id": "notification_pending_confirmations",
                "type": "confirmation",
                "title": "有AI任务等待确认",
                "summary": f"当前有{pending_confirmation_count}个AI草稿等待老板确认，确认前不会改库存、销售或财务事实。",
                "severity": "high",
                "source_employee": "AI运营协调官",
                "route": "/tasks",
                "action_label": "去确认",
                "evidence": [f"待确认任务数: {pending_confirmation_count}", "所有高风险AI操作保持 confirmation-first"],
                "created_at": now,
                "read": False,
            }
        )

    low_stock_count = len(low_stock_alerts)
    if low_stock_count:
        first_names = [str(getattr(alert, "item_name", "低库存商品")) for alert in low_stock_alerts[:3]]
        items.append(
            {
                "id": "notification_low_stock",
                "type": "inventory_risk",
                "title": "库存风控专员发现低库存",
                "summary": f"当前有{low_stock_count}个商品低于安全库存：{'、'.join(first_names)}。",
                "severity": "high",
                "source_employee": "库存风控专员",
                "route": "/inventory?filter=low-stock",
                "action_label": "看库存",
                "evidence": [f"低库存商品数: {low_stock_count}", *first_names],
                "created_at": now,
                "read": False,
            }
        )

    business_health = str(daily_advisor_report.get("business_health", "quiet"))
    if not items and business_health in {"healthy", "quiet"}:
        items.append(
            {
                "id": "notification_daily_report",
                "type": "daily_advisor",
                "title": "今日经营日报已生成",
                "summary": str(daily_advisor_report.get("summary", "经营策略顾问已完成今日经营复盘。")),
                "severity": "low",
                "source_employee": "经营策略顾问",
                "route": "/daily-report",
                "action_label": "看日报",
                "evidence": ["来源: pc-dashboard-overview"],
                "created_at": now,
                "read": False,
            }
        )

    unread_count = sum(1 for item in items if not item.get("read"))
    attention_count = sum(1 for item in items if item.get("severity") in {"high", "medium"})
    return {
        "unread_count": unread_count,
        "attention_count": attention_count,
        "generated_at": now,
        "items": items[:8],
    }


def _build_daily_advisor_report(
    *,
    revenue,
    low_stock_count: int,
    pending_confirmation_count: int,
    active_item_count: int,
    recent_activity_count: int,
    top_priorities: list[dict[str, object]],
    suggestions: list[dict[str, object]],
) -> dict[str, object]:
    sales_amount = _to_float(revenue.total_revenue)
    sales_count = int(revenue.transaction_count)
    items_sold = int(getattr(revenue, "items_sold", 0) or 0)
    business_health = "attention_needed" if pending_confirmation_count or low_stock_count else "healthy" if sales_count else "quiet"

    sections = [
        {
            "key": "sales",
            "title": "销售概况",
            "content": f"今日销售额{sales_amount:.2f}元，记录到{sales_count}笔销售，售出{items_sold}件商品。",
            "metrics": {
                "total_revenue": round(sales_amount, 2),
                "transaction_count": sales_count,
                "items_sold": items_sold,
            },
            "employee": "经营数据分析员",
        },
        {
            "key": "inventory",
            "title": "库存风险",
            "content": f"库存风控专员检测到{low_stock_count}个低库存商品。" if low_stock_count else "库存风控专员暂未发现低库存风险。",
            "metrics": {"low_stock_count": low_stock_count, "active_item_count": active_item_count},
            "employee": "库存风控专员",
        },
        {
            "key": "tasks",
            "title": "AI任务与确认",
            "content": f"当前有{pending_confirmation_count}个AI草稿等待老板确认。" if pending_confirmation_count else "当前没有待确认AI草稿。",
            "metrics": {
                "pending_confirmation_count": pending_confirmation_count,
                "recent_activity_count": recent_activity_count,
            },
            "employee": "AI运营协调官",
        },
    ]

    next_actions = [
        {
            "title": str(priority.get("title", "查看今日重点")),
            "reason": str(priority.get("reason", "AI已整理今日经营重点")),
            "route": dict(priority.get("action", {})).get("route", "/dashboard"),
            "label": dict(priority.get("action", {})).get("label", "查看"),
        }
        for priority in top_priorities[:3]
    ]
    if not next_actions:
        next_actions = [{"title": "查看经营看板", "reason": "暂无高优先级事项", "route": "/dashboard", "label": "查看看板"}]

    risk_notes: list[str] = []
    if pending_confirmation_count:
        risk_notes.append("涉及库存、销售、采购的AI草稿必须先确认，确认前不会改业务事实。")
    if low_stock_count:
        risk_notes.append("低库存商品可能影响后续销售，建议先核对库存再补货。")
    if sales_count == 0:
        risk_notes.append("今日暂无销售流水，日报可能缺少销售趋势判断。")
    if not risk_notes:
        risk_notes.append("当前未发现高风险事项，继续保持数据录入完整。")

    return {
        "title": "今日经营参谋日报",
        "generated_by": "经营策略顾问",
        "summary": (
            f"今日销售额{sales_amount:.2f}元，{sales_count}笔销售；"
            f"低库存{low_stock_count}个，待确认AI任务{pending_confirmation_count}个。"
        ),
        "business_health": business_health,
        "sections": sections,
        "next_actions": next_actions,
        "risk_notes": risk_notes,
        "suggestion_count": len(suggestions),
        "evidence": {
            "source": "pc-dashboard-overview",
            "sales_transaction_count": sales_count,
            "low_stock_count": low_stock_count,
            "pending_confirmation_count": pending_confirmation_count,
            "active_item_count": active_item_count,
            "recent_activity_count": recent_activity_count,
        },
    }


def _today_report_date() -> str:
    return datetime.utcnow().date().isoformat()


def _build_execution_recaps(db_session: Session, *, tenant_id: str, shop_id: str, limit: int = 8) -> list[dict[str, object]]:
    rows = db_session.execute(
        select(V2TaskRun)
        .where(
            V2TaskRun.tenant_id == tenant_id,
            V2TaskRun.shop_id == shop_id,
        )
        .order_by(V2TaskRun.created_at.desc())
        .limit(limit)
    ).scalars().all()
    recaps: list[dict[str, object]] = []
    for row in rows:
        recaps.append(
            {
                "id": row.task_run_id,
                "summary": row.result_summary or "AI任务已记录",
                "status": row.status,
                "intent_type": row.intent_type,
                "risk_level": row.risk_level,
                "created_at": row.created_at.isoformat() if row.created_at is not None else "",
                "route": "/tasks" if row.status == "awaiting_confirmation" else "/dashboard",
            }
        )
    return recaps


def _source_employee_for_intent(intent_type: str | None) -> str:
    key = _employee_key_for_intent(intent_type)
    return {
        "business_data_analyst": "经营数据分析员",
        "purchase_replenishment_specialist": "进货补货专员",
        "inventory_risk_controller": "库存风控专员",
        "product_catalog_manager": "商品档案管理员",
        "operations_coordinator": "AI运营协调官",
    }.get(key, "AI运营协调官")


def _execution_recap_summary(items: list[dict[str, object]]) -> dict[str, int]:
    sales_order_count = sum(1 for item in items if "sales" in str(item.get("kind", "")))
    purchase_order_count = sum(1 for item in items if "purchase" in str(item.get("kind", "")))
    inventory_count = sum(1 for item in items if any(token in str(item.get("kind", "")) for token in ["inventory", "stock_in", "stock_out"]))
    other_count = max(0, len(items) - sales_order_count - purchase_order_count - inventory_count)
    return {
        "total_count": len(items),
        "sales_order_count": sales_order_count,
        "purchase_order_count": purchase_order_count,
        "inventory_count": inventory_count,
        "other_count": other_count,
    }


def _build_committed_execution_recaps(db_session: Session, *, tenant_id: str, shop_id: str, limit: int = 20) -> list[dict[str, object]]:
    safe_limit = max(1, min(limit, 100))
    rows = db_session.execute(
        select(V2Confirmation, V2TaskRun)
        .join(V2TaskRun, V2TaskRun.task_run_id == V2Confirmation.task_run_id)
        .where(
            V2Confirmation.tenant_id == tenant_id,
            V2Confirmation.shop_id == shop_id,
            V2TaskRun.tenant_id == tenant_id,
            V2TaskRun.shop_id == shop_id,
            V2Confirmation.status.in_(["approved", "committed"]),
        )
        .order_by(V2Confirmation.resolved_at.desc().nullslast(), V2Confirmation.created_at.desc())
        .limit(safe_limit)
    ).all()
    items: list[dict[str, object]] = []
    for confirmation, task in rows:
        resolution_payload = confirmation.resolution_payload or {}
        execution_result = resolution_payload.get("execution_result") if isinstance(resolution_payload, dict) else None
        if not isinstance(execution_result, dict):
            continue
        if execution_result.get("status") != "committed":
            continue
        kind = str(execution_result.get("kind") or confirmation.confirmation_type or "ai_task")
        raw_effects = execution_result.get("effects")
        if isinstance(raw_effects, dict):
            effects = [str(value) for value in raw_effects.values() if value]
        elif isinstance(raw_effects, list):
            effects = [str(effect) for effect in raw_effects if effect]
        else:
            effects = []
        items.append(
            {
                "confirmation_id": confirmation.confirmation_id,
                "task_run_id": confirmation.task_run_id,
                "kind": kind,
                "status": "committed",
                "summary": str(execution_result.get("summary") or task.result_summary or "AI任务已完成并落账"),
                "effects": effects,
                "next_route": str(execution_result.get("next_route") or "/tasks"),
                "created_at": confirmation.created_at.isoformat() if confirmation.created_at is not None else "",
                "resolved_at": confirmation.resolved_at.isoformat() if confirmation.resolved_at is not None else "",
                "source_employee": _source_employee_for_intent(task.intent_type or confirmation.confirmation_type),
                "intent_type": task.intent_type or confirmation.confirmation_type,
                "risk_level": task.risk_level,
                "evidence": [
                    "来自已审批AI任务",
                    "execution_result.status=committed",
                    f"confirmation_id={confirmation.confirmation_id}",
                ],
            }
        )
    return items


def get_pc_dashboard_execution_recaps(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    limit: int = 20,
) -> dict[str, object]:
    items = _build_committed_execution_recaps(db_session, tenant_id=tenant_id, shop_id=shop_id, limit=limit)
    return {
        "summary": _execution_recap_summary(items),
        "items": items,
        "generated_at": datetime.utcnow().replace(microsecond=0).isoformat(),
    }


def _build_report_history(
    *,
    revenue,
    low_stock_count: int,
    pending_confirmation_count: int,
    days: int = 7,
) -> list[dict[str, object]]:
    today = datetime.utcnow().date()
    items: list[dict[str, object]] = []
    for offset in range(max(1, min(days, 31))):
        report_date = today - timedelta(days=offset)
        is_today = offset == 0
        total_revenue = round(_to_float(revenue.total_revenue), 2) if is_today else 0.0
        transaction_count = int(revenue.transaction_count) if is_today else 0
        day_low_stock_count = low_stock_count if is_today else 0
        day_pending_count = pending_confirmation_count if is_today else 0
        health = "attention_needed" if day_low_stock_count or day_pending_count else "healthy" if transaction_count else "quiet"
        items.append(
            {
                "report_date": report_date.isoformat(),
                "title": "今日经营日报" if is_today else f"{report_date.isoformat()} 经营日报",
                "summary": (
                    f"销售额{total_revenue:.2f}元，{transaction_count}笔销售；"
                    f"低库存{day_low_stock_count}个，待确认AI任务{day_pending_count}个。"
                ),
                "business_health": health,
                "total_revenue": total_revenue,
                "transaction_count": transaction_count,
                "low_stock_count": day_low_stock_count,
                "pending_confirmation_count": day_pending_count,
                "route": "/daily-report",
            }
        )
    return items


def get_pc_dashboard_daily_report(
    db_session: Session,
    *,
    account_id: str,
    tenant_id: str,
    shop_id: str,
) -> dict[str, object]:
    overview = get_pc_dashboard_overview(
        db_session,
        account_id=account_id,
        tenant_id=tenant_id,
        shop_id=shop_id,
    )
    base_report = dict(overview["daily_advisor_report"])
    revenue = get_revenue_summary(db_session, tenant_id=tenant_id, shop_id=shop_id, days=1)
    low_stock_alerts = get_low_stock_alerts(db_session, tenant_id=tenant_id, shop_id=shop_id, limit=20)
    pending_confirmation_count = _get_pending_confirmation_count(db_session, tenant_id=tenant_id, shop_id=shop_id)
    execution_recaps = _build_execution_recaps(db_session, tenant_id=tenant_id, shop_id=shop_id)
    history = _build_report_history(
        revenue=revenue,
        low_stock_count=len(low_stock_alerts),
        pending_confirmation_count=pending_confirmation_count,
        days=7,
    )
    sections = list(base_report.get("sections", []))
    sections.append(
        {
            "key": "execution_recaps",
            "title": "AI执行复盘",
            "content": f"经营策略顾问已整理最近{len(execution_recaps)}条AI任务执行记录。" if execution_recaps else "今日暂无AI执行复盘。",
            "metrics": {"execution_recap_count": len(execution_recaps)},
            "employee": "AI运营协调官",
        }
    )
    timeline = [
        {
            "time_label": "今日",
            "actor_name": section.get("employee", "经营策略顾问"),
            "summary": section.get("content", "日报分段已生成"),
            "route": "/daily-report",
        }
        for section in sections[:6]
    ]
    evidence = dict(base_report.get("evidence", {}))
    evidence.update(
        {
            "source": "pc-dashboard-daily-report",
            "report_date": _today_report_date(),
            "pending_confirmation_count": pending_confirmation_count,
            "low_stock_count": len(low_stock_alerts),
            "execution_recap_count": len(execution_recaps),
        }
    )
    return {
        **base_report,
        "title": "AI经营日报详情",
        "report_date": _today_report_date(),
        "generated_at": datetime.utcnow().replace(microsecond=0).isoformat(),
        "sections": sections,
        "execution_recaps": execution_recaps,
        "timeline": timeline,
        "history": history,
        "evidence": evidence,
    }


def get_pc_dashboard_daily_report_history(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    days: int = 7,
) -> dict[str, object]:
    revenue = get_revenue_summary(db_session, tenant_id=tenant_id, shop_id=shop_id, days=1)
    low_stock_alerts = get_low_stock_alerts(db_session, tenant_id=tenant_id, shop_id=shop_id, limit=20)
    pending_confirmation_count = _get_pending_confirmation_count(db_session, tenant_id=tenant_id, shop_id=shop_id)
    return {
        "items": _build_report_history(
            revenue=revenue,
            low_stock_count=len(low_stock_alerts),
            pending_confirmation_count=pending_confirmation_count,
            days=days,
        )
    }


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
    employee_stats = _build_employee_runtime_stats(db_session, tenant_id=tenant_id, shop_id=shop_id)
    top_priorities = _build_top_priorities(
        low_stock_count=low_stock_count,
        pending_confirmation_count=pending_confirmation_count,
        revenue=revenue,
    )
    suggestions = _build_suggestions(
        low_stock_count=low_stock_count,
        pending_confirmation_count=pending_confirmation_count,
        revenue=revenue,
    )
    activities = _build_activities(
        low_stock_count=low_stock_count,
        pending_confirmation_count=pending_confirmation_count,
        revenue=revenue,
    )
    todos = _build_todos(
        low_stock_count=low_stock_count,
        pending_confirmation_count=pending_confirmation_count,
    )
    daily_advisor_report = _build_daily_advisor_report(
        revenue=revenue,
        low_stock_count=low_stock_count,
        pending_confirmation_count=pending_confirmation_count,
        active_item_count=active_item_count,
        recent_activity_count=recent_activity_count,
        top_priorities=top_priorities,
        suggestions=suggestions,
    )

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
            employee_stats=employee_stats,
        ),
        "top_priorities": top_priorities,
        "suggestions": suggestions,
        "activities": activities,
        "todos": todos,
        "daily_advisor_report": daily_advisor_report,
        "notifications": _build_notifications(
            pending_confirmation_count=pending_confirmation_count,
            low_stock_alerts=low_stock_alerts,
            daily_advisor_report=daily_advisor_report,
        ),
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
