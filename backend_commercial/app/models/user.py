"""
User and authentication models
"""
from datetime import datetime
from typing import Optional, List
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Table, Enum
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship
import uuid
import enum

from app.db.base import Base


class UserRole(str, enum.Enum):
    """User roles"""
    SUPER_ADMIN = "super_admin"
    SHOP_OWNER = "shop_owner"
    SHOP_MANAGER = "shop_manager"
    SHOP_STAFF = "shop_staff"
    VIEWER = "viewer"


class UserStatus(str, enum.Enum):
    """User account status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING_VERIFICATION = "pending_verification"


# Association table for user roles
user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True),
    Column("role_id", UUID(as_uuid=True), ForeignKey("roles.id"), primary_key=True),
)


class Role(Base):
    """Role model for RBAC"""
    __tablename__ = "roles"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(50), unique=True, nullable=False)
    description = Column(String(255))
    permissions = Column(ARRAY(String), default=[])
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    users = relationship("User", secondary=user_roles, back_populates="roles")


class User(Base):
    """User model with authentication fields"""
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    phone = Column(String(20), unique=True, nullable=True, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    
    # Authentication
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    status = Column(Enum(UserStatus), default=UserStatus.PENDING_VERIFICATION)
    
    # Profile
    full_name = Column(String(100))
    avatar_url = Column(String(500))
    
    # Multi-tenant
    shop_id = Column(UUID(as_uuid=True), ForeignKey("shops.id"), nullable=True)
    
    # Security
    last_login_at = Column(DateTime)
    last_login_ip = Column(String(45))
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    roles = relationship("Role", secondary=user_roles, back_populates="users")
    shop = relationship("Shop", back_populates="users")
    sessions = relationship("UserSession", back_populates="user")
    
    @property
    def is_superuser(self) -> bool:
        """Check if user has superadmin role"""
        return any(role.name == UserRole.SUPER_ADMIN for role in self.roles)
    
    @property
    def is_locked(self) -> bool:
        """Check if account is locked"""
        if self.locked_until and self.locked_until > datetime.utcnow():
            return True
        return False
    
    def has_permission(self, permission: str) -> bool:
        """Check if user has specific permission"""
        for role in self.roles:
            if permission in role.permissions:
                return True
        return False


class UserSession(Base):
    """User session tracking"""
    __tablename__ = "user_sessions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    session_token = Column(String(500), unique=True, nullable=False)
    refresh_token = Column(String(500), unique=True, nullable=True)
    
    # Session info
    ip_address = Column(String(45))
    user_agent = Column(String(500))
    device_info = Column(String(255))
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    last_activity_at = Column(DateTime, default=datetime.utcnow)
    
    # Status
    is_active = Column(Boolean, default=True)
    revoked_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="sessions")


class Shop(Base):
    """Shop/tenant model for multi-tenancy"""
    __tablename__ = "shops"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    
    # Business info
    business_license = Column(String(100))
    tax_id = Column(String(100))
    address = Column(String(500))
    phone = Column(String(20))
    email = Column(String(255))
    
    # Settings
    settings = Column(JSON, default={})
    features = Column(ARRAY(String), default=[])
    
    # Status
    is_active = Column(Boolean, default=True)
    subscription_plan = Column(String(50), default="free")
    subscription_expires_at = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    users = relationship("User", back_populates="shop")
    inventory_items = relationship("InventoryItem", back_populates="shop")
    orders = relationship("Order", back_populates="shop")