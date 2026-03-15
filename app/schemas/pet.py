from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class PetCreate(BaseModel):
    owner_id: int
    name: str
    species: str
    breed: str | None = None
    date_of_birth: date | None = None


class PetUpdate(BaseModel):
    owner_id: int | None = None
    name: str | None = None
    species: str | None = None
    breed: str | None = None
    date_of_birth: date | None = None


class PetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int
    name: str
    species: str
    breed: str | None
    date_of_birth: date | None
    created_at: datetime
    updated_at: datetime
