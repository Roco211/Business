import importlib
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.db.session import get_session_factory
from app.models import Alert, Confirmation, InventoryItem, Message, TaskRun
from app.services.bootstrap import ensure_default_context
from app.services.dashboard import get_dashboard_summary


def _load_demo_state_module():
    try:
        return importlib.import_module("app.services.demo_state")
    except ModuleNotFoundError as exc:
        pytest.fail(f"app.services.demo_state module is missing: {exc}")


def _load_bootstrap_function():
    module = _load_demo_state_module()
    bootstrap_demo_state = getattr(module, "bootstrap_demo_state", None)
    if bootstrap_demo_state is None:
        pytest.fail("bootstrap_demo_state function is missing")
    return bootstrap_demo_state


def test_bootstrap_demo_state_creates_representative_default_demo_state(db_session) -> None:
    bootstrap_demo_state = _load_bootstrap_function()

    summary = bootstrap_demo_state(db_session)
    context = ensure_default_context(db_session)
    inventory_items = list(
        db_session.scalars(
            select(InventoryItem)
            .where(
                InventoryItem.shop_id == context.shop.shop_id,
                InventoryItem.is_active.is_(True),
            )
            .order_by(InventoryItem.name.asc())
        )
    )
    open_alerts = list(
        db_session.scalars(
            select(Alert).where(
                Alert.shop_id == context.shop.shop_id,
                Alert.status == "open",
            )
        )
    )
    pending_confirmations = list(
        db_session.scalars(
            select(Confirmation)
            .join(TaskRun, TaskRun.task_run_id == Confirmation.task_run_id)
            .where(
                TaskRun.session_id == context.session.session_id,
                Confirmation.status == "pending",
            )
            .order_by(Confirmation.confirmation_type.asc(), Confirmation.confirmation_id.asc())
        )
    )
    messages = list(
        db_session.scalars(
            select(Message)
            .where(Message.session_id == context.session.session_id)
            .order_by(Message.created_at.asc(), Message.message_id.asc())
        )
    )
    dashboard = get_dashboard_summary(db_session, shop=context.shop)

    inventory_by_name = {item.name: item for item in inventory_items}
    pending_types = [confirmation.confirmation_type for confirmation in pending_confirmations]
    owner_messages = [message for message in messages if message.actor_type == "owner"]
    system_messages = [message for message in messages if message.actor_type == "system"]

    assert summary.inventory_item_names == ["Coca Cola 500ml", "Cola", "Red Bull 250ml"]
    assert summary.pending_confirmation_types == ["receipt-stock-in-batch", "stock-out"]
    assert summary.open_low_stock_item_names == ["Cola"]
    assert summary.inventory_item_count == 3
    assert summary.message_count == 10
    assert summary.pending_confirmation_count == 2
    assert summary.open_low_stock_alert_count == 1

    assert list(inventory_by_name) == ["Coca Cola 500ml", "Cola", "Red Bull 250ml"]
    assert inventory_by_name["Cola"].current_stock == Decimal("4")
    assert inventory_by_name["Cola"].low_stock_threshold == Decimal("5")
    assert inventory_by_name["Red Bull 250ml"].current_stock == Decimal("7")
    assert inventory_by_name["Coca Cola 500ml"].current_stock == Decimal("6")
    assert len(open_alerts) == 1
    assert open_alerts[0].item_id == inventory_by_name["Cola"].item_id
    assert pending_types == ["receipt-stock-in-batch", "stock-out"]
    assert len(messages) == 10
    assert len(owner_messages) == 4
    assert len(system_messages) == 6
    assert sum(message.message_type == "receipt-image" for message in owner_messages) == 2
    assert all(message.message_type == "text" for message in system_messages)
    assert context.shop.default_low_stock_threshold == Decimal("5")
    assert context.session.last_event_seq > 0
    assert dashboard.today_stock_in_count == 3
    assert dashboard.today_task_completed_count == 2
    assert dashboard.pending_confirmations_count == 2
    assert dashboard.open_low_stock_alert_count == 1
    assert dashboard.last_inventory_event_at is not None


def test_bootstrap_demo_state_is_repeatable_without_accumulating_demo_noise(db_session) -> None:
    bootstrap_demo_state = _load_bootstrap_function()

    first_summary = bootstrap_demo_state(db_session)
    second_summary = bootstrap_demo_state(db_session)
    context = ensure_default_context(db_session)

    inventory_names = list(
        db_session.scalars(
            select(InventoryItem.name)
            .where(
                InventoryItem.shop_id == context.shop.shop_id,
                InventoryItem.is_active.is_(True),
            )
            .order_by(InventoryItem.name.asc())
        )
    )
    open_alert_count = len(
        list(
            db_session.scalars(
                select(Alert).where(
                    Alert.shop_id == context.shop.shop_id,
                    Alert.status == "open",
                )
            )
        )
    )
    pending_confirmation_types = list(
        db_session.scalars(
            select(Confirmation.confirmation_type)
            .join(TaskRun, TaskRun.task_run_id == Confirmation.task_run_id)
            .where(
                TaskRun.session_id == context.session.session_id,
                Confirmation.status == "pending",
            )
            .order_by(Confirmation.confirmation_type.asc(), Confirmation.confirmation_id.asc())
        )
    )
    message_count = int(
        db_session.scalar(
            select(func.count())
            .select_from(Message)
            .where(Message.session_id == context.session.session_id)
        )
        or 0
    )
    task_run_count = int(
        db_session.scalar(
            select(func.count())
            .select_from(TaskRun)
            .where(TaskRun.session_id == context.session.session_id)
        )
        or 0
    )

    assert second_summary == first_summary
    assert inventory_names == ["Coca Cola 500ml", "Cola", "Red Bull 250ml"]
    assert open_alert_count == 1
    assert pending_confirmation_types == ["receipt-stock-in-batch", "stock-out"]
    assert message_count == 10
    assert task_run_count == 4


def test_bootstrap_demo_state_persists_seeded_state_across_new_session(db_session) -> None:
    bootstrap_demo_state = _load_bootstrap_function()

    summary = bootstrap_demo_state(db_session)
    verification_session = get_session_factory()()
    try:
        context = ensure_default_context(verification_session)
        persisted_message_count = int(
            verification_session.scalar(
                select(func.count())
                .select_from(Message)
                .where(Message.session_id == context.session.session_id)
            )
            or 0
        )
        persisted_task_run_count = int(
            verification_session.scalar(
                select(func.count())
                .select_from(TaskRun)
                .where(TaskRun.session_id == context.session.session_id)
            )
            or 0
        )
        persisted_open_alert_count = int(
            verification_session.scalar(
                select(func.count())
                .select_from(Alert)
                .where(
                    Alert.shop_id == context.shop.shop_id,
                    Alert.status == "open",
                )
            )
            or 0
        )
    finally:
        verification_session.close()

    assert summary.message_count == persisted_message_count
    assert summary.task_run_count == persisted_task_run_count
    assert summary.open_low_stock_alert_count == persisted_open_alert_count
