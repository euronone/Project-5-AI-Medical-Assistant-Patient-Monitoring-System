from typing import Optional
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.doctor import DoctorProfile


def get_doctors(
    db: Session,
    page: int = 1,
    per_page: int = 20,
    specialization: Optional[str] = None,
    department: Optional[str] = None,
    available_for_telemedicine: Optional[bool] = None,
) -> dict:
    """Return a paginated list of doctors with optional filters."""
    query = (
        db.query(DoctorProfile)
        .join(User, DoctorProfile.user_id == User.id)
        .filter(User.is_active == True)
    )

    if specialization:
        query = query.filter(
            DoctorProfile.specialization.ilike(f"%{specialization.strip()}%")
        )
    if department:
        query = query.filter(
            DoctorProfile.department.ilike(f"%{department.strip()}%")
        )
    if available_for_telemedicine is not None:
        query = query.filter(
            DoctorProfile.available_for_telemedicine == available_for_telemedicine
        )

    total = query.count()
    doctors = (
        query.order_by(User.last_name.asc(), User.first_name.asc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    return {"doctors": doctors, "total": total, "page": page, "per_page": per_page}


def get_doctor_by_id(db: Session, doctor_id: str) -> Optional[DoctorProfile]:
    """Return a single doctor profile with joined user info."""
    return (
        db.query(DoctorProfile)
        .join(User, DoctorProfile.user_id == User.id)
        .filter(DoctorProfile.id == doctor_id)
        .first()
    )


def update_doctor(
    db: Session,
    doctor_id: str,
    data: dict,
    current_user: User,
) -> Optional[DoctorProfile]:
    """
    Update doctor profile fields.

    - Doctors → own profile only
    - Admins  → any profile
    """
    doctor = get_doctor_by_id(db, doctor_id)
    if doctor is None:
        return None

    if current_user.role == "doctor" and doctor.user_id != current_user.id:
        return None

    profile_fields = {
        "specialization", "department", "hospital_affiliation",
        "years_of_experience", "consultation_fee",
        "available_for_telemedicine", "bio",
    }
    user_fields = {"first_name", "last_name", "phone"}

    for field in profile_fields:
        if data.get(field) is not None:
            setattr(doctor, field, data[field])

    for field in user_fields:
        if data.get(field) is not None:
            setattr(doctor.user, field, data[field])

    db.commit()
    db.refresh(doctor)
    return doctor
