from app.models.patient import Patient
from app.repositories.base import CRUDBase
from app.schemas.patient import PatientCreate, PatientUpdate

patient_repo = CRUDBase[Patient, PatientCreate, PatientUpdate](Patient)
