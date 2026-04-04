from fastapi import APIRouter, Depends, Header, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.contracts.common import DataEnvelope, ErrorBody, ErrorEnvelope
from app.contracts.session import SessionBootstrapData
from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.services.bootstrap import ensure_default_context

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


@router.post(
    "/bootstrap",
    response_model=DataEnvelope[SessionBootstrapData],
    responses={401: {"model": ErrorEnvelope, "description": "Unauthorized"}},
)
def bootstrap_session(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
    db_session: Session = Depends(get_db_session),
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

    context = ensure_default_context(db_session)

    return DataEnvelope(
        data=SessionBootstrapData(
            session_id=context.session.session_id,
            session_type=context.session.session_type,
            title=context.session.title,
            participants=context.session.participants,
        )
    )
