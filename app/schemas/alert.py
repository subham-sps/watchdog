import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class AlertRead(BaseModel):
    id: uuid.UUID
    source_id: Optional[uuid.UUID]
    rule_name: str
    severity: str
    message: str
    acknowledged: bool
    acknowledged_at: Optional[datetime]
    created_at: datetime
    resolved_at: Optional[datetime]

    model_config = {"from_attributes": True}


class MetricsSummary(BaseModel):
    total_events: int
    events_last_hour: int
    events_by_level: dict[str, int]
    active_alerts: int
    total_sources: int
