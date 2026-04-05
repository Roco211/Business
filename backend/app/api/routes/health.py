from fastapi import APIRouter, Depends, Header, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.contracts.common import DataEnvelope, ErrorBody, ErrorEnvelope
from app.contracts.system import DemoBootstrapSummaryData, HealthResponse
from app.db.session import get_db_session
from app.services.demo_state import bootstrap_demo_state

router = APIRouter(tags=["system"])


def _unauthorized() -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content=ErrorEnvelope(
            error=ErrorBody(code="unauthorized", message="Unauthorized", details=[])
        ).model_dump(),
    )


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.post("/api/v1/system/demo/bootstrap", response_model=DataEnvelope[DemoBootstrapSummaryData])
def post_demo_bootstrap(
    authorization: str | None = Header(default=None),
    db_session: Session = Depends(get_db_session),
) -> DataEnvelope[DemoBootstrapSummaryData] | JSONResponse:
    if authorization != "Bearer mock_owner_token":
        return _unauthorized()

    summary = bootstrap_demo_state(db_session)
    return DataEnvelope(
        data=DemoBootstrapSummaryData(
            **summary.to_dict(),
        )
    )
