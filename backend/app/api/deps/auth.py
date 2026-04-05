from dataclasses import dataclass

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.services.auth_sessions import resolve_auth_session


class AuthUnauthorizedError(Exception):
    pass


@dataclass(frozen=True)
class AuthenticatedContext:
    actor_id: str
    shop_id: str
    auth_session_id: str
    role: str


def require_authenticated_context(
    authorization: str | None = Header(default=None),
    db_session: Session = Depends(get_db_session),
) -> AuthenticatedContext:
    if authorization is None:
        raise AuthUnauthorizedError

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise AuthUnauthorizedError

    resolved = resolve_auth_session(db_session, token)
    if resolved is None:
        raise AuthUnauthorizedError

    return AuthenticatedContext(
        actor_id=resolved.actor_id,
        shop_id=resolved.shop_id,
        auth_session_id=resolved.auth_session_id,
        role=resolved.role,
    )
