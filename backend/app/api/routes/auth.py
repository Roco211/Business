from fastapi import APIRouter, Depends

from app.contracts.auth import MockLoginData, MockLoginRequest
from app.contracts.common import DataEnvelope
from app.core.config import Settings, get_settings

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/mock-login", response_model=DataEnvelope[MockLoginData])
def mock_login(
    payload: MockLoginRequest,
    settings: Settings = Depends(get_settings),
) -> DataEnvelope[MockLoginData]:
    return DataEnvelope(
        data=MockLoginData(
            access_token="mock_owner_token",
            token_type="Bearer",
            owner_actor_id=settings.default_owner_actor_id,
            shop_id=payload.shop_id or settings.default_shop_id,
            shop_name="演示店铺",
        )
    )
