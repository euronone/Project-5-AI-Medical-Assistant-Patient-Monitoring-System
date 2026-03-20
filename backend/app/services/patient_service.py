from typing import Optional
from sqlalchemy import or_
from app.extensions import db
from app.models.user import User
from app.models.patient import PatientProfile


def get_patients(
    current_user: User,
    page: int = 1,
    per_page: int = 20,
    search: Optional[str] = None,
) -> dict:
    """
    Return a paginated list of patients.

    - Admins  → see all patients
    - Doctors → see only their assigned patients (primary_physician_id = doctor user id)
    - Others  → forbidden (handled at route level)
    """
    query = (
        db.session.query(PatientProfile)
        .join(User, PatientProfile.user_id == User.id)
        .filter(User.is_active == True)
    )

    # Role-based filtering
    if current_user.role == "doctor":
        query = query.filter(PatientProfile.primary_physician_id == current_user.id)

    # Search across first name, last name, email
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

    return {
        "patients": patients,
        "total": total,
        "page": page,
        "per_page": per_page,
    }


def get_patient_by_id(
    patient_id: str,
    current_user: User,
) -> Optional[PatientProfile]:
    """
    Return a single patient profile with joined user info.

    - Patients  → can only fetch their own profile
    - Doctors   → can fetch their assigned patients
    - Admins    → can fetch anyone
    """
    patient = (
        db.session.query(PatientProfile)
        .join(User, PatientProfile.user_id == User.id)
        .filter(PatientProfile.id == patient_id)
        .first()
    )

    if patient is None:
        return None

    # Access control
    if current_user.role == "patient":
        if patient.user_id != current_user.id:
            return None  # Route layer converts None → 403

    if current_user.role == "doctor":
        if patient.primary_physician_id != current_user.id:
            return None

    return patient


def update_patient(
    patient_id: str,
    data: dict,
    current_user: User,
) -> Optional[PatientProfile]:
    """
    Update patient profile fields and optionally the linked user fields.

    Returns the updated PatientProfile or None if not found / not allowed.
    """
    patient = get_patient_by_id(patient_id, current_user)
    if patient is None:
        return None

    # Fields that belong on PatientProfile
    profile_fields = {
        "gender",
        "blood_type",
        "height_cm",
        "weight_kg",
        "emergency_contact_name",
        "emergency_contact_phone",
        "insurance_provider",
        "insurance_policy_number",
    }

    # Fields that belong on User
    user_fields = {"first_name", "last_name", "phone"}

    for field in profile_fields:
        value = data.get(field)
        if value is not None:
            setattr(patient, field, value)

    for field in user_fields:
        value = data.get(field)
        if value is not None:
            setattr(patient.user, field, value)

    db.session.commit()
    db.session.refresh(patient)
    return patient
