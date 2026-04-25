from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable

from fastapi import Request
from fastapi.responses import JSONResponse, Response

from app.contracts.v2.common import V2ErrorBody, V2ErrorEnvelope


class InMemoryRateLimiter:
    """Small per-process rate limiter for single-node trial deployments.

    Production multi-node deployments should replace this with Redis-backed
    rate limiting, but this gives the commercial trial a safe default guardrail.
    """

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


def client_rate_limit_key(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def build_rate_limit_middleware(
    limiter: InMemoryRateLimiter,
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
