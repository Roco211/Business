"""
Shop schemas for request/response validation
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field, EmailStr, validator


class ShopCreate(BaseModel):
    """Shop creation schema"""
    name: str = Field(..., min_length=2, max_length=100, description="Shop name")
    slug: str = Field(..., min_length=2, max_length=100, description="URL-friendly identifier")
    business_license: Optional[str] = Field(None, max_length=100, description="Business license number")
    tax_id: Optional[str] = Field(None, max_length=100, description="Tax identification number")
    address: Optional[str] = Field(None, max_length=500, description="Business address")
    phone: Optional[str] = Field(None, max_length=20, description="Contact phone")
    email: Optional[EmailStr] = Field(None, description="Contact email")
    settings: Optional[Dict[str, Any]] = Field(default={}, description="Shop settings")
    features: Optional[List[str]] = Field(default=[], description="Enabled features")
    
    @validator("slug")
    def validate_slug(cls, v):
        if not v.isalnum() and "-" not in v and "_" not in v:
            raise ValueError("Slug must be alphanumeric with hyphens or underscores")
        return v.lower()


class ShopUpdate(BaseModel):
    """Shop update schema"""
    name: Optional[str] = Field(None, min_length=2, max_length=100, description="Shop name")
    business_license: Optional[str] = Field(None, max_length=100, description="Business license number")
    tax_id: Optional[str] = Field(None, max_length=100, description="Tax identification number")
    address: Optional[str] = Field(None, max_length=500, description="Business address")
    phone: Optional[str] = Field(None, max_length=20, description="Contact phone")
    email: Optional[EmailStr] = Field(None, description="Contact email")
    is_active: Optional[bool] = Field(None, description="Shop active status")
    subscription_plan: Optional[str] = Field(None, max_length=50, description="Subscription plan")
    subscription_expires_at: Optional[datetime] = Field(None, description="Subscription expiration")


class ShopSettings(BaseModel):
    """Shop settings schema"""
    settings: Dict[str, Any] = Field(..., description="Shop settings")


class ShopFeature(BaseModel):
    """Shop features schema"""
    features: List[str] = Field(..., description="Enabled features")


class ShopResponse(BaseModel):
    """Shop response schema"""
    id: UUID = Field(..., description="Shop ID")
    name: str = Field(..., description="Shop name")
    slug: str = Field(..., description="URL-friendly identifier")
    business_license: Optional[str] = Field(None, description="Business license number")
    tax_id: Optional[str] = Field(None, description="Tax identification number")
    address: Optional[str] = Field(None, description="Business address")
    phone: Optional[str] = Field(None, description="Contact phone")
    email: Optional[str] = Field(None, description="Contact email")
    settings: Dict[str, Any] = Field(default={}, description="Shop settings")
    features: List[str] = Field(default=[], description="Enabled features")
    is_active: bool = Field(..., description="Shop active status")
    subscription_plan: str = Field(..., description="Subscription plan")
    subscription_expires_at: Optional[datetime] = Field(None, description="Subscription expiration")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    
    class Config:
        from_attributes = True


class ShopListResponse(BaseModel):
    """Shop list response schema"""
    items: List[ShopResponse] = Field(..., description="List of shops")
    total: int = Field(..., description="Total number of shops")
    page: int = Field(..., description="Current page")
    page_size: int = Field(..., description="Items per page")
    total_pages: int = Field(..., description="Total number of pages")


class ShopStats(BaseModel):
    """Shop statistics schema"""
    total_users: int = Field(..., description="Total users in shop")
    total_items: int = Field(..., description="Total inventory items")
    total_orders: int = Field(..., description="Total orders")
    total_revenue: float = Field(..., description="Total revenue")
    active_users_today: int = Field(..., description="Active users today")
    orders_today: int = Field(..., description="Orders today")
    revenue_today: float = Field(..., description="Revenue today")


class ShopSubscription(BaseModel):
    """Shop subscription schema"""
    plan: str = Field(..., description="Subscription plan")
    expires_at: datetime = Field(..., description="Expiration date")
    is_active: bool = Field(..., description="Subscription active status")
    features: List[str] = Field(..., description="Available features")
    limits: Dict[str, Any] = Field(..., description="Usage limits")