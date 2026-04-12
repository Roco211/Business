"""
Shop management routes for multi-tenancy
"""
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from app.db.base import get_db, PaginationParams, apply_pagination, apply_sorting
from app.models.user import Shop, User, UserRole
from app.core.security import get_current_user_id, require_superuser
from app.core.middleware import get_tenant_context, TenantContextManager
from app.api.schemas.shop import (
    ShopCreate,
    ShopUpdate,
    ShopResponse,
    ShopListResponse,
    ShopSettings,
    ShopFeature,
)

router = APIRouter()


@router.post("/", response_model=ShopResponse, status_code=status.HTTP_201_CREATED)
async def create_shop(
    shop_data: ShopCreate,
    current_user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new shop
    
    Args:
        shop_data: Shop creation data
        current_user_id: Current user ID
        db: Database session
    
    Returns:
        ShopResponse: Created shop
    
    Raises:
        HTTPException: If shop slug already exists
    """
    # Check if shop slug already exists
    existing_shop = await db.execute(
        select(Shop).where(Shop.slug == shop_data.slug)
    )
    if existing_shop.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Shop with this slug already exists",
        )
    
    # Create shop
    shop = Shop(
        name=shop_data.name,
        slug=shop_data.slug,
        business_license=shop_data.business_license,
        tax_id=shop_data.tax_id,
        address=shop_data.address,
        phone=shop_data.phone,
        email=shop_data.email,
        settings=shop_data.settings or {},
        features=shop_data.features or [],
    )
    
    db.add(shop)
    await db.commit()
    await db.refresh(shop)
    
    # Update current user to be shop owner
    user_result = await db.execute(select(User).where(User.id == current_user_id))
    user = user_result.scalar_one_or_none()
    
    if user:
        user.shop_id = shop.id
        # Add shop owner role if not already present
        # This is simplified - in real implementation, use role relationships
        await db.commit()
    
    return ShopResponse.from_orm(shop)


@router.get("/", response_model=ShopListResponse)
async def list_shops(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    is_active: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    current_user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    List shops with pagination and filtering
    
    Args:
        page: Page number
        page_size: Items per page
        is_active: Filter by active status
        search: Search in name or slug
        current_user_id: Current user ID
        db: Database session
    
    Returns:
        ShopListResponse: Paginated list of shops
    """
    # Build query
    query = select(Shop)
    
    # Apply filters
    filters = []
    
    if is_active is not None:
        filters.append(Shop.is_active == is_active)
    
    if search:
        filters.append(
            or_(
                Shop.name.ilike(f"%{search}%"),
                Shop.slug.ilike(f"%{search}%"),
            )
        )
    
    if filters:
        query = query.where(and_(*filters))
    
    # Get total count
    count_query = select(Shop).where(and_(*filters)) if filters else select(Shop)
    count_result = await db.execute(count_query)
    total_count = len(count_result.scalars().all())
    
    # Apply pagination
    pagination = PaginationParams(page=page, page_size=page_size)
    query = apply_pagination(query, pagination)
    
    # Apply sorting
    query = query.order_by(Shop.created_at.desc())
    
    # Execute query
    result = await db.execute(query)
    shops = result.scalars().all()
    
    return ShopListResponse(
        items=[ShopResponse.from_orm(shop) for shop in shops],
        total=total_count,
        page=page,
        page_size=page_size,
        total_pages=(total_count + page_size - 1) // page_size,
    )


@router.get("/me", response_model=ShopResponse)
async def get_my_shop(
    current_user_id: str = Depends(get_current_user_id),
    tenant_ctx: TenantContextManager = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    """
    Get current user's shop
    
    Args:
        current_user_id: Current user ID
        tenant_ctx: Tenant context
        db: Database session
    
    Returns:
        ShopResponse: User's shop
    
    Raises:
        HTTPException: If user has no shop
    """
    # Get user
    user_result = await db.execute(select(User).where(User.id == current_user_id))
    user = user_result.scalar_one_or_none()
    
    if not user or not user.shop_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User has no shop assigned",
        )
    
    # Get shop
    shop_result = await db.execute(select(Shop).where(Shop.id == user.shop_id))
    shop = shop_result.scalar_one_or_none()
    
    if not shop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shop not found",
        )
    
    return ShopResponse.from_orm(shop)


@router.get("/{shop_id}", response_model=ShopResponse)
async def get_shop(
    shop_id: UUID,
    current_user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Get shop by ID
    
    Args:
        shop_id: Shop ID
        current_user_id: Current user ID
        db: Database session
    
    Returns:
        ShopResponse: Shop details
    
    Raises:
        HTTPException: If shop not found
    """
    # Get shop
    shop_result = await db.execute(select(Shop).where(Shop.id == shop_id))
    shop = shop_result.scalar_one_or_none()
    
    if not shop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shop not found",
        )
    
    return ShopResponse.from_orm(shop)


@router.put("/{shop_id}", response_model=ShopResponse)
async def update_shop(
    shop_id: UUID,
    shop_data: ShopUpdate,
    current_user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Update shop
    
    Args:
        shop_id: Shop ID
        shop_data: Shop update data
        current_user_id: Current user ID
        db: Database session
    
    Returns:
        ShopResponse: Updated shop
    
    Raises:
        HTTPException: If shop not found or permission denied
    """
    # Get shop
    shop_result = await db.execute(select(Shop).where(Shop.id == shop_id))
    shop = shop_result.scalar_one_or_none()
    
    if not shop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shop not found",
        )
    
    # Check permissions (simplified)
    user_result = await db.execute(select(User).where(User.id == current_user_id))
    user = user_result.scalar_one_or_none()
    
    if not user or (user.shop_id != shop_id and not user.is_superuser):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )
    
    # Update shop fields
    update_data = shop_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(shop, field, value)
    
    await db.commit()
    await db.refresh(shop)
    
    return ShopResponse.from_orm(shop)


