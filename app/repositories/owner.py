from app.models.owner import Owner
from app.repositories.base import CRUDBase
from app.schemas.owner import OwnerCreate, OwnerUpdate

owner_repo = CRUDBase[Owner, OwnerCreate, OwnerUpdate](Owner)
