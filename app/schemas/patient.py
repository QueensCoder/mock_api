from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PatientCreate(BaseModel):
    pet_id: int
    condition: str
    notes: str | None = None
    visited_at: datetime


class PatientUpdate(BaseModel):
    condition: str | None = None
    notes: str | None = None
    visited_at: datetime | None = None


class PatientResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    pet_id: int
    condition: str
    notes: str | None
    visited_at: datetime
    created_at: datetime
    updated_at: datetime
