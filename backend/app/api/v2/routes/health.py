from fastapi import APIRouter
from pydantic import BaseModel

from app.contracts.v2.common import V2DataEnvelope

router = APIRouter(prefix="/api/v2", tags=["v2-system"])


class V2HealthData(BaseModel):
    status: str
    api_version: str


@router.get("/health", response_model=V2DataEnvelope[V2HealthData])
def v2_health() -> V2DataEnvelope[V2HealthData]:
    return V2DataEnvelope(data=V2HealthData(status="ok", api_version="v2"))
