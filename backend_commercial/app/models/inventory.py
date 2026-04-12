"""
Inventory models with multi-tenant support
"""
from datetime import datetime
from typing import Optional, List
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Float, Integer, Text, JSON
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSONB
from sqlalchemy.orm import relationship
import uuid

from app.db.base import Base


class InventoryItem(Base):
    """Inventory item model with multi-tenant isolation"""
    __tablename__ = "inventory_items"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Multi-tenant isolation
    shop_id = Column(UUID(as_uuid=True), ForeignKey("shops.id"), nullable=False, index=True)
    
    # Basic info
    name = Column(String(200), nullable=False, index=True)
    sku = Column(String(100), unique=True, nullable=True, index=True)
    barcode = Column(String(100), nullable=True, index=True)
    category = Column(String(100), nullable=True, index=True)
    description = Column(Text, nullable=True)
    
    # Stock info
    current_stock = Column(Float, default=0, nullable=False)
    min_stock = Column(Float, default=0, nullable=False)
    max_stock = Column(Float, nullable=True)
    unit = Column(String(20), default="件", nullable=False)
    
    # Pricing
    cost_price = Column(Float, default=0, nullable=False)
    selling_price = Column(Float, default=0, nullable=False)
    wholesale_price = Column(Float, nullable=True)
    
    # Supplier info
    supplier_id = Column(UUID(as_uuid=True), ForeignKey("suppliers.id"), nullable=True)
    supplier_sku = Column(String(100), nullable=True)
    
    # Location
    location = Column(String(100), nullable=True)
    warehouse_zone = Column(String(50), nullable=True)
    shelf_number = Column(String(50), nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    is_tracked = Column(Boolean, default=True, nullable=False)  # Whether stock is tracked
    is_perishable = Column(Boolean, default=False, nullable=False)
    expiry_date = Column(DateTime, nullable=True)
    
    # Metadata
    image_url = Column(String(500), nullable=True)
    tags = Column(ARRAY(String), default=[])
    custom_fields = Column(JSONB, default={})
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_stock_update = Column(DateTime, nullable=True)
    
    # Relationships
    shop = relationship("Shop", back_populates="inventory_items")
    supplier = relationship("Supplier", back_populates="items")
    stock_movements = relationship("StockMovement", back_populates="item")
    order_items = relationship("OrderItem", back_populates="item")
    
    # Indexes for performance
    __table_args__ = (
        # Composite index for shop-specific queries
        {"postgresql_partition_by": "LIST (shop_id)"}  # For partitioning if needed
    )
    
    @property
    def is_low_stock(self) -> bool:
        """Check if stock is below minimum"""
        return self.current_stock <= self.min_stock
    
    @property
    def is_overstock(self) -> bool:
        """Check if stock is above maximum"""
        if self.max_stock is None:
            return False
        return self.current_stock >= self.max_stock
    
    @property
    def profit_margin(self) -> float:
        """Calculate profit margin"""
        if self.cost_price == 0:
            return 0
        return ((self.selling_price - self.cost_price) / self.cost_price) * 100


class StockMovement(Base):
    """Stock movement history with multi-tenant isolation"""
    __tablename__ = "stock_movements"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Multi-tenant isolation
    shop_id = Column(UUID(as_uuid=True), ForeignKey("shops.id"), nullable=False, index=True)
    
    # Movement info
    item_id = Column(UUID(as_uuid=True), ForeignKey("inventory_items.id"), nullable=False, index=True)
    movement_type = Column(String(20), nullable=False, index=True)  # in, out, adjustment, transfer
    quantity = Column(Float, nullable=False)
    unit_price = Column(Float, nullable=True)
    
    # Reference info
    reference_type = Column(String(50), nullable=True)  # order, purchase, adjustment, etc.
    reference_id = Column(UUID(as_uuid=True), nullable=True)
    reason = Column(String(200), nullable=True)
    
    # Source/Destination
    source_location = Column(String(100), nullable=True)
    destination_location = Column(String(100), nullable=True)
    
    # User info
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    shop = relationship("Shop")
    item = relationship("InventoryItem", back_populates="stock_movements")
    user = relationship("User")


class Supplier(Base):
    """Supplier model with multi-tenant isolation"""
    __tablename__ = "suppliers"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Multi-tenant isolation
    shop_id = Column(UUID(as_uuid=True), ForeignKey("shops.id"), nullable=False, index=True)
    
    # Basic info
    name = Column(String(200), nullable=False, index=True)
    code = Column(String(50), unique=True, nullable=True, index=True)
    contact_person = Column(String(100), nullable=True)
    
    # Contact info
    email = Column(String(255), nullable=True)
    phone = Column(String(20), nullable=True)
    mobile = Column(String(20), nullable=True)
    address = Column(Text, nullable=True)
    website = Column(String(500), nullable=True)
    
    # Business info
    tax_id = Column(String(100), nullable=True)
    business_license = Column(String(100), nullable=True)
    bank_account = Column(String(100), nullable=True)
    bank_name = Column(String(100), nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    rating = Column(Integer, nullable=True)  # 1-5 rating
    
    # Metadata
    notes = Column(Text, nullable=True)
    tags = Column(ARRAY(String), default=[])
    custom_fields = Column(JSONB, default={})
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    shop = relationship("Shop")
    items = relationship("InventoryItem", back_populates="supplier")
    purchase_orders = relationship("PurchaseOrder", back_populates="supplier")


class PurchaseOrder(Base):
    """Purchase order model with multi-tenant isolation"""
    __tablename__ = "purchase_orders"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Multi-tenant isolation
    shop_id = Column(UUID(as_uuid=True), ForeignKey("shops.id"), nullable=False, index=True)
    
    # Order info
    order_number = Column(String(50), unique=True, nullable=False, index=True)
    supplier_id = Column(UUID(as_uuid=True), ForeignKey("suppliers.id"), nullable=False)
    
    # Status
    status = Column(String(20), default="draft", nullable=False, index=True)  # draft, pending, approved, received, cancelled
    
    # Dates
    order_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    expected_delivery_date = Column(DateTime, nullable=True)
    actual_delivery_date = Column(DateTime, nullable=True)
    
    # Financial
    subtotal = Column(Float, default=0, nullable=False)
    tax_amount = Column(Float, default=0, nullable=False)
    shipping_cost = Column(Float, default=0, nullable=False)
    total_amount = Column(Float, default=0, nullable=False)
    currency = Column(String(3), default="CNY", nullable=False)
    
    # Shipping info
    shipping_address = Column(Text, nullable=True)
    shipping_method = Column(String(100), nullable=True)
    tracking_number = Column(String(100), nullable=True)
    
    # User info
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    approved_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    
    # Metadata
    notes = Column(Text, nullable=True)
    attachments = Column(ARRAY(String), default=[])
    custom_fields = Column(JSONB, default={})
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    shop = relationship("Shop")
    supplier = relationship("Supplier", back_populates="purchase_orders")
    items = relationship("PurchaseOrderItem", back_populates="purchase_order")
    created_by_user = relationship("User", foreign_keys=[created_by])
    approved_by_user = relationship("User", foreign_keys=[approved_by])


class PurchaseOrderItem(Base):
    """Purchase order item model"""
    __tablename__ = "purchase_order_items"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    purchase_order_id = Column(UUID(as_uuid=True), ForeignKey("purchase_orders.id"), nullable=False)
    item_id = Column(UUID(as_uuid=True), ForeignKey("inventory_items.id"), nullable=False)
    
    # Item info
    quantity = Column(Float, nullable=False)
    unit_price = Column(Float, nullable=False)
    total_price = Column(Float, nullable=False)
    
    # Delivery info
    quantity_received = Column(Float, default=0, nullable=False)
    received_date = Column(DateTime, nullable=True)
    
    # Status
    status = Column(String(20), default="pending", nullable=False)  # pending, partial, received, cancelled
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    purchase_order = relationship("PurchaseOrder", back_populates="items")
    item = relationship("InventoryItem")