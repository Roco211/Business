from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select

from app.api.v2.routes.chat import _execute_stock_transaction
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
from app.services.v2_conversation import approve_v2_confirmation
from app.services.v2_time import utc_now_naive


@dataclass(frozen=True)
class FakeIntent:
    intent_type: str
    item_name: str
    quantity: int


@dataclass(frozen=True)
class FakeContext:
    tenant_id: str
    shop_id: str


@dataclass(frozen=True)
class FakeAccount:
    account_id: str


def _seed_chat_inventory(db_session, *, quantity: Decimal = Decimal("10")) -> tuple[FakeContext, FakeAccount, V2InventoryItem]:
    now = utc_now_naive()
    account = V2Account(
        account_id="acct_chat_confirm",
        email="chat-confirm@example.com",
        display_name="Chat Confirm Tester",
        password_hash="hash",
        password_salt="salt",
        status="active",
        created_at=now,
        updated_at=now,
    )
    tenant = V2Tenant(
        tenant_id="tenant_chat_confirm",
        name="确认流测试租户",
        slug="chat-confirm-tenant",
        status="active",
        plan_code="trial",
        owner_account_id=account.account_id,
        created_at=now,
        updated_at=now,
    )
    shop = V2Shop(
        shop_id="shop_chat_confirm",
        tenant_id=tenant.tenant_id,
        code="MAIN",
        name="确认流测试门店",
        locale="zh-CN",
        timezone="Asia/Shanghai",
        status="active",
        created_at=now,
        updated_at=now,
    )
    item = V2InventoryItem(
        inventory_item_id="item_chat_confirm_hammer",
        tenant_id=tenant.tenant_id,
        sku="HAMMER-CHAT-CONFIRM",
        name="测试锤子",
        barcode=None,
        default_unit="把",
        status="active",
        created_at=now,
        updated_at=now,
    )
    snapshot = V2InventoryStockSnapshot(
        snapshot_id="snap_chat_confirm_hammer",
        tenant_id=tenant.tenant_id,
        shop_id=shop.shop_id,
        inventory_item_id=item.inventory_item_id,
        current_quantity=quantity,
        current_price=Decimal("12.50"),
        low_stock_threshold=Decimal("3"),
        updated_at=now,
    )
    db_session.add_all([account, tenant, shop, item, snapshot])
    db_session.commit()
    return FakeContext(tenant_id=tenant.tenant_id, shop_id=shop.shop_id), FakeAccount(account_id=account.account_id), item


def test_chat_stock_in_creates_pending_confirmation_without_committing_inventory(db_session):
    context, account, item = _seed_chat_inventory(db_session, quantity=Decimal("10"))

    reply = _execute_stock_transaction(
        FakeIntent(intent_type="stock_in", item_name="测试锤子", quantity=5),
        db_session,
        context,
        account,
        "进货5把测试锤子",
    )

    snapshot = db_session.scalar(
        select(V2InventoryStockSnapshot).where(
            V2InventoryStockSnapshot.inventory_item_id == item.inventory_item_id,
            V2InventoryStockSnapshot.shop_id == context.shop_id,
        )
    )
    confirmation = db_session.scalar(select(V2Confirmation))
    task_run = db_session.scalar(select(V2TaskRun))

    assert reply is not None
    assert "待确认" in reply
    assert "入库成功" not in reply
    assert snapshot.current_quantity == Decimal("10.000")
    assert confirmation is not None
    assert confirmation.status == "pending"
    assert confirmation.confirmation_type == "inventory.stock_in"
    assert confirmation.draft_payload["item_id"] == item.inventory_item_id
    assert confirmation.draft_payload["quantity"] == 5
    assert task_run is not None
    assert task_run.status == "awaiting_confirmation"


