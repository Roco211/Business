from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps.auth import AuthenticatedContext, require_authenticated_context
from app.core.config import get_settings
from app.contracts.common import DataEnvelope, ErrorBody, ErrorEnvelope
from app.contracts.system import (
    DemoBootstrapSummaryData,
    HealthResponse,
    PilotControlData,
    PilotControlMutationRequest,
    PilotSummaryData,
    SystemReadinessData,
)
from app.db.session import get_db_session
from app.models import PilotControl
from app.services.demo_state import bootstrap_demo_state
from app.services.pilot_control import (
    PilotControlTransitionError,
    PilotControlValidationError,
    get_or_create_pilot_control,
    mutate_pilot_control,
)
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


def _error_response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=ErrorEnvelope(
            error=ErrorBody(code=code, message=message, details=[])
        ).model_dump(),
    )


def _to_pilot_control_data(pilot_control: PilotControl) -> PilotControlData:
    return PilotControlData.model_validate(pilot_control, from_attributes=True)


def _ensure_pilot_control_with_retry(
    db_session: Session,
    *,
    shop_id: str,
    trial_provider_profile: str,
) -> PilotControl:
    pilot_control, changed = get_or_create_pilot_control(
        db_session,
        shop_id=shop_id,
        trial_provider_profile=trial_provider_profile,
    )
    if not changed:
        return pilot_control

    try:
        db_session.commit()
        return pilot_control
    except IntegrityError:
        db_session.rollback()
        pilot_control, changed = get_or_create_pilot_control(
            db_session,
            shop_id=shop_id,
            trial_provider_profile=trial_provider_profile,
        )
        if changed:
            db_session.commit()
        return pilot_control


def _mutate_pilot_control_with_retry(
    db_session: Session,
    *,
    shop_id: str,
    actor_id: str,
    trial_provider_profile: str,
    payload: PilotControlMutationRequest,
) -> PilotControl:
    try:
        pilot_control, changed = mutate_pilot_control(
            db_session,
            shop_id=shop_id,
            actor_id=actor_id,
            trial_provider_profile=trial_provider_profile,
            cutover_mode=payload.cutover_mode,
            approved_calibration_artifact_id=payload.approved_calibration_artifact_id,
            approved_calibration_report_path=payload.approved_calibration_report_path,
            notes=payload.notes,
        )
        if changed:
            db_session.commit()
        return pilot_control
    except IntegrityError:
        db_session.rollback()
        pilot_control, changed = mutate_pilot_control(
            db_session,
            shop_id=shop_id,
            actor_id=actor_id,
            trial_provider_profile=trial_provider_profile,
            cutover_mode=payload.cutover_mode,
            approved_calibration_artifact_id=payload.approved_calibration_artifact_id,
            approved_calibration_report_path=payload.approved_calibration_report_path,
            notes=payload.notes,
        )
        if changed:
            db_session.commit()
        return pilot_control


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get(
    "/api/v1/system/readiness",
    response_model=DataEnvelope[SystemReadinessData],
    responses={status.HTTP_401_UNAUTHORIZED: {"model": ErrorEnvelope, "description": "Unauthorized"}},
)
def get_system_readiness(
    auth: AuthenticatedContext = Depends(require_authenticated_context),
    db_session: Session = Depends(get_db_session),
) -> DataEnvelope[SystemReadinessData]:
    settings = get_settings()
    pilot_control = _ensure_pilot_control_with_retry(
        db_session,
        shop_id=auth.shop_id,
        trial_provider_profile=settings.trial_provider_profile.strip(),
    )
    readiness_data: SystemReadinessData = build_system_readiness(settings).model_copy(
        update={
            "trial_provider_profile": pilot_control.trial_provider_profile,
            "approved_calibration_artifact_id": pilot_control.approved_calibration_artifact_id,
            "cutover_mode": pilot_control.cutover_mode,
        }
    )
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


@router.get(
    "/api/v1/system/pilot-control",
    response_model=DataEnvelope[PilotControlData],
    responses={status.HTTP_401_UNAUTHORIZED: {"model": ErrorEnvelope, "description": "Unauthorized"}},
)
def get_pilot_control(
    auth: AuthenticatedContext = Depends(require_authenticated_context),
    db_session: Session = Depends(get_db_session),
) -> DataEnvelope[PilotControlData]:
    settings = get_settings()
    pilot_control = _ensure_pilot_control_with_retry(
        db_session,
        shop_id=auth.shop_id,
        trial_provider_profile=settings.trial_provider_profile.strip(),
    )
    return DataEnvelope(data=_to_pilot_control_data(pilot_control))


@router.post(
    "/api/v1/system/pilot-control",
    response_model=DataEnvelope[PilotControlData],
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorEnvelope, "description": "Unauthorized"},
        status.HTTP_409_CONFLICT: {"model": ErrorEnvelope, "description": "Invalid cutover transition"},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": ErrorEnvelope, "description": "Validation error"},
    },
)
def post_pilot_control(
    payload: PilotControlMutationRequest,
    auth: AuthenticatedContext = Depends(require_authenticated_context),
    db_session: Session = Depends(get_db_session),
) -> DataEnvelope[PilotControlData] | JSONResponse:
    if (
        payload.cutover_mode is None
        and payload.approved_calibration_artifact_id is None
        and payload.approved_calibration_report_path is None
        and payload.notes is None
    ):
        return _error_response(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "validation_error",
            "At least one mutable pilot-control field is required.",
        )

    settings = get_settings()
    try:
        pilot_control = _mutate_pilot_control_with_retry(
            db_session,
            shop_id=auth.shop_id,
            actor_id=auth.actor_id,
            trial_provider_profile=settings.trial_provider_profile.strip(),
            payload=payload,
        )
    except PilotControlValidationError:
        db_session.rollback()
        return _error_response(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "invalid_cutover_mode",
            "cutover_mode is invalid",
        )
    except PilotControlTransitionError:
        db_session.rollback()
        return _error_response(
            status.HTTP_409_CONFLICT,
            "invalid_cutover_mode_transition",
            "cutover_mode transition is not allowed",
        )
    except Exception:
        db_session.rollback()
        raise

    return DataEnvelope(data=_to_pilot_control_data(pilot_control))
