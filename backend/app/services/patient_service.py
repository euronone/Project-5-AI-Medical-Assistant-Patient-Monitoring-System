from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models.user import User
from app.models.patient import PatientProfile


def get_patients(
    db: Session,
    current_user: User,
    page: int = 1,
    per_page: int = 20,
    search: Optional[str] = None,
) -> dict:
    """
    Return a paginated list of patients.

    - Admins  → see all patients
    - Doctors → see only their assigned patients (primary_physician_id = doctor user id)
    """
    query = (
        db.query(PatientProfile)
        .join(User, PatientProfile.user_id == User.id)
        .filter(User.is_active == True)
    )

    if current_user.role == "doctor":
        query = query.filter(PatientProfile.primary_physician_id == current_user.id)

    if search:
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                User.first_name.ilike(term),
                User.last_name.ilike(term),
                User.email.ilike(term),
            )
        )

    total = query.count()
    patients = (
        query.order_by(User.last_name.asc(), User.first_name.asc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    return {"patients": patients, "total": total, "page": page, "per_page": per_page}


def get_patient_by_id(
    db: Session,
    patient_id: str,
    current_user: User,
) -> Optional[PatientProfile]:
    """
    Return a single patient profile with joined user info.

    - Patients → own profile only
    - Doctors  → their assigned patients
    - Admins   → anyone
    """
    patient = (
        db.query(PatientProfile)
        .join(User, PatientProfile.user_id == User.id)
        .filter(PatientProfile.id == patient_id)
        .first()
    )

    if patient is None:
        return None

    if current_user.role == "patient" and patient.user_id != current_user.id:
        return None

    if current_user.role == "doctor" and patient.primary_physician_id != current_user.id:
        return None

    return patient


def update_patient(
    db: Session,
    patient_id: str,
    data: dict,
    current_user: User,
) -> Optional[PatientProfile]:
    """Update allowed patient profile fields."""
    patient = get_patient_by_id(db, patient_id, current_user)
    if patient is None:
        return None

    profile_fields = {
        "gender", "blood_type", "height_cm", "weight_kg",
        "emergency_contact_name", "emergency_contact_phone",
        "insurance_provider", "insurance_policy_number",
    }
    user_fields = {"first_name", "last_name", "phone"}

    for field in profile_fields:
        if data.get(field) is not None:
            setattr(patient, field, data[field])

    for field in user_fields:
        if data.get(field) is not None:
            setattr(patient.user, field, data[field])

    db.commit()
    db.refresh(patient)
    return patient
