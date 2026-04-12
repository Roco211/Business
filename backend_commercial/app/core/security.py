"""
Security utilities for authentication and authorization
"""
import secrets
from datetime import datetime, timedelta
from typing import Optional, Union, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import ValidationError

from config import get_settings

settings = get_settings()

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT Bearer token
security_scheme = HTTPBearer()


def generate_secret_key(length: int = 32) -> str:
    """Generate a secure random secret key"""
    return secrets.token_urlsafe(length)


def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    subject: Union[str, Any],
    expires_delta: Optional[timedelta] = None,
    extra_data: Optional[dict] = None
) -> str:
    """
    Create JWT access token
    
    Args:
        subject: Token subject (usually user ID)
        expires_delta: Optional custom expiration
        extra_data: Additional data to include in token
    
    Returns:
        JWT token string
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            hours=settings.JWT_EXPIRATION_HOURS
        )
    
    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "type": "access",
        "iat": datetime.utcnow()
    }
    
    if extra_data:
        to_encode.update(extra_data)
    
    return jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )


def create_refresh_token(
    subject: Union[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create JWT refresh token
    
    Args:
        subject: Token subject (usually user ID)
        expires_delta: Optional custom expiration
    
    Returns:
        JWT refresh token string
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            days=settings.JWT_REFRESH_EXPIRATION_DAYS
        )
    
    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "type": "refresh",
        "iat": datetime.utcnow()
    }
    
    return jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )


def decode_token(token: str) -> dict:
    """
    Decode and validate JWT token
    
    Args:
        token: JWT token string
    
    Returns:
        Decoded token payload
    
    Raises:
        HTTPException: If token is invalid
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme)
) -> str:
    """
    Extract user ID from JWT token
    
    Args:
        credentials: HTTP bearer credentials
    
    Returns:
        User ID string
    
    Raises:
        HTTPException: If token is invalid
    """
    try:
        payload = decode_token(credentials.credentials)
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing subject",
            )
        return user_id
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication credentials: {str(e)}",
        )


def get_current_active_user(
    user_id: str = Depends(get_current_user_id)
) -> dict:
    """
    Get current active user (simplified version)
    
    In a real implementation, this would fetch user from database
    """
    # This is a placeholder - in real implementation, fetch from DB
    return {
        "user_id": user_id,
        "is_active": True,
        "is_superuser": False
    }


def require_superuser(
    current_user: dict = Depends(get_current_active_user)
) -> dict:
    """
    Require superuser privileges
    
    Args:
        current_user: Current authenticated user
    
    Returns:
        User dict if superuser
    
    Raises:
        HTTPException: If not superuser
    """
    if not current_user.get("is_superuser"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superuser privileges required",
        )
    return current_user


class TokenData:
    """Token data model"""
    def __init__(
        self,
        user_id: str,
        token_type: str = "access",
        exp: Optional[datetime] = None,
        **kwargs
    ):
        self.user_id = user_id
        self.token_type = token_type
        self.exp = exp
        for key, value in kwargs.items():
            setattr(self, key, value)


def validate_token_type(token: str, expected_type: str) -> TokenData:
    """
    Validate token type and return token data
    
    Args:
        token: JWT token
        expected_type: Expected token type (access/refresh)
    
    Returns:
        TokenData instance
    
    Raises:
        HTTPException: If token type doesn't match
    """
    try:
        payload = decode_token(token)
        token_type = payload.get("type")
        
        if token_type != expected_type:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token type: expected {expected_type}",
            )
        
        return TokenData(**payload)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token validation failed: {str(e)}",
        )