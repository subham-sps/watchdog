import uuid
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, field_validator

VALID_LEVELS = {"debug", "info", "warning", "error", "critical"}


class SourceCreate(BaseModel):
    name: str
    description: Optional[str] = None


class SourceRead(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class EventCreate(BaseModel):
    source_id: Optional[uuid.UUID] = None
    level: str = "info"
    message: str
    payload: Optional[dict[str, Any]] = None
    occurred_at: Optional[datetime] = None
    fingerprint: Optional[str] = None

    @field_validator("level")
    @classmethod
    def validate_level(cls, v: str) -> str:
        v = v.lower()
        if v not in VALID_LEVELS:
            raise ValueError(f"level must be one of {sorted(VALID_LEVELS)}")
        return v

    @field_validator("message")
    @classmethod
    def message_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("message must not be empty")
        return v


class EventRead(BaseModel):
    id: uuid.UUID
    source_id: Optional[uuid.UUID]
    level: str
    message: str
    payload: Optional[dict[str, Any]]
    occurred_at: datetime
    fingerprint: Optional[str]

    model_config = {"from_attributes": True}