def test_chat_stock_out_creates_pending_confirmation_without_committing_inventory(db_session):
    context, account, item = _seed_chat_inventory(db_session, quantity=Decimal("10"))

    reply = _execute_stock_transaction(
        FakeIntent(intent_type="stock_out", item_name="测试锤子", quantity=2),
        db_session,
        context,
        account,
        "卖出2把测试锤子",
    )

    snapshot = db_session.scalar(
        select(V2InventoryStockSnapshot).where(
            V2InventoryStockSnapshot.inventory_item_id == item.inventory_item_id,
            V2InventoryStockSnapshot.shop_id == context.shop_id,
        )
    )
    confirmation = db_session.scalar(select(V2Confirmation))
    task_run = db_session.scalar(select(V2TaskRun))

    assert reply is not None
    assert "待确认" in reply
    assert "出库成功" not in reply
    assert snapshot.current_quantity == Decimal("10.000")
    assert confirmation is not None
    assert confirmation.status == "pending"
    assert confirmation.confirmation_type == "inventory.stock_out"
    assert confirmation.draft_payload["inventory_item_id"] == item.inventory_item_id
    assert confirmation.draft_payload["stock_out_quantity"] == 2
    assert task_run is not None
    assert task_run.status == "awaiting_confirmation"


def test_chat_stock_in_confirmation_approval_commits_original_draft_payload(db_session):
    context, account, item = _seed_chat_inventory(db_session, quantity=Decimal("10"))
    _execute_stock_transaction(
        FakeIntent(intent_type="stock_in", item_name="测试锤子", quantity=5),
        db_session,
        context,
        account,
        "进货5把测试锤子",
    )
    confirmation = db_session.scalar(select(V2Confirmation))
    assert confirmation is not None

    approve_v2_confirmation(
        db_session,
        tenant_id=context.tenant_id,
        shop_id=context.shop_id,
        confirmation_id=confirmation.confirmation_id,
        resolution_payload={},
        approved_by_account_id=account.account_id,
    )

    snapshot = db_session.scalar(
        select(V2InventoryStockSnapshot).where(
            V2InventoryStockSnapshot.inventory_item_id == item.inventory_item_id,
            V2InventoryStockSnapshot.shop_id == context.shop_id,
        )
    )
    task_run = db_session.scalar(select(V2TaskRun))
    ledger_event = db_session.scalar(select(V2InventoryLedgerEvent))

    assert snapshot.current_quantity == Decimal("15.000")
    assert confirmation.resolution_payload["fields"]["item_id"] == item.inventory_item_id
    assert confirmation.resolution_payload["fields"]["quantity"] == 5
    assert task_run.status == "committed"
    assert ledger_event is not None
    assert ledger_event.event_type == "stock_in"
    assert ledger_event.quantity_delta == Decimal("5.000")


def test_chat_stock_out_confirmation_approval_commits_original_draft_payload(db_session):
    context, account, item = _seed_chat_inventory(db_session, quantity=Decimal("10"))
    _execute_stock_transaction(
        FakeIntent(intent_type="stock_out", item_name="测试锤子", quantity=2),
        db_session,
        context,
        account,
        "卖出2把测试锤子",
    )
    confirmation = db_session.scalar(select(V2Confirmation))
    assert confirmation is not None

    approve_v2_confirmation(
        db_session,
        tenant_id=context.tenant_id,
        shop_id=context.shop_id,
        confirmation_id=confirmation.confirmation_id,
        resolution_payload={},
        approved_by_account_id=account.account_id,
    )

    snapshot = db_session.scalar(
        select(V2InventoryStockSnapshot).where(
            V2InventoryStockSnapshot.inventory_item_id == item.inventory_item_id,
            V2InventoryStockSnapshot.shop_id == context.shop_id,
        )
    )
    task_run = db_session.scalar(select(V2TaskRun))
    ledger_event = db_session.scalar(select(V2InventoryLedgerEvent))

    assert snapshot.current_quantity == Decimal("8.000")
    assert confirmation.resolution_payload["fields"]["inventory_item_id"] == item.inventory_item_id
    assert confirmation.resolution_payload["fields"]["stock_out_quantity"] == 2
    assert task_run.status == "committed"
    assert ledger_event is not None
    assert ledger_event.event_type == "stock_out"
    assert ledger_event.quantity_delta == Decimal("-2.000")
