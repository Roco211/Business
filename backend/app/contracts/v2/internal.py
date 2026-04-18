from datetime import datetime

from pydantic import BaseModel


class V2WorkerHealthData(BaseModel):
    tenant_id: str
    shop_id: str
    pending_count: int
    processing_count: int
    completed_count: int
    failed_count: int
    oldest_pending_at: datetime | None
    oldest_available_pending_at: datetime | None


class V2ProjectionReplayRequest(BaseModel):
    inventory_item_id: str | None = None


class V2ProjectionReplayData(BaseModel):
    tenant_id: str
    shop_id: str
    inventory_item_id: str | None
    replayed_item_count: int
    replayed_snapshot_count: int
    deleted_snapshot_count: int
    ledger_event_count: int
    replayed_at: datetime
