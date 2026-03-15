from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class OwnerCreate(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    phone: str | None = None


class OwnerUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None


class OwnerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    first_name: str
    last_name: str
    email: str
    phone: str | None
    created_at: datetime
    updated_at: datetime
