from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MedicineCreate(BaseModel):
    name: str
    description: str | None = None
    dosage: str | None = None
    unit: str | None = None


class MedicineUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    dosage: str | None = None
    unit: str | None = None


class MedicineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    dosage: str | None
    unit: str | None
    created_at: datetime
    updated_at: datetime
