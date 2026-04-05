from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.contracts.auth import LoginData, LoginRequest, MockLoginData, MockLoginRequest
from app.contracts.common import DataEnvelope, ErrorBody, ErrorEnvelope
from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.services.auth_sessions import (
    authenticate_owner,
    issue_auth_session,
    resolve_owner_membership_and_shop,
)
from app.services.bootstrap import ensure_default_owner_membership, ensure_default_shop

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _unauthorized() -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content=ErrorEnvelope(
            error=ErrorBody(
                code="unauthorized",
                message="Unauthorized",
                details=[],
            )
        ).model_dump(),
    )


@router.post("/login", response_model=DataEnvelope[LoginData], responses={401: {"model": ErrorEnvelope}})
def login(
    payload: LoginRequest,
    settings: Settings = Depends(get_settings),
    db_session: Session = Depends(get_db_session),
) -> DataEnvelope[LoginData] | JSONResponse:
    shop = ensure_default_shop(db_session)
    ensure_default_owner_membership(db_session, shop)
    owner = authenticate_owner(db_session, payload.email, payload.password)
    if owner is None:
        return _unauthorized()

    membership_and_shop = resolve_owner_membership_and_shop(db_session, owner.actor_id)
    if membership_and_shop is None:
        return _unauthorized()

    membership, shop = membership_and_shop
    issued_session = issue_auth_session(
        db_session,
        actor_id=owner.actor_id,
        shop_id=membership.shop_id,
        ttl_minutes=settings.auth_session_ttl_minutes,
    )
    return DataEnvelope(
        data=LoginData(
            access_token=issued_session.access_token,
            token_type="Bearer",
            owner_actor_id=owner.actor_id,
            shop_id=shop.shop_id,
            shop_name=shop.name,
        )
    )


@router.post("/mock-login", response_model=DataEnvelope[MockLoginData])
def mock_login(
    payload: MockLoginRequest,
    settings: Settings = Depends(get_settings),
    db_session: Session = Depends(get_db_session),
) -> DataEnvelope[MockLoginData]:
    shop = ensure_default_shop(db_session)

    return DataEnvelope(
        data=MockLoginData(
            access_token="mock_owner_token",
            token_type="Bearer",
            owner_actor_id=settings.default_owner_actor_id,
            shop_id=shop.shop_id,
            shop_name=shop.name,
        )
    )
