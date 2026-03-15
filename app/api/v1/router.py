from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    events,
    health,
    medicines,
    owners,
    patients,
    pet_search,
    pets,
    users,
    visits,
)

api_router = APIRouter()

api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(events.router, tags=["events"])
api_router.include_router(owners.router, prefix="/owners", tags=["owners"])
api_router.include_router(pets.router, prefix="/pets", tags=["pets"])
api_router.include_router(patients.router, prefix="/patients", tags=["patients"])
api_router.include_router(medicines.router, prefix="/medicines", tags=["medicines"])
api_router.include_router(pet_search.router, prefix="/search", tags=["search"])
api_router.include_router(visits.router, prefix="/visits", tags=["visits"])
