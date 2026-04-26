from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable
from typing import Protocol, runtime_checkable

from fastapi import Request
from fastapi.responses import JSONResponse, Response

from app.contracts.v2.common import V2ErrorBody, V2ErrorEnvelope
from app.core.config import Settings


@runtime_checkable
class RateLimiter(Protocol):
    def allow(self, key: str, now: float | None = None) -> bool: ...


class InMemoryRateLimiter:
    """Small per-process rate limiter for single-node trial deployments."""

    def __init__(self, limit_per_minute: int) -> None:
        self.limit_per_minute = max(0, limit_per_minute)
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str, now: float | None = None) -> bool:
        if self.limit_per_minute <= 0:
            return True
        current = time.monotonic() if now is None else now
        window_start = current - 60
        hits = self._hits[key]
        while hits and hits[0] < window_start:
            hits.popleft()
        if len(hits) >= self.limit_per_minute:
            return False
        hits.append(current)
        return True


class RedisRateLimiter:
    """Redis-backed fixed-window limiter for production multi-instance deployments.

    The Redis URL is kept inside the Redis client only and is never included in
    keys, details, or responses.
    """

    def __init__(
        self,
        limit_per_minute: int,
        *,
        redis_url: str | None = None,
        redis_client: object | None = None,
        key_prefix: str = "business:rate-limit",
    ) -> None:
        self.limit_per_minute = max(0, limit_per_minute)
        self.redis_url = redis_url or ""
        self.redis_client = redis_client
        self.key_prefix = key_prefix.strip(":") or "business:rate-limit"

    def _client(self):
        if self.redis_client is not None:
            return self.redis_client
        try:
            import redis  # type: ignore
        except Exception:
            return None
        if not self.redis_url.strip():
            return None
        self.redis_client = redis.Redis.from_url(self.redis_url, decode_responses=True)
        return self.redis_client

    def allow(self, key: str, now: float | None = None) -> bool:
        if self.limit_per_minute <= 0:
            return True
        client = self._client()
        if client is None:
            return False
        current = int(time.time() if now is None else now)
        window = current // 60
        redis_key = f"{self.key_prefix}:{key}:{window}"
        try:
            count = int(client.incr(redis_key))
            if count == 1:
                client.expire(redis_key, 70)
            return count <= self.limit_per_minute
        except Exception:
            return False


def create_rate_limiter(settings: Settings) -> RateLimiter:
    backend = settings.rate_limit_backend.strip().lower() or "memory"
    if backend == "redis":
        return RedisRateLimiter(settings.rate_limit_per_minute, redis_url=settings.redis_url)
    return InMemoryRateLimiter(settings.rate_limit_per_minute)


def client_rate_limit_key(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def build_rate_limit_middleware(
    limiter: RateLimiter,
) -> Callable[[Request, Callable[[Request], Awaitable[Response]]], Awaitable[Response]]:
    async def _rate_limit_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if request.url.path.startswith("/assets"):
            return await call_next(request)
        if not limiter.allow(client_rate_limit_key(request)):
            return JSONResponse(
                status_code=429,
                content=V2ErrorEnvelope(
                    error=V2ErrorBody(
                        code="rate_limited",
                        message="Too many requests, please retry later",
                    )
                ).model_dump(),
            )
        return await call_next(request)

    return _rate_limit_middleware


async def security_headers_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    return response
