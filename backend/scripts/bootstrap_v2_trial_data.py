"""Bootstrap V2 Trial Data - 创建演示数据用于pilot验证"""
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from decimal import Decimal
import uuid
from app.models.v2_identity import V2Account, V2Tenant, V2Shop, V2TenantMembership
from app.models.v2_inventory import V2InventoryItem, V2InventoryStockSnapshot
from app.services.v2_identity import hash_v2_password

def generate_id():
    return str(uuid.uuid4()).replace("-", "")[:24]

def utc_now():
    from app.services.v2_time import utc_now_naive
    return utc_now_naive()

def ensure_not_production() -> None:
    if os.getenv("APP_ENV", "development").strip().lower() == "production":
        raise SystemExit("Refusing to seed trial data in production")


def setup_v2_tables():
    database_url = os.getenv("DATABASE_URL", "sqlite:///./aism-dev.db")
    engine = create_engine(database_url.replace("sqlite://", "sqlite:///"))
    V2Account.metadata.create_all(engine)
    V2Tenant.metadata.create_all(engine)
    V2Shop.metadata.create_all(engine)
    V2TenantMembership.metadata.create_all(engine)
    V2InventoryItem.metadata.create_all(engine)
    V2InventoryStockSnapshot.metadata.create_all(engine)
    return engine

def seed_trial_data(db):
    if db.query(V2Account).first():
        print("[SKIP] V2Account already exists")
        return

    password = "demo123"
    salt = generate_id()[:16]
    password_hash = hash_v2_password(password, salt)

    account_id = generate_id()
    demo_account = V2Account(
        account_id=account_id,
        email="demo@aistoremanager.com",
        display_name="演示用户",
        password_hash=password_hash,
        password_salt=salt,
        status="active",
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    db.add(demo_account)
    db.flush()
    print(f"[CREATE] V2Account: {demo_account.email}")

    tenant_id = generate_id()
    demo_tenant = V2Tenant(
        tenant_id=tenant_id,
        name="小米五金店租户",
        slug="xiaomi-hardware",
        status="active",
        plan_code="trial",
        owner_account_id=account_id,
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    db.add(demo_tenant)
    db.flush()
    print(f"[CREATE] V2Tenant: {demo_tenant.name}")

    membership_id = generate_id()
    membership = V2TenantMembership(
        membership_id=membership_id,
        tenant_id=tenant_id,
        account_id=account_id,
        role_key="owner",
        status="active",
        joined_at=utc_now(),
        updated_at=utc_now(),
    )
    db.add(membership)
    db.flush()

    shop_id = generate_id()
    demo_shop = V2Shop(
        shop_id=shop_id,
        tenant_id=tenant_id,
        code="main",
        name="小米五金店",
        locale="zh-CN",
        timezone="Asia/Shanghai",
        status="active",
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    db.add(demo_shop)
    db.flush()
    print(f"[CREATE] V2Shop: {demo_shop.name}")
    
    # Create V2ShopAccess linking membership to shop
    from app.models.v2_identity import V2ShopAccess
    shop_access = V2ShopAccess(
        shop_access_id=generate_id(),
        tenant_id=tenant_id,
        shop_id=shop_id,
        membership_id=membership_id,
        access_level="owner",
        status="active",
        created_at=utc_now(),
    )
    db.add(shop_access)
    db.flush()
    print(f"[CREATE] V2ShopAccess: owner -> {demo_shop.name}")
    
    # Create V2InventoryItems first (required for snapshots)
    inventory_items = [
        V2InventoryItem(
            inventory_item_id=generate_id(),
            tenant_id=tenant_id,
            sku="TOOL-HAMMER-001",
            name="高精度锤子",
            barcode="6901234567890",
            default_unit="把",
            status="active",
            created_at=utc_now(),
            updated_at=utc_now(),
        ),
        V2InventoryItem(
            inventory_item_id=generate_id(),
            tenant_id=tenant_id,
            sku="TOOL-WRENCH-002",
            name="多功能扳手套装",
            barcode="6900987654321",
            default_unit="套",
            status="active",
            created_at=utc_now(),
            updated_at=utc_now(),
        ),
        V2InventoryItem(
            inventory_item_id=generate_id(),
            tenant_id=tenant_id,
            sku="ELEC-SCREW-003",
            name="电动螺丝刀",
            barcode="6901111222233",
            default_unit="个",
            status="active",
            created_at=utc_now(),
            updated_at=utc_now(),
        ),
    ]
    db.add_all(inventory_items)
    db.flush()
    print(f"[CREATE] Inventory items: {len(inventory_items)}")

    # Create V2InventoryStockSnapshot for each item
    snapshots = [
        V2InventoryStockSnapshot(
            snapshot_id=generate_id(),
            tenant_id=tenant_id,
            shop_id=shop_id,
            inventory_item_id=inventory_items[0].inventory_item_id,
            current_quantity=Decimal("15"),
            current_price=Decimal("39.90"),
            low_stock_threshold=Decimal("5"),
            updated_at=utc_now(),
        ),
        V2InventoryStockSnapshot(
            snapshot_id=generate_id(),
            tenant_id=tenant_id,
            shop_id=shop_id,
            inventory_item_id=inventory_items[1].inventory_item_id,
            current_quantity=Decimal("8"),
            current_price=Decimal("129.00"),
            low_stock_threshold=Decimal("3"),
            updated_at=utc_now(),
        ),
        V2InventoryStockSnapshot(
            snapshot_id=generate_id(),
            tenant_id=tenant_id,
            shop_id=shop_id,
            inventory_item_id=inventory_items[2].inventory_item_id,
            current_quantity=Decimal("3"),
            current_price=Decimal("199.00"),
            low_stock_threshold=Decimal("5"),
            updated_at=utc_now(),
        ),
    ]
    db.add_all(snapshots)
    db.commit()
    print(f"[CREATE] Stock snapshots: {len(snapshots)}")
    print("\n✅ V2 Trial data seeded successfully!")
    print(f"   Login: demo@aistoremanager.com / demo123")
    print(f"   Shop: {demo_shop.name} ({shop_id})")
    print(f"   Low-stock alert: 电动螺丝刀 (qty=3 < threshold=5)")

if __name__ == "__main__":
    ensure_not_production()
    print("Bootstrapping V2 Trial Data for local-demo/trial only...")
    engine = setup_v2_tables()
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    try:
        seed_trial_data(db)
    finally:
        db.close()
