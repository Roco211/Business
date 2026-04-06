from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps.auth import AuthenticatedContext, require_authenticated_context
from app.core.config import get_settings
from app.contracts.common import DataEnvelope, ErrorBody, ErrorEnvelope
from app.contracts.system import (
    DemoBootstrapSummaryData,
    HealthResponse,
    PilotSummaryData,
    SystemReadinessData,
)
from app.db.session import get_db_session
from app.services.demo_state import bootstrap_demo_state
from app.services.pilot_summary import build_pilot_summary
from app.services.system_readiness import build_system_readiness

router = APIRouter(tags=["system"])


def _unauthorized() -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content=ErrorEnvelope(
            error=ErrorBody(code="unauthorized", message="Unauthorized", details=[])
        ).model_dump(),
    )


def _not_found() -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content=ErrorEnvelope(
            error=ErrorBody(code="shop_not_found", message="Shop not found", details=[])
        ).model_dump(),
    )


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get(
    "/api/v1/system/readiness",
    response_model=DataEnvelope[SystemReadinessData],
    responses={status.HTTP_401_UNAUTHORIZED: {"model": ErrorEnvelope, "description": "Unauthorized"}},
)
def get_system_readiness(
    _: AuthenticatedContext = Depends(require_authenticated_context),
) -> DataEnvelope[SystemReadinessData]:
    settings = get_settings()
    readiness_data: SystemReadinessData = build_system_readiness(settings)
    return DataEnvelope(data=readiness_data)


@router.get(
    "/api/v1/system/pilot-summary",
    response_model=DataEnvelope[PilotSummaryData],
    responses={status.HTTP_401_UNAUTHORIZED: {"model": ErrorEnvelope, "description": "Unauthorized"}},
)
def get_pilot_summary(
    auth: AuthenticatedContext = Depends(require_authenticated_context),
    db_session: Session = Depends(get_db_session),
    hours: int = Query(default=24, ge=1, le=168),
) -> DataEnvelope[PilotSummaryData]:
    settings = get_settings()
    return DataEnvelope(
        data=build_pilot_summary(
            db_session,
            shop_id=auth.shop_id,
            hours=hours,
            trial_provider_profile=settings.trial_provider_profile.strip(),
        )
    )


@router.post("/api/v1/system/demo/bootstrap", response_model=DataEnvelope[DemoBootstrapSummaryData])
def post_demo_bootstrap(
    auth: AuthenticatedContext = Depends(require_authenticated_context),
    db_session: Session = Depends(get_db_session),
) -> DataEnvelope[DemoBootstrapSummaryData] | JSONResponse:
    settings = get_settings()
    if auth.shop_id != settings.default_shop_id:
        return _not_found()
    summary = bootstrap_demo_state(db_session)
    return DataEnvelope(
        data=DemoBootstrapSummaryData(
            **summary.to_dict(),
        )
    )
