from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.contracts.auth import MockLoginData, MockLoginRequest
from app.contracts.common import DataEnvelope
from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.services.bootstrap import ensure_default_shop

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


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