@router.delete("/{shop_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_shop(
    shop_id: UUID,
    current_user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete shop (soft delete)
    
    Args:
        shop_id: Shop ID
        current_user_id: Current user ID
        db: Database session
    
    Raises:
        HTTPException: If shop not found or permission denied
    """
    # Get shop
    shop_result = await db.execute(select(Shop).where(Shop.id == shop_id))
    shop = shop_result.scalar_one_or_none()
    
    if not shop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shop not found",
        )
    
    # Check permissions (only superadmin can delete shops)
    user_result = await db.execute(select(User).where(User.id == current_user_id))
    user = user_result.scalar_one_or_none()
    
    if not user or not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only superadmins can delete shops",
        )
    
    # Soft delete
    shop.is_active = False
    await db.commit()


@router.post("/{shop_id}/activate", response_model=ShopResponse)
async def activate_shop(
    shop_id: UUID,
    current_user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Activate shop
    
    Args:
        shop_id: Shop ID
        current_user_id: Current user ID
        db: Database session
    
    Returns:
        ShopResponse: Activated shop
    
    Raises:
        HTTPException: If shop not found or permission denied
    """
    # Get shop
    shop_result = await db.execute(select(Shop).where(Shop.id == shop_id))
    shop = shop_result.scalar_one_or_none()
    
    if not shop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shop not found",
        )
    
    # Check permissions (only superadmin can activate shops)
    user_result = await db.execute(select(User).where(User.id == current_user_id))
    user = user_result.scalar_one_or_none()
    
    if not user or not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only superadmins can activate shops",
        )
    
    # Activate shop
    shop.is_active = True
    await db.commit()
    await db.refresh(shop)
    
    return ShopResponse.from_orm(shop)


@router.put("/{shop_id}/settings", response_model=ShopResponse)
async def update_shop_settings(
    shop_id: UUID,
    settings_data: ShopSettings,
    current_user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Update shop settings
    
    Args:
        shop_id: Shop ID
        settings_data: Shop settings
        current_user_id: Current user ID
        db: Database session
    
    Returns:
        ShopResponse: Updated shop
    
    Raises:
        HTTPException: If shop not found or permission denied
    """
    # Get shop
    shop_result = await db.execute(select(Shop).where(Shop.id == shop_id))
    shop = shop_result.scalar_one_or_none()
    
    if not shop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shop not found",
        )
    
    # Check permissions
    user_result = await db.execute(select(User).where(User.id == current_user_id))
    user = user_result.scalar_one_or_none()
    
    if not user or (user.shop_id != shop_id and not user.is_superuser):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )
    
    # Update settings
    shop.settings = settings_data.settings
    await db.commit()
    await db.refresh(shop)
    
    return ShopResponse.from_orm(shop)


@router.post("/{shop_id}/features", response_model=ShopResponse)
async def update_shop_features(
    shop_id: UUID,
    features_data: ShopFeature,
    current_user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Update shop features
    
    Args:
        shop_id: Shop ID
        features_data: Shop features
        current_user_id: Current user ID
        db: Database session
    
    Returns:
        ShopResponse: Updated shop
    
    Raises:
        HTTPException: If shop not found or permission denied
    """
    # Get shop
    shop_result = await db.execute(select(Shop).where(Shop.id == shop_id))
    shop = shop_result.scalar_one_or_none()
    
    if not shop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shop not found",
        )
    
    # Check permissions (only superadmin can update features)
    user_result = await db.execute(select(User).where(User.id == current_user_id))
    user = user_result.scalar_one_or_none()
    
    if not user or not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only superadmins can update shop features",
        )
    
    # Update features
    shop.features = features_data.features
    await db.commit()
    await db.refresh(shop)
    
    return ShopResponse.from_orm(shop)


@router.get("/{shop_id}/users", response_model=List[dict])
async def list_shop_users(
    shop_id: UUID,
    current_user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    List users in a shop
    
    Args:
        shop_id: Shop ID
        current_user_id: Current user ID
        db: Database session
    
    Returns:
        List[dict]: List of users in the shop
    
    Raises:
        HTTPException: If shop not found or permission denied
    """
    # Get shop
    shop_result = await db.execute(select(Shop).where(Shop.id == shop_id))
    shop = shop_result.scalar_one_or_none()
    
    if not shop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shop not found",
        )
    
    # Check permissions
    user_result = await db.execute(select(User).where(User.id == current_user_id))
    user = user_result.scalar_one_or_none()
    
    if not user or (user.shop_id != shop_id and not user.is_superuser):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )
    
    # Get users in shop
    users_result = await db.execute(
        select(User).where(User.shop_id == shop_id)
    )
    users = users_result.scalars().all()
    
    return [
        {
            "user_id": str(u.id),
            "email": u.email,
            "username": u.username,
            "full_name": u.full_name,
            "status": u.status,
            "created_at": u.created_at,
        }
        for u in users
    ]