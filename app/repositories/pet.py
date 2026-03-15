from app.models.pet import Pet
from app.repositories.base import CRUDBase
from app.schemas.pet import PetCreate, PetUpdate

pet_repo = CRUDBase[Pet, PetCreate, PetUpdate](Pet)
