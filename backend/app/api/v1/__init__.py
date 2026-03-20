from fastapi import APIRouter
from app.api.v1.patients import router as patients_router
from app.api.v1.doctors import router as doctors_router
from app.api.v1.health import router as health_router

v1_router = APIRouter(prefix="/v1")

v1_router.include_router(patients_router)
v1_router.include_router(doctors_router)
v1_router.include_router(health_router)
