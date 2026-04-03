from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.contracts.common import DataEnvelope
from app.contracts.session import SessionBootstrapData
from app.core.config import Settings, get_settings

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


@router.post("/bootstrap", response_model=DataEnvelope[SessionBootstrapData])
def bootstrap_session(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> DataEnvelope[SessionBootstrapData]:
    if authorization != "Bearer mock_owner_token":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    return DataEnvelope(
        data=SessionBootstrapData(
            session_id=settings.default_session_id,
            session_type="workgroup",
            title="数字员工工作群",
            participants=["xiaoya", "laoli"],
        )
    )
