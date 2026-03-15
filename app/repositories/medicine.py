from app.models.medicine import Medicine
from app.repositories.base import CRUDBase
from app.schemas.medicine import MedicineCreate, MedicineUpdate

medicine_repo = CRUDBase[Medicine, MedicineCreate, MedicineUpdate](Medicine)
