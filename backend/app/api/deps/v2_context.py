from dataclasses import dataclass
from typing import Callable

from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.models import V2ContextSession
from app.services.v2_identity import resolve_v2_auth_session
from app.services.v2_time import utc_now_naive


class V2UnauthorizedError(Exception):
    pass


@dataclass(frozen=True)
class V2AuthenticatedAccount:
    auth_session_id: str
    account_id: str


def require_v2_authenticated_account(
    authorization: str | None = Header(default=None),
    db_session: Session = Depends(get_db_session),
) -> V2AuthenticatedAccount:
    if authorization is None:
        raise V2UnauthorizedError

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise V2UnauthorizedError

    resolved = resolve_v2_auth_session(db_session, token)
    if resolved is None:
        raise V2UnauthorizedError

    return V2AuthenticatedAccount(
        auth_session_id=resolved.auth_session_id,
        account_id=resolved.account_id,
    )


class V2ContextRequiredError(Exception):
    pass


class V2ForbiddenError(Exception):
    def __init__(self, permission: str) -> None:
        self.permission = permission
        super().__init__(permission)


@dataclass(frozen=True)
class V2ExecutionContext:
    account_id: str
    tenant_id: str
    shop_id: str
    membership_id: str
    role_key: str
    permissions: tuple[str, ...]
    context_session_id: str


def require_v2_execution_context(
    x_context_token: str | None = Header(default=None, alias="X-Context-Token"),
    db_session: Session = Depends(get_db_session),
) -> V2ExecutionContext:
    if not x_context_token:
        raise V2ContextRequiredError

    context_session = db_session.scalar(
        select(V2ContextSession).where(
            V2ContextSession.context_session_id == x_context_token,
            V2ContextSession.status == "active",
            V2ContextSession.expires_at > utc_now_naive(),
        )
    )
    if context_session is None:
        raise V2ContextRequiredError

    return V2ExecutionContext(
        account_id=context_session.account_id,
        tenant_id=context_session.tenant_id,
        shop_id=context_session.shop_id,
        membership_id=context_session.membership_id,
        role_key=str(context_session.permission_snapshot["role_key"]),
        permissions=tuple(context_session.permission_snapshot["permissions"]),
        context_session_id=context_session.context_session_id,
    )


def has_v2_permission(context: V2ExecutionContext, permission: str) -> bool:
    return permission in context.permissions


def ensure_v2_permission(context: V2ExecutionContext, permission: str) -> None:
    if not has_v2_permission(context, permission):
        raise V2ForbiddenError(permission)


def require_v2_permission(permission: str) -> Callable[[V2ExecutionContext], V2ExecutionContext]:
    def _dependency(
        context: V2ExecutionContext = Depends(require_v2_execution_context),
    ) -> V2ExecutionContext:
        ensure_v2_permission(context, permission)
        return context

    return _dependency
