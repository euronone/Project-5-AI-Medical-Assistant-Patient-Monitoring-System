from uuid import UUID
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.doctor_schema import DoctorProfileSchema, DoctorUpdateSchema, DoctorListSchema
from app.services import doctor_service

router = APIRouter(prefix="/doctors", tags=["Doctors"])


@router.get("", response_model=DoctorListSchema)
def list_doctors(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    specialization: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    available_for_telemedicine: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List doctors with optional filters.

    - **specialization** — partial match (e.g. "cardio")
    - **department** — partial match
    - **available_for_telemedicine** — true/false
    """
    result = doctor_service.get_doctors(
        db=db,
        page=page,
        per_page=per_page,
        specialization=specialization,
        department=department,
        available_for_telemedicine=available_for_telemedicine,
    )
    return result


@router.get("/{doctor_id}", response_model=DoctorProfileSchema)
def get_doctor(
    doctor_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get full doctor profile with joined user info."""
    doctor = doctor_service.get_doctor_by_id(db=db, doctor_id=str(doctor_id))

    if doctor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor not found",
        )

    return doctor


@router.put("/{doctor_id}", response_model=DoctorProfileSchema)
def update_doctor(
    doctor_id: UUID,
    body: DoctorUpdateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update doctor profile fields.

    - **doctor** → own profile only
    - **admin** → any doctor profile
    - **others** → 403
    """
    if current_user.role not in ("admin", "doctor"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    data = body.model_dump(exclude_none=True)

    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid fields provided",
        )

    doctor = doctor_service.update_doctor(
        db=db,
        doctor_id=str(doctor_id),
        data=data,
        current_user=current_user,
    )

    if doctor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor not found or access denied",
        )

    return doctor
