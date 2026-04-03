from fastapi import APIRouter, Depends, Header, status
from fastapi.responses import JSONResponse

from app.contracts.common import DataEnvelope, ErrorBody, ErrorEnvelope
from app.contracts.session import SessionBootstrapData
from app.core.config import Settings, get_settings

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


@router.post(
    "/bootstrap",
    response_model=DataEnvelope[SessionBootstrapData],
    responses={401: {"model": ErrorEnvelope, "description": "Unauthorized"}},
)
def bootstrap_session(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> DataEnvelope[SessionBootstrapData]:
    if authorization != "Bearer mock_owner_token":
        payload = ErrorEnvelope(
            error=ErrorBody(
                code="unauthorized",
                message="Unauthorized",
                details=[],
            )
        )
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content=payload.model_dump(),
        )

    return DataEnvelope(
        data=SessionBootstrapData(
            session_id=settings.default_session_id,
            session_type="workgroup",
            title="数字员工工作群",
            participants=["xiaoya", "laoli"],
        )
    )
