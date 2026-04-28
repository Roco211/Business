from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from app.contracts.v2.common import V2DataEnvelope
from app.services.system_readiness import build_mock_guardrails_check

router = APIRouter(prefix="/api/v2", tags=["v2-system"])


class V2HealthData(BaseModel):
    status: str
    api_version: str


class V2ReadinessData(BaseModel):
    overall_status: str
    checks: list[dict[str, Any]]


@router.get("/health", response_model=V2DataEnvelope[V2HealthData])
def v2_health() -> V2DataEnvelope[V2HealthData]:
    return V2DataEnvelope(data=V2HealthData(status="ok", api_version="v2"))


@router.get("/system/readiness", response_model=V2DataEnvelope[V2ReadinessData])
def v2_system_readiness() -> V2DataEnvelope[V2ReadinessData]:
    checks = [build_mock_guardrails_check().as_dict()]
    overall_status = "degraded" if any(check["status"] == "degraded" for check in checks) else "ready"
    return V2DataEnvelope(data=V2ReadinessData(overall_status=overall_status, checks=checks))
