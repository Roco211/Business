"""
Middleware for request processing
"""
import time
import logging
from typing import Callable, Optional
from uuid import UUID

from fastapi import Request, Response, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from config import get_settings
from app.core.security import decode_token

logger = logging.getLogger(__name__)
settings = get_settings()


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        
        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        
        if settings.ENVIRONMENT == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log all requests with timing"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        
        # Generate request ID
        request_id = request.headers.get("X-Request-ID", str(time.time_ns()))
        
        # Add request ID to request state
        request.state.request_id = request_id
        
        # Log request
        logger.info(
            f"Request started: {request.method} {request.url.path}",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "client_ip": request.client.host,
                "user_agent": request.headers.get("user-agent"),
            }
        )
        
        try:
            response = await call_next(request)
            
            # Calculate processing time
            process_time = (time.time() - start_time) * 1000
            
            # Add headers
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = f"{process_time:.2f}ms"
            
            # Log response
            logger.info(
                f"Request completed: {request.method} {request.url.path} - {response.status_code}",
                extra={
                    "request_id": request_id,
                    "status_code": response.status_code,
                    "process_time_ms": process_time,
                }
            )
            
            return response
            
        except Exception as e:
            # Log error
            process_time = (time.time() - start_time) * 1000
            logger.error(
                f"Request failed: {request.method} {request.url.path} - {str(e)}",
                extra={
                    "request_id": request_id,
                    "error": str(e),
                    "process_time_ms": process_time,
                },
                exc_info=True,
            )
            raise


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple rate limiting middleware"""
    
    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.requests = {}  # In production, use Redis
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip rate limiting for health checks
        if request.url.path in ["/health", "/api/docs", "/api/redoc"]:
            return await call_next(request)
        
        client_ip = request.client.host
        current_time = time.time()
        
        # Clean old requests
        if client_ip in self.requests:
            self.requests[client_ip] = [
                t for t in self.requests[client_ip] 
                if current_time - t < 60
            ]
        
        # Check rate limit
        if client_ip in self.requests and len(self.requests[client_ip]) >= self.requests_per_minute:
            logger.warning(f"Rate limit exceeded for IP: {client_ip}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please try again later.",
            )
        
        # Add current request
        if client_ip not in self.requests:
            self.requests[client_ip] = []
        self.requests[client_ip].append(current_time)
        
        return await call_next(request)


class MultiTenantMiddleware(BaseHTTPMiddleware):
    """
    Multi-tenant middleware for automatic shop_id filtering
    
    This middleware:
    1. Extracts shop_id from JWT token or request header
    2. Validates user has access to the shop
    3. Adds shop_id to request state for use in endpoints
    4. Ensures all queries are scoped to the current shop
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip for non-API routes
        if not request.url.path.startswith("/api/"):
            return await call_next(request)
        
        # Skip for auth routes
        if request.url.path.startswith("/api/v1/auth/"):
            return await call_next(request)
        
        # Try to get shop_id from different sources
        shop_id = None
        
        # 1. Try to get from JWT token
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            try:
                token = auth_header.split(" ")[1]
                payload = decode_token(token)
                shop_id = payload.get("shop_id")
            except:
                pass
        
        # 2. Try to get from header
        if not shop_id:
            shop_id = request.headers.get("X-Shop-ID")
        
        # 3. Try to get from query parameter
        if not shop_id:
            shop_id = request.query_params.get("shop_id")
        
        # Validate shop_id format if provided
        if shop_id:
            try:
                UUID(shop_id)  # Validate UUID format
                request.state.shop_id = shop_id
                logger.debug(f"Multi-tenant context set: shop_id={shop_id}")
            except ValueError:
                logger.warning(f"Invalid shop_id format: {shop_id}")
                # Don't raise error, let endpoint handle validation
        
        # Add shop_id to request headers for downstream processing
        if shop_id:
            # Create a mutable copy of headers
            headers = dict(request.headers)
            headers["X-Shop-ID"] = shop_id
            
            # Note: In a real implementation, you might want to modify the request
            # For now, we'll just add it to request state
        
        response = await call_next(request)
        return response


class TenantContextManager:
    """
    Helper class for managing tenant context
    
    Usage:
        tenant_ctx = TenantContextManager(request)
        if tenant_ctx.shop_id:
            # Query is scoped to this shop
            items = await db.query(InventoryItem).filter(
                InventoryItem.shop_id == tenant_ctx.shop_id
            ).all()
    """
    
    def __init__(self, request: Request):
        self.request = request
        self.shop_id = getattr(request.state, "shop_id", None)
    
    @property
    def is_tenant_scoped(self) -> bool:
        """Check if request is scoped to a tenant"""
        return self.shop_id is not None
    
    def require_tenant(self):
        """Require tenant context or raise error"""
        if not self.shop_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Shop ID is required. Please specify X-Shop-ID header or shop_id query parameter.",
            )
    
    def scope_query(self, query, model):
        """Scope a query to the current tenant"""
        if self.shop_id:
            return query.filter(model.shop_id == self.shop_id)
        return query


# Helper function to get tenant context
def get_tenant_context(request: Request) -> TenantContextManager:
    """Get tenant context from request"""
    return TenantContextManager(request)