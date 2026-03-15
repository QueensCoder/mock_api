from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


class VisitCreate(BaseModel):
    pet_id: int
    owner_id: int
    visited_at: datetime
    reason: str | None = None
    notes: str | None = None
    status: str = "scheduled"

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        allowed = {"scheduled", "completed", "cancelled", "no_show"}
        if v not in allowed:
            raise ValueError(f"status must be one of {allowed}")
        return v


class VisitUpdate(BaseModel):
    reason: str | None = None
    notes: str | None = None
    status: str | None = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str | None) -> str | None:
        if v is None:
            return v
        allowed = {"scheduled", "completed", "cancelled", "no_show"}
        if v not in allowed:
            raise ValueError(f"status must be one of {allowed}")
        return v


class VisitResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    pet_id: int
    owner_id: int
    visited_at: datetime
    reason: str | None = None
    notes: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
