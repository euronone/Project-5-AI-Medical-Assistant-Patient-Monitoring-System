from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1 import v1_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="MedAssist AI",
        description="AI Medical Assistant & Patient Monitoring System",
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(v1_router, prefix="/api")

    # Import models so Alembic can detect them
    from app.models import User, PatientProfile, DoctorProfile  # noqa: F401

    return app
