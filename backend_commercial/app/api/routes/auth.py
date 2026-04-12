"""
Authentication routes
"""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.base import get_db
from app.models.user import User, UserSession, UserStatus
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user_id,
)
from app.api.schemas.auth import (
    UserRegister,
    UserLogin,
    TokenResponse,
    RefreshTokenRequest,
    PasswordReset,
    PasswordResetConfirm,
)
from config import get_settings

settings = get_settings()
router = APIRouter()


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserRegister,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Register a new user
    
    Args:
        user_data: User registration data
        request: FastAPI request object
        db: Database session
    
    Returns:
        TokenResponse: Access and refresh tokens
    
    Raises:
        HTTPException: If user already exists
    """
    # Check if user already exists
    existing_user = await db.execute(
        select(User).where(
            (User.email == user_data.email) | (User.username == user_data.username)
        )
    )
    if existing_user.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email or username already exists",
        )
    
    # Create new user
    user = User(
        email=user_data.email,
        username=user_data.username,
        hashed_password=hash_password(user_data.password),
        full_name=user_data.full_name,
        phone=user_data.phone,
        status=UserStatus.PENDING_VERIFICATION,
    )
    
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    # Create tokens
    access_token = create_access_token(
        subject=str(user.id),
        extra_data={"username": user.username, "email": user.email}
    )
    refresh_token = create_refresh_token(subject=str(user.id))
    
    # Create session
    session = UserSession(
        user_id=user.id,
        session_token=access_token,
        refresh_token=refresh_token,
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent"),
        expires_at=datetime.utcnow() + timedelta(days=settings.JWT_REFRESH_EXPIRATION_DAYS),
    )
    db.add(session)
    await db.commit()
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.JWT_EXPIRATION_HOURS * 3600,
        user_id=str(user.id),
        username=user.username,
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """
    User login
    
    Args:
        request: FastAPI request object
        form_data: OAuth2 form data (username/email and password)
        db: Database session
    
    Returns:
        TokenResponse: Access and refresh tokens
    
    Raises:
        HTTPException: If credentials are invalid
    """
    # Find user by username or email
    user_result = await db.execute(
        select(User).where(
            (User.username == form_data.username) | (User.email == form_data.username)
        )
    )
    user = user_result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    
    # Check if account is locked
    if user.is_locked:
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Account is locked. Please try again later.",
        )
    
    # Check if account is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )
    
    # Verify password
    if not verify_password(form_data.password, user.hashed_password):
        # Increment failed login attempts
        user.failed_login_attempts += 1
        
        # Lock account after 5 failed attempts
        if user.failed_login_attempts >= 5:
            user.locked_until = datetime.utcnow() + timedelta(minutes=15)
        
        await db.commit()
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    
    # Reset failed login attempts on successful login
    user.failed_login_attempts = 0
    user.last_login_at = datetime.utcnow()
    user.last_login_ip = request.client.host
    
    # Update status if pending verification
    if user.status == UserStatus.PENDING_VERIFICATION:
        user.status = UserStatus.ACTIVE
        user.is_verified = True
    
    await db.commit()
    
    # Create tokens
    access_token = create_access_token(
        subject=str(user.id),
        extra_data={"username": user.username, "email": user.email}
    )
    refresh_token = create_refresh_token(subject=str(user.id))
    
    # Create new session
    session = UserSession(
        user_id=user.id,
        session_token=access_token,
        refresh_token=refresh_token,
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent"),
        expires_at=datetime.utcnow() + timedelta(days=settings.JWT_REFRESH_EXPIRATION_DAYS),
    )
    db.add(session)
    await db.commit()
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.JWT_EXPIRATION_HOURS * 3600,
        user_id=str(user.id),
        username=user.username,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    refresh_data: RefreshTokenRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Refresh access token using refresh token
    
    Args:
        refresh_data: Refresh token data
        request: FastAPI request object
        db: Database session
    
    Returns:
        TokenResponse: New access and refresh tokens
    
    Raises:
        HTTPException: If refresh token is invalid
    """
    try:
        # Decode refresh token
        payload = decode_token(refresh_data.refresh_token)
        
        # Verify token type
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
            )
        
        user_id = payload.get("sub")
        
        # Find user
        user_result = await db.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one_or_none()
        
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive",
            )
        
        # Find and revoke old session
        old_session_result = await db.execute(
            select(UserSession).where(
                UserSession.refresh_token == refresh_data.refresh_token,
                UserSession.is_active == True,
            )
        )
        old_session = old_session_result.scalar_one_or_none()
        
        if old_session:
            old_session.is_active = False
            old_session.revoked_at = datetime.utcnow()
        
        # Create new tokens
        access_token = create_access_token(
            subject=str(user.id),
            extra_data={"username": user.username, "email": user.email}
        )
        new_refresh_token = create_refresh_token(subject=str(user.id))
        
        # Create new session
        new_session = UserSession(
            user_id=user.id,
            session_token=access_token,
            refresh_token=new_refresh_token,
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent"),
            expires_at=datetime.utcnow() + timedelta(days=settings.JWT_REFRESH_EXPIRATION_DAYS),
        )
        db.add(new_session)
        await db.commit()
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=new_refresh_token,
            token_type="bearer",
            expires_in=settings.JWT_EXPIRATION_HOURS * 3600,
            user_id=str(user.id),
            username=user.username,
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid refresh token: {str(e)}",
        )


@router.post("/logout")
async def logout(
    current_user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Logout user (revoke current session)
    
    Args:
        current_user_id: Current user ID from token
        db: Database session
    
    Returns:
        dict: Success message
    """
    # Find and revoke all active sessions for user
    sessions_result = await db.execute(
        select(UserSession).where(
            UserSession.user_id == current_user_id,
            UserSession.is_active == True,
        )
    )
    sessions = sessions_result.scalars().all()
    
    for session in sessions:
        session.is_active = False
        session.revoked_at = datetime.utcnow()
    
    await db.commit()
    
    return {"message": "Successfully logged out"}


@router.get("/me")
async def get_current_user(
    current_user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Get current user information
    
    Args:
        current_user_id: Current user ID from token
        db: Database session
    
    Returns:
        dict: User information
    """
    user_result = await db.execute(select(User).where(User.id == current_user_id))
    user = user_result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    return {
        "user_id": str(user.id),
        "email": user.email,
        "username": user.username,
        "full_name": user.full_name,
        "phone": user.phone,
        "status": user.status,
        "is_verified": user.is_verified,
        "created_at": user.created_at,
        "last_login_at": user.last_login_at,
    }


@router.post("/password-reset")
async def request_password_reset(
    reset_data: PasswordReset,
    db: AsyncSession = Depends(get_db),
):
    """
    Request password reset email
    
    Args:
        reset_data: Password reset request data
        db: Database session
    
    Returns:
        dict: Success message
    """
    # Find user by email
    user_result = await db.execute(select(User).where(User.email == reset_data.email))
    user = user_result.scalar_one_or_none()
    
    if not user:
        # Don't reveal if user exists or not
        return {"message": "If the email exists, a reset link has been sent"}
    
    # In a real implementation, send password reset email
    # For now, just return success message
    return {"message": "If the email exists, a reset link has been sent"}


@router.post("/password-reset/confirm")
async def confirm_password_reset(
    reset_data: PasswordResetConfirm,
    db: AsyncSession = Depends(get_db),
):
    """
    Confirm password reset with token
    
    Args:
        reset_data: Password reset confirmation data
        db: Database session
    
    Returns:
        dict: Success message
    """
    # In a real implementation, validate reset token and update password
    # For now, just return success message
    return {"message": "Password has been reset successfully"}