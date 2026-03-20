from uuid import UUID
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_roles
from app.models.user import User
from app.schemas.patient_schema import PatientProfileSchema, PatientUpdateSchema, PatientListSchema
from app.services import patient_service

router = APIRouter(prefix="/patients", tags=["Patients"])


@router.get("", response_model=PatientListSchema)
def list_patients(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List patients with pagination and optional search.

    - **admin** → all patients
    - **doctor** → their assigned patients only
    - **patient / nurse** → 403
    """
    if current_user.role not in ("admin", "doctor"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    result = patient_service.get_patients(
        db=db,
        current_user=current_user,
        page=page,
        per_page=per_page,
        search=search,
    )
    return result


@router.get("/{patient_id}", response_model=PatientProfileSchema)
def get_patient(
    patient_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get full patient profile with joined user info.

    - **patient** → own profile only
    - **doctor** → their assigned patients
    - **admin** → any patient
    """
    if current_user.role not in ("admin", "doctor", "patient"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    patient = patient_service.get_patient_by_id(
        db=db,
        patient_id=str(patient_id),
        current_user=current_user,
    )

    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found or access denied",
        )

    return patient


@router.put("/{patient_id}", response_model=PatientProfileSchema)
def update_patient(
    patient_id: UUID,
    body: PatientUpdateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update patient profile fields.

    - **patient** → own profile only
    - **admin** → any patient profile
    - **doctor** → 403 (read-only access)
    """
    if current_user.role not in ("admin", "patient"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    data = body.model_dump(exclude_none=True)

    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid fields provided",
        )

    patient = patient_service.update_patient(
        db=db,
        patient_id=str(patient_id),
        data=data,
        current_user=current_user,
    )

    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found or access denied",
        )

    return patient
